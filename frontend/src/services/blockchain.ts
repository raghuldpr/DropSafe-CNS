// DropSafe Blockchain Verification Service
// Directly interacts with the Ethereum AuditAnchor smart contract via RPC

export const AUDIT_ANCHOR_ABI = [
  'function batches(uint256) view returns (bytes32 merkleRoot, uint64 firstSequence, uint64 lastSequence, uint64 eventCount, uint64 anchoredAt, address submitter)',
  'function verifyBatchRoot(uint256 batchNumber, bytes32 expectedRoot) view returns (bool)',
  'event BatchAnchored(uint256 indexed batchNumber, bytes32 indexed merkleRoot, uint64 firstSequence, uint64 lastSequence, uint64 eventCount, address submitter, uint256 timestamp)',
];

export interface OnChainVerificationResult {
  verified: boolean;
  batchNumber: number;
  contractAddress: string;
  onChainMerkleRoot: string;
  anchoredAt?: string;
  submitter?: string;
  error?: string;
}

export async function verifyBatchOnChain(
  batchNumber: number,
  expectedMerkleRootHex: string
): Promise<OnChainVerificationResult> {
  let rpcUrl = import.meta.env.VITE_BLOCKCHAIN_RPC_URL || 'http://127.0.0.1:8545';
  // Allow a same-origin path (e.g. "/rpc") so remote visitors can reach the chain via the dev proxy
  if (rpcUrl.startsWith('/')) rpcUrl = `${window.location.origin}${rpcUrl}`;
  const contractAddress =
    import.meta.env.VITE_AUDIT_ANCHOR_CONTRACT_ADDRESS ||
    '0x0000000000000000000000000000000000000000';

  const normalizedRoot = expectedMerkleRootHex.startsWith('0x')
    ? expectedMerkleRootHex
    : `0x${expectedMerkleRootHex}`;

  try {
    // Dynamic import of ethers to support flexible bundle loads
    const { ethers } = await import('ethers');

    const provider = new ethers.JsonRpcProvider(rpcUrl);
    const contract = new ethers.Contract(contractAddress, AUDIT_ANCHOR_ABI, provider);

    const isMatch: boolean = await contract.verifyBatchRoot(batchNumber, normalizedRoot);
    const batchData = await contract.batches(batchNumber);

    return {
      verified: isMatch,
      batchNumber,
      contractAddress,
      onChainMerkleRoot: batchData.merkleRoot,
      anchoredAt: batchData.anchoredAt ? new Date(Number(batchData.anchoredAt) * 1000).toISOString() : undefined,
      submitter: batchData.submitter,
    };
  } catch (err: any) {
    console.warn(`[DropSafe Web3] Direct RPC check failed or local mock mode: ${err.message}`);
    // If running in development with mock anchor mode or RPC unreachable:
    return {
      verified: false,
      batchNumber,
      contractAddress,
      onChainMerkleRoot: '0x0000000000000000000000000000000000000000000000000000000000000000',
      error: `Could not connect to Ethereum node at ${rpcUrl} (${err.message}). Is local Hardhat node running?`,
    };
  }
}
