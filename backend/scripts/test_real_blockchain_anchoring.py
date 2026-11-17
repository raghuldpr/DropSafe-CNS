import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.audit import AuditBatch, AuditEvent, BlockchainAnchor, OutboxJob
from app.audit import service as audit_service
from app.worker.worker import OutboxWorker, AUDIT_ANCHOR_ABI
from web3 import Web3
from sqlalchemy import select

async def run():
    print("=== TASK 5: REAL LOCAL BLOCKCHAIN ANCHORING TEST ===")
    
    # 1. Verify Web3 Connection & Contract State
    print(f"[1] Connecting to EVM RPC at {settings.EVM_RPC_URL}...")
    w3 = Web3(Web3.HTTPProvider(settings.EVM_RPC_URL))
    assert w3.is_connected(), f"Failed to connect to EVM RPC at {settings.EVM_RPC_URL}"
    chain_id = w3.eth.chain_id
    current_block = w3.eth.block_number
    print(f"    Connected to chain_id={chain_id}, current_block={current_block}")
    
    contract_address = Web3.to_checksum_address(settings.ANCHOR_CONTRACT_ADDRESS)
    contract = w3.eth.contract(address=contract_address, abi=AUDIT_ANCHOR_ABI)
    print(f"    AuditAnchor contract bound at {contract_address}")
    
    signer_key = settings.ANCHOR_SIGNER_PRIVATE_KEY or settings.EVM_SIGNER_PRIVATE_KEY
    account = w3.eth.account.from_key(signer_key)
    signer_balance = w3.eth.get_balance(account.address)
    print(f"    Local Signer address: {account.address} (Balance: {w3.from_wei(signer_balance, 'ether')} ETH)")

    async with AsyncSessionLocal() as session:
        # 2. Check for unbatched audit events or create audit events
        print("\n[2] Checking for unbatched audit events...")
        unbatched_count = (await session.execute(
            select(AuditEvent).where(AuditEvent.batch_id.is_(None))
        )).scalars().all()
        print(f"    Found {len(unbatched_count)} unbatched audit events in database.")
        
        if len(unbatched_count) == 0:
            print("    Creating sample audit event to anchor...")
            await audit_service.record_audit_event(
                db=session,
                event_type="test.blockchain.anchor",
                outcome="success",
                metadata={"test_run": "task_5_blockchain_verification"}
            )
            await session.commit()

        # 3. Aggregate into AuditBatch
        print("\n[3] Creating AuditBatch from unbatched events...")
        batch_resp = await audit_service.create_audit_batch(session)
        assert batch_resp is not None, "Failed to create audit batch!"
        await session.commit()
        
        batch_id = batch_resp.id
        batch_number = batch_resp.batch_number
        merkle_root_hex = batch_resp.merkle_root_hex
        event_count = batch_resp.event_count
        print(f"    Created AuditBatch: batch_number={batch_number}, events={event_count}, merkle_root={merkle_root_hex}")

        # 4. Process Outbox Job using OutboxWorker
        print("\n[4] Running OutboxWorker to anchor batch to real local Hardhat blockchain...")
        worker = OutboxWorker(worker_id="test-local-blockchain-worker")
        job = await worker.fetch_and_claim_job(session)
        assert job is not None, "No outbox job found to claim!"
        print(f"    Claimed OutboxJob: id={job.id}, type={job.job_type}, aggregate_id={job.aggregate_id}")
        
        success = await worker.execute_job(session, job)
        assert success is True, "OutboxWorker failed to execute anchoring job!"
        await session.commit()
        print(f"    OutboxJob {job.id} executed successfully with status '{job.status}'.")

        # 5. Verify BlockchainAnchor and DB state
        print("\n[5] Verifying database records for BlockchainAnchor and AuditBatch...")
        db_batch = (await session.execute(select(AuditBatch).where(AuditBatch.id == batch_id))).scalar_one()
        assert db_batch.status == "anchored", f"Expected batch status 'anchored', got '{db_batch.status}'"
        print(f"    AuditBatch {batch_id} status: '{db_batch.status}', anchored_at: {db_batch.anchored_at}")

        anchor = (await session.execute(
            select(BlockchainAnchor).where(BlockchainAnchor.batch_id == batch_id)
        )).scalar_one()
        tx_hash = anchor.transaction_hash
        block_num = anchor.block_number
        print(f"    BlockchainAnchor recorded:")
        print(f"      - Network: {anchor.network_name}")
        print(f"      - Chain ID: {anchor.chain_id}")
        print(f"      - Contract Address: {anchor.contract_address}")
        print(f"      - Transaction Hash: {tx_hash}")
        print(f"      - Block Number: {block_num}")
        print(f"      - Status: {anchor.status}")

        # 6. Verify Transaction Receipt directly from Hardhat node
        print("\n[6] Verifying actual transaction receipt on Hardhat JSON-RPC node...")
        receipt = w3.eth.get_transaction_receipt(tx_hash)
        assert receipt is not None, f"No receipt found on chain for tx {tx_hash}"
        assert receipt.status == 1, "Transaction reverted on chain!"
        gas_used = receipt.gasUsed
        print(f"    Transaction receipt confirmed: status={receipt.status}, block={receipt.blockNumber}, gasUsed={gas_used}")

        # 7. Query AuditAnchor Smart Contract (verifyBatchRoot)
        print("\n[7] Querying smart contract verifyBatchRoot() on-chain...")
        root_bytes = bytes.fromhex(merkle_root_hex)
        is_verified_onchain = contract.functions.verifyBatchRoot(batch_number, root_bytes).call()
        assert is_verified_onchain is True, "Smart contract verifyBatchRoot returned FALSE for anchored Merkle root!"
        print(f"    Contract verifyBatchRoot({batch_number}, 0x{merkle_root_hex}) -> TRUE!")

        # Also test with a tampered root
        tampered_root = bytearray(root_bytes)
        tampered_root[0] ^= 0x01
        is_tampered_verified = contract.functions.verifyBatchRoot(batch_number, bytes(tampered_root)).call()
        assert is_tampered_verified is False, "Smart contract accepted tampered Merkle root!"
        print("    Contract verifyBatchRoot with tampered root -> FALSE (tamper-evident confirmation).")

        print("\n>>> ALL TASK 5 REAL LOCAL BLOCKCHAIN VERIFICATION CHECKS PASSED! <<<")

if __name__ == "__main__":
    asyncio.run(run())
