import { ethers } from "hardhat";

// Generates a brand-new throwaway wallet for Sepolia. Fund the address from a faucet, then use the
// private key as ANCHOR_SIGNER_PRIVATE_KEY. TEST NETWORK ONLY: never reuse this key on mainnet.
const wallet = ethers.Wallet.createRandom();
console.log("Address     :", wallet.address);
console.log("Private key :", wallet.privateKey);
