import argparse
import asyncio
import hashlib
import os
import signal
import socket
import sys
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import service as audit_service
from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import AsyncSessionLocal, engine
from app.models.audit import AuditBatch, BlockchainAnchor, OutboxJob

logger = get_logger(__name__)

MAX_JOB_RETRIES = 5
LOCK_TIMEOUT_SECONDS = 300


AUDIT_ANCHOR_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "uint256", "name": "batchNumber", "type": "uint256"},
            {"indexed": True, "internalType": "bytes32", "name": "merkleRoot", "type": "bytes32"},
            {"indexed": False, "internalType": "uint64", "name": "firstSequence", "type": "uint64"},
            {"indexed": False, "internalType": "uint64", "name": "lastSequence", "type": "uint64"},
            {"indexed": False, "internalType": "uint64", "name": "eventCount", "type": "uint64"},
            {"indexed": False, "internalType": "address", "name": "submitter", "type": "address"},
            {"indexed": False, "internalType": "uint256", "name": "timestamp", "type": "uint256"},
        ],
        "name": "BatchAnchored",
        "type": "event",
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "batchNumber", "type": "uint256"},
            {"internalType": "bytes32", "name": "merkleRoot", "type": "bytes32"},
            {"internalType": "uint64", "name": "firstSequence", "type": "uint64"},
            {"internalType": "uint64", "name": "lastSequence", "type": "uint64"},
            {"internalType": "uint64", "name": "eventCount", "type": "uint64"},
        ],
        "name": "anchorBatch",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "uint256", "name": "batchNumber", "type": "uint256"},
            {"internalType": "bytes32", "name": "expectedRoot", "type": "bytes32"},
        ],
        "name": "verifyBatchRoot",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    },
]


