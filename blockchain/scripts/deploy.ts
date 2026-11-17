import { ethers } from "hardhat";

async function main() {
  console.log("Deploying DropSafe AuditAnchor contract...");

  const [deployer] = await ethers.getSigners();
  console.log("Deploying with account:", deployer.address);

  const AuditAnchor = await ethers.getContractFactory("AuditAnchor");
  const anchor = await AuditAnchor.deploy();
  await anchor.waitForDeployment();

  const contractAddress = await anchor.getAddress();
  console.log(`DropSafe AuditAnchor successfully deployed to: ${contractAddress}`);
  console.log(`Save this contract address to ANCHOR_CONTRACT_ADDRESS in your backend .env file:`);
  console.log(`ANCHOR_CONTRACT_ADDRESS=${contractAddress}`);
}

main().catch((error) => {
  console.error("Deployment failed:", error);
  process.exitCode = 1;
});
