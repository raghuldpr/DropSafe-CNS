// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title AuditAnchor
 * @notice DropSafe cryptographic Merkle root anchoring contract for tamper-evident audit ledger commitments.
 */
contract AuditAnchor {
    struct BatchCommitment {
        bytes32 merkleRoot;
        uint64 firstSequence;
        uint64 lastSequence;
        uint64 eventCount;
        uint64 anchoredAt;
        address submitter;
    }

    /// @notice Registry of anchored audit batches indexed by sequential batch number
    mapping(uint256 => BatchCommitment) public batches;

    /// @notice Emitted whenever an audit batch Merkle root is committed on-chain
    event BatchAnchored(
        uint256 indexed batchNumber,
        bytes32 indexed merkleRoot,
        uint64 firstSequence,
        uint64 lastSequence,
        uint64 eventCount,
        address submitter,
        uint256 timestamp
    );

    /**
     * @notice Anchor an audit batch Merkle root commitment to the ledger.
     * @param batchNumber Monotonically increasing batch sequence number
     * @param merkleRoot 32-byte root hash of the deterministic batch Merkle tree
     * @param firstSequence Sequence number of the first event in this batch
     * @param lastSequence Sequence number of the last event in this batch
     * @param eventCount Total number of events contained within this batch
     */
    function anchorBatch(
        uint256 batchNumber,
        bytes32 merkleRoot,
        uint64 firstSequence,
        uint64 lastSequence,
        uint64 eventCount
    ) external {
        require(batchNumber > 0, "Batch number must be positive");
        require(merkleRoot != bytes32(0), "Merkle root cannot be empty");
        require(lastSequence >= firstSequence, "Invalid sequence range");
        require(eventCount > 0, "Event count must be positive");
        require(batches[batchNumber].merkleRoot == bytes32(0), "Batch already anchored");

        batches[batchNumber] = BatchCommitment({
            merkleRoot: merkleRoot,
            firstSequence: firstSequence,
            lastSequence: lastSequence,
            eventCount: eventCount,
            anchoredAt: uint64(block.timestamp),
            submitter: msg.sender
        });

        emit BatchAnchored(
            batchNumber,
            merkleRoot,
            firstSequence,
            lastSequence,
            eventCount,
            msg.sender,
            block.timestamp
        );
    }

    /**
     * @notice Cryptographically verify whether a batch commitments matches the given expected Merkle root.
     * @param batchNumber The batch index to inspect
     * @param expectedRoot The expected 32-byte Merkle root
     * @return bool True if anchored root matches expectedRoot, false otherwise
     */
    function verifyBatchRoot(
        uint256 batchNumber,
        bytes32 expectedRoot
    ) external view returns (bool) {
        return batches[batchNumber].merkleRoot == expectedRoot && expectedRoot != bytes32(0);
    }
}