class OutboxWorker:
    """Worker process responsible for deterministic Merkle batching and blockchain anchoring."""

    def __init__(self, worker_id: Optional[str] = None):
        hostname = socket.gethostname()
        pid = os.getpid()
        rand_id = uuid.uuid4().hex[:6]
        self.worker_id = worker_id or f"worker-{hostname}-{pid}-{rand_id}"
        self._running = False

    async def fetch_and_claim_job(self, db: AsyncSession) -> Optional[OutboxJob]:
        """Claim next pending outbox job using lease locking."""
        now = datetime.now(timezone.utc)
        lock_cutoff = now - timedelta(seconds=LOCK_TIMEOUT_SECONDS)

        # Select jobs that are pending OR stalled in processing past lock timeout
        stmt = (
            select(OutboxJob)
            .where(
                or_(
                    OutboxJob.status == "pending",
                    (OutboxJob.status == "processing") & (OutboxJob.locked_at < lock_cutoff),
                ),
                OutboxJob.run_after <= now,
            )
            .order_by(OutboxJob.run_after.asc(), OutboxJob.created_at.asc())
            .limit(1)
        )
        job = (await db.execute(stmt)).scalar_one_or_none()
        if not job:
            return None

        job.status = "processing"
        job.locked_at = now
        job.locked_by = self.worker_id
        await db.commit()
        await db.refresh(job)
        return job

    async def execute_job(self, db: AsyncSession, job: OutboxJob) -> bool:
        """Process a single claimed outbox job according to its job_type."""
        logger.info(f"Processing outbox job {job.id} (type={job.job_type}, aggregate_id={job.aggregate_id})")

        try:
            if job.job_type == "build_audit_batch":
                await self._handle_build_audit_batch(db, job)
            elif job.job_type == "anchor_batch":
                await self._handle_anchor_batch(db, job)
            else:
                logger.warning(f"Unrecognized job type '{job.job_type}' for job {job.id}")
                job.status = "failed"
                job.last_error_code = "UNKNOWN_JOB_TYPE"
                job.locked_at = None
                job.locked_by = None
                await db.commit()
                return False

            job.status = "succeeded"
            job.locked_at = None
            job.locked_by = None
            job.last_error_code = None
            await db.commit()
            logger.info(f"Outbox job {job.id} succeeded")
            return True

        except Exception as e:
            logger.exception(f"Error processing outbox job {job.id}: {e}")
            await db.rollback()

            now = datetime.now(timezone.utc)
            job.attempt_count += 1
            job.locked_at = None
            job.locked_by = None
            job.last_error_code = str(e)[:80]

            if job.attempt_count >= MAX_JOB_RETRIES:
                job.status = "failed"
                logger.error(f"Outbox job {job.id} failed permanently after {job.attempt_count} attempts")
                # Mark batch failed if anchor_batch
                if job.job_type == "anchor_batch":
                    batch_stmt = select(AuditBatch).where(AuditBatch.id == job.aggregate_id)
                    batch = (await db.execute(batch_stmt)).scalar_one_or_none()
                    if batch:
                        batch.status = "failed"
            else:
                job.status = "pending"
                backoff_seconds = min(2 ** job.attempt_count, 300)
                job.run_after = now + timedelta(seconds=backoff_seconds)
                logger.info(f"Outbox job {job.id} rescheduled for attempt {job.attempt_count + 1} in {backoff_seconds}s")

            await db.commit()
            return False

    async def _handle_build_audit_batch(self, db: AsyncSession, job: OutboxJob) -> None:
        """Aggregate unbatched events into a new AuditBatch."""
        batch = await audit_service.create_audit_batch(db)
        if batch:
            logger.info(f"Successfully aggregated audit batch {batch.id} via job {job.id}")
        else:
            logger.info("No unbatched audit events found to aggregate")

    async def _handle_anchor_batch(self, db: AsyncSession, job: OutboxJob) -> None:
        """Anchor an AuditBatch Merkle root to the target blockchain/mock ledger."""
        stmt = select(AuditBatch).where(AuditBatch.id == job.aggregate_id)
        batch = (await db.execute(stmt)).scalar_one_or_none()
        if not batch:
            raise ValueError(f"AuditBatch {job.aggregate_id} not found")

        if batch.status == "anchored":
            logger.info(f"AuditBatch {batch.id} is already anchored; skipping")
            return

        now = datetime.now(timezone.utc)
        batch.status = "anchoring"
        await db.flush()

        mode = (settings.AUDIT_ANCHOR_MODE or "mock").lower()

        if mode in ("local", "sepolia") and settings.EVM_RPC_URL:
            # Live RPC anchoring mode via Web3.py
            logger.info(f"Anchoring batch {batch.id} via live EVM RPC: {settings.EVM_RPC_URL}")
            try:
                from web3 import Web3

                w3 = Web3(Web3.HTTPProvider(settings.EVM_RPC_URL, request_kwargs={"timeout": 15}))
                if not w3.is_connected():
                    raise ConnectionError(f"Cannot connect to EVM RPC endpoint: {settings.EVM_RPC_URL}")

                signer_key = settings.EVM_SIGNER_PRIVATE_KEY or settings.ANCHOR_SIGNER_PRIVATE_KEY
                if not signer_key:
                    raise ValueError("EVM_SIGNER_PRIVATE_KEY or ANCHOR_SIGNER_PRIVATE_KEY is not configured")

                account = w3.eth.account.from_key(signer_key)
                contract_address = Web3.to_checksum_address(settings.ANCHOR_CONTRACT_ADDRESS)
                contract = w3.eth.contract(address=contract_address, abi=AUDIT_ANCHOR_ABI)

                chain_id = w3.eth.chain_id
                nonce = w3.eth.get_transaction_count(account.address)

                # Ensure 32-byte merkle root
                merkle_root_bytes32 = batch.merkle_root if len(batch.merkle_root) == 32 else batch.merkle_root[:32].ljust(32, b"\x00")

                tx_data = contract.functions.anchorBatch(
                    int(batch.batch_number),
                    merkle_root_bytes32,
                    int(batch.first_sequence_number),
                    int(batch.last_sequence_number),
                    int(batch.event_count),
                ).build_transaction({
                    "from": account.address,
                    "nonce": nonce,
                    "chainId": chain_id,
                    "gasPrice": w3.eth.gas_price,
                })

                signed_tx = w3.eth.account.sign_transaction(tx_data, private_key=signer_key)
                tx_hash_bytes = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
                tx_hash = w3.to_hex(tx_hash_bytes)

                receipt = w3.eth.wait_for_transaction_receipt(tx_hash_bytes, timeout=60)
                block_number = receipt.get("blockNumber")
                tx_status = "confirmed" if receipt.get("status") == 1 else "failed"

                anchor = BlockchainAnchor(
                    batch_id=batch.id,
                    chain_id=chain_id,
                    network_name=mode,
                    contract_address=settings.ANCHOR_CONTRACT_ADDRESS,
                    transaction_hash=tx_hash,
                    block_number=block_number,
                    status=tx_status,
                    submitted_at=now,
                    confirmed_at=now if tx_status == "confirmed" else None,
                    confirmation_count=1 if tx_status == "confirmed" else 0,
                )
                db.add(anchor)

                if tx_status == "confirmed":
                    batch.status = "anchored"
                    batch.anchored_at = now
                else:
                    batch.status = "failed"
                await db.flush()
                logger.info(f"Batch {batch.id} live-anchored successfully (tx={tx_hash}, block={block_number})")
            except Exception as e:
                logger.warning(f"Live EVM anchoring failed for batch {batch.id}: {e}. Recording failure.")
                anchor = BlockchainAnchor(
                    batch_id=batch.id,
                    chain_id=11155111 if mode == "sepolia" else 31337,
                    network_name=mode,
                    contract_address=settings.ANCHOR_CONTRACT_ADDRESS or "0x0000000000000000000000000000000000000000",
                    transaction_hash=None,
                    block_number=None,
                    status="failed",
                    error_code=str(e)[:80],
                    submitted_at=now,
                    confirmed_at=None,
                    confirmation_count=0,
                )
                db.add(anchor)
                await db.flush()
                raise
        else:
            # Deterministic Mock Anchoring:
            # Generates a valid 0x hex transaction hash and simulated Sepolia block height
            seed_data = f"{batch.id}:{batch.merkle_root.hex()}:{batch.batch_number}".encode("utf-8")
            tx_hash = "0x" + hashlib.sha256(seed_data).hexdigest()
            block_number = 5000000 + batch.batch_number
            chain_id = 11155111  # Sepolia testnet ID
            network_name = "sepolia-mock"
            contract_addr = settings.ANCHOR_CONTRACT_ADDRESS or "0x0000000000000000000000000000000000000000"

            anchor = BlockchainAnchor(
                batch_id=batch.id,
                chain_id=chain_id,
                network_name=network_name,
                contract_address=contract_addr,
                transaction_hash=tx_hash,
                block_number=block_number,
                status="confirmed",
                submitted_at=now,
                confirmed_at=now,
                confirmation_count=1,
            )
            db.add(anchor)
            batch.status = "anchored"
            batch.anchored_at = now
            await db.flush()
            logger.info(f"Batch {batch.id} mock-anchored successfully (tx={tx_hash}, block={block_number})")

    async def run_once(self) -> int:
        """Process all currently ready pending outbox jobs until queue is empty. Returns processed count."""
        processed_count = 0
        while True:
            async with AsyncSessionLocal() as db:
                job = await self.fetch_and_claim_job(db)
                if not job:
                    break
                success = await self.execute_job(db, job)
                if success:
                    processed_count += 1
        return processed_count

    async def run_loop(self, poll_interval: float = 3.0) -> None:
        """Continuous polling loop for outbox jobs."""
        self._running = True
        logger.info(f"Starting OutboxWorker [{self.worker_id}] with poll_interval={poll_interval}s")

        while self._running:
            try:
                processed = await self.run_once()
                if processed == 0:
                    await asyncio.sleep(poll_interval)
            except asyncio.CancelledError:
                logger.info(f"Worker [{self.worker_id}] received cancellation signal; stopping")
                break
            except Exception as e:
                logger.exception(f"Unexpected worker loop exception: {e}")
                await asyncio.sleep(poll_interval)

    def stop(self) -> None:
        """Signal worker loop to terminate."""
        self._running = False


async def main() -> None:
    parser = argparse.ArgumentParser(description="DropSafe Outbox & Blockchain Anchor Worker")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run pending jobs once and exit immediately",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=3.0,
        help="Polling interval in seconds (default: 3.0)",
    )
    args = parser.parse_args()

    worker = OutboxWorker()

    if args.once:
        logger.info("Executing worker in one-shot mode (--once)...")
        count = await worker.run_once()
        logger.info(f"One-shot processing complete. Total jobs processed: {count}")
    else:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, worker.stop)
            except (NotImplementedError, AttributeError):
                # Windows does not support add_signal_handler for all signals
                pass

        try:
            await worker.run_loop(poll_interval=args.poll_interval)
        finally:
            await engine.dispose()


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
