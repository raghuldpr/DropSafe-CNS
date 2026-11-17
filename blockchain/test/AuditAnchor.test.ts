import { expect } from "chai";
import { ethers } from "hardhat";
import { AuditAnchor } from "../typechain-types";

describe("AuditAnchor Smart Contract", function () {
  let anchor: AuditAnchor;
  let owner: any;
  let user: any;

  beforeEach(async function () {
    [owner, user] = await ethers.getSigners();
    const AuditAnchorFactory = await ethers.getContractFactory("AuditAnchor");
    anchor = await AuditAnchorFactory.deploy();
    await anchor.waitForDeployment();
  });

  after(async function () {
    // Explicitly allow pending asynchronous handles and event loop ticks to drain before test teardown
    await new Promise((resolve) => setTimeout(resolve, 100));
  });

  it("should deploy with unanchored initial state", async function () {
    const isVerified = await anchor.verifyBatchRoot(1, ethers.ZeroHash);
    expect(isVerified).to.be.false;
  });

  it("should successfully anchor an audit batch and emit BatchAnchored event", async function () {
    const dummyRoot = ethers.keccak256(ethers.toUtf8Bytes("merkle-root-batch-1"));
    const tx = await anchor.anchorBatch(1, dummyRoot, 1, 100, 100);
    const receipt = await tx.wait();
    expect(receipt?.status).to.equal(1);

    const isVerified = await anchor.verifyBatchRoot(1, dummyRoot);
    expect(isVerified).to.be.true;

    // Check mapping fields
    const batchData = await anchor.batches(1);
    expect(batchData.merkleRoot).to.equal(dummyRoot);
    expect(batchData.firstSequence).to.equal(1n);
    expect(batchData.lastSequence).to.equal(100n);
    expect(batchData.eventCount).to.equal(100n);
    expect(batchData.submitter).to.equal(owner.address);
  });

  it("should reject anchoring an already anchored batch number", async function () {
    const dummyRoot = ethers.keccak256(ethers.toUtf8Bytes("merkle-root-batch-1"));
    await anchor.anchorBatch(1, dummyRoot, 1, 50, 50);

    await expect(
      anchor.anchorBatch(1, dummyRoot, 1, 50, 50)
    ).to.be.revertedWith("Batch already anchored");
  });

  it("should reject anchoring empty root or invalid sequence", async function () {
    await expect(
      anchor.anchorBatch(1, ethers.ZeroHash, 1, 10, 10)
    ).to.be.revertedWith("Merkle root cannot be empty");

    const dummyRoot = ethers.keccak256(ethers.toUtf8Bytes("root"));
    await expect(
      anchor.anchorBatch(1, dummyRoot, 10, 5, 10)
    ).to.be.revertedWith("Invalid sequence range");
  });

  it("should return false when verifying with tampered or non-matching root", async function () {
    const validRoot = ethers.keccak256(ethers.toUtf8Bytes("valid-root"));
    const wrongRoot = ethers.keccak256(ethers.toUtf8Bytes("wrong-root"));

    await anchor.anchorBatch(2, validRoot, 101, 200, 100);
    expect(await anchor.verifyBatchRoot(2, validRoot)).to.be.true;
    expect(await anchor.verifyBatchRoot(2, wrongRoot)).to.be.false;
  });
});
