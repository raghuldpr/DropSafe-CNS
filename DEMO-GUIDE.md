# DropSafe: Capstone Demo Guide

Two ways to present. **Hosted** is the primary (nothing to start). **Local** is the backup if the internet or the hosted services fail.

| | Hosted (primary) | Local (backup) |
|---|---|---|
| Open | https://dropsafe-cns.pages.dev | `start-demo.bat`, then http://localhost:5173 |
| Chain | Sepolia public testnet | Hardhat on your laptop |
| "Seal & Anchor" takes | about 40 seconds | about 5 to 10 seconds |
| Needs | Internet | Docker Desktop running |

## 0. Rules that prevent a broken demo (read first)

1. **One normal browser profile per user. Never incognito.** Each browser holds the user's private key in its own storage. A browser that has no saved key generates a **new** key at sign-in, and that replaces the user's old key on the server, so earlier files can no longer be opened by that user. Incognito forgets the key every time.
   - Use two different browsers (for example Chrome for Alice, Edge for Bob), or two separate Chrome profiles.
   - Do not clear site data between rehearsal and presentation, or you will start fresh again (that is fine, but do it before sharing, not in the middle).
2. **Bob must sign in once before Alice shares with him.** Sharing locks the file key to Bob's key at the moment of sharing. If Bob has never signed in, the app says he has no encryption key yet.
3. **First sign-in in a browser takes about 10 to 20 seconds** (it generates a 3072-bit key). Say "it's generating my encryption keys in the browser" while it works. Later sign-ins are instant.
4. **Don't restart the local demo mid-presentation.** A restart wipes the local chain and files.
5. **Hosted data persists.** Anything you change (for example Bob's clearance) stays changed. Set it back after you show it.

## 1. Before the exam

**The day before (hosted):**
1. Open https://dropsafe-cns.pages.dev in both browsers you'll use. Sign in as Alice in one and Bob in the other, once each, so the keys exist.
2. Rehearse the full script below once, including sharing and revoking.
3. Open `https://dropsafe-api-50047831488.development.catalystappsail.in/api/v1/health` and check it says `healthy`.

**30 minutes before:**
1. Load the site once to wake the backend (it sleeps when idle; the first request can take a couple of seconds).
2. Sign in as Alice and Bob in their browsers so both are ready.
3. Have the Etherscan link ready in a tab: https://sepolia.etherscan.io/address/0xcF21E2e72D327a2a698cB4F10271599995Def5b8
4. (Backup) Start Docker Desktop and run `start-demo.bat` once to confirm the local version still starts (about 30 to 70 seconds). Then `stop-demo.bat`, or leave it running in the background if you want the backup instantly available.

**Local start details:** `start-demo.bat` starts Postgres and Redis (Docker), the local Hardhat chain with a fresh contract, migrates and seeds the database, then starts the backend, the anchoring worker and the frontend, and opens http://localhost:5173. Every start is a clean slate. Stop with `stop-demo.bat`. Logs: `backend.log`, `worker.log`, `frontend.log`, `hardhat.log`.

If Docker Desktop shows a "sailor" error, restart Windows (Restart, not Shut down) and open Docker again.

## 2. The 60-second pitch

> "DropSafe is a zero-knowledge file vault. Files are encrypted **in the browser** before upload, so the server only ever stores ciphertext. Sharing is governed by **ABAC** (attribute-based access control) plus per-file grants. Every action goes into a **tamper-evident audit log**: events are SHA-256 hash-chained, grouped into **Merkle trees**, and each Merkle root is **anchored on a blockchain**. Anyone can later prove an event existed and was not altered."

| Layer | Tech | Role |
|---|---|---|
| Frontend | React + Vite + TypeScript on Cloudflare Pages | Client-side crypto (WebCrypto), UI, on-chain verification via ethers |
| Backend | FastAPI on Zoho Catalyst AppSail | Auth, ABAC policy engine, wrapped-key management, audit ledger |
| Database | Neon PostgreSQL (hosted), local Postgres (backup) | Users, attributes, metadata, grants, audit events, encrypted file blobs |
| Worker | Python outbox worker | Picks up sealed batches and anchors the Merkle root on-chain |
| Blockchain | `AuditAnchor` Solidity contract on Sepolia (hosted), Hardhat (local) | Immutable store of batch Merkle roots |

Ideas worth naming: envelope encryption (a per-file key wrapped separately for each recipient), default-deny authorization, signed attribute credentials, the outbox pattern for reliable anchoring.

## 3. Demo accounts (one click on the sign-in page)

| Button | Email | Password | Attributes | Role in the demo |
|---|---|---|---|---|
| Alice (Owner) | alice@dropsafe.local | AlicePass123! | engineering, clearance 2 | File owner who shares |
| Bob (Finance) | bob@dropsafe.local | BobPass123! | finance, clearance 1 | Allowed recipient |
| Charlie (Contractor) | charlie@dropsafe.local | CharliePass123! | engineering, contractor | Blocked by the policy |
| Admin | admin@dropsafe.local | AdminPass123! | admin role | Manages trusted attributes |

## 4. Demo script (about 10 minutes)

**A. Landing and sign-in (1 min)**
Show the landing page, then Sign In. Point at the Quick Demo Accounts card: these are seeded users with different attributes. Click **Alice (Owner)** in her browser (this is where the key generation pause happens if it is the first time).

**B. Upload and client-side encryption (2 min), as Alice**
1. Upload a small PDF or image.
2. Show the progress stages (hash, encrypt in the browser, wrap the key, upload ciphertext).
3. Say: "The server never sees the plaintext or the file key."
4. Open the file's details: size, SHA-256 and encryption metadata.

**C. Sharing with ABAC, then revocation (3 min)**
1. As Alice, apply a policy to the file: **department equals finance** (Access Policies page).
2. Try to share with **charlie@dropsafe.local**. It is refused: Charlie is not eligible under the policy. He is in engineering, so job title does not matter, attributes do. Default-deny.
3. Share with **bob@dropsafe.local**. This succeeds.
4. In Bob's browser, open **Shared with me**, open the file, and download or view it. It decrypts for him because the file key was wrapped for his key.
5. Back as Alice, open **Shared by me** and **Revoke** Bob's access. In Bob's browser, try again: access is denied.
6. Say: "Revocation stops future access and key issuance. It can't erase a copy that was already downloaded."

**D. Audit and blockchain (3 min), as Alice**
1. Open **Audit Log**. Every upload, share, denial and revocation is listed.
2. Click **Verify Hash Chain** and show the "valid" result. Each event includes the previous event's hash, so editing history breaks the chain.
3. Click **Seal & Anchor Batch**. This builds a Merkle tree over the new events and queues an anchoring job. **On the hosted version this takes about 40 seconds** because it is a real Sepolia transaction. While it runs, explain the Merkle tree, and click **Refresh** every 10 to 15 seconds. The backend sleeps when idle, so keeping the page active keeps it awake until the batch shows **anchored**.
4. Open the **Merkle Batches & On-Chain Anchors** tab, open an event's proof and show the on-chain verification result. The root is read straight from the smart contract.
5. Open the Etherscan link and show the contract and the transaction.
6. Say: "Even a database admin can't silently alter history, because the root is on the chain."

**E. Admin (1 min)**
1. Click **Admin** on the sign-in card (separate browser or after signing out), then **Admin Console** in the sidebar. Only admins see this item, and the backend refuses the admin endpoints for other users.
2. Show the user table with roles and attributes.
3. Select Bob, set `clearance_level` to 3, save. A green banner confirms it and notes the change is audited.
4. Show the new `admin.user_attribute.assigned` event in the Audit Log.
5. **Set Bob's clearance back to 1** (hosted data persists).
This answers "who decides the attributes ABAC trusts?": only an admin, with every change audited.

## 5. Likely examiner questions

- **Why blockchain, not just a log?** A database log can be rewritten by whoever controls the database. The on-chain Merkle root is independent, tamper-evident evidence, and only a hash goes on-chain, never sensitive data.
- **Why Merkle batches?** One transaction covers many events, which keeps gas cost low, and each event still gets an inclusion proof.
- **What does the server know?** Metadata, wrapped keys, policies and audit events. Never plaintext or unwrapped keys.
- **What does revocation not do?** It cannot erase a copy already downloaded. It stops future access.
- **What if the user loses their browser key?** The file keys wrapped for that key are unrecoverable by design. That is the zero-knowledge trade-off.
- **Why Sepolia and not mainnet?** It is a free public testnet with the same EVM behavior, so the contract and flow are identical. Moving to mainnet is a configuration and cost decision, not a code change.
- **Why a local Hardhat chain as well?** A deterministic offline backup for demos and tests.
- **Public share links?** A deliberate design decision not to implement them, to avoid leaking the file key in a URL.
- **How is it hosted for free?** Cloudflare Pages (frontend and proxy), Zoho Catalyst AppSail (backend and worker), Neon Postgres, and the Sepolia testnet. Details are in `DEPLOY.md`.
- **Evidence of testing?** 86 backend tests, 5 smart-contract tests, and end-to-end scripts in `backend/scripts/` for the encryption round trip, sharing with ABAC and revocation, cryptographic integrity and real anchoring.

## 6. Troubleshooting

| Symptom | Fix |
|---|---|
| Hosted site slow on the first click | The backend was asleep; wait a few seconds and retry |
| "Failed to fetch" at sign-in | Check the health URL above; if it is down, switch to the local backup |
| A recipient can't open a shared file | Their browser is not the one that holds their key (incognito, a different browser, or cleared data). Have them sign in on the original browser. In the worst case, upload a fresh file and share again |
| "Recipient has not registered an encryption key" | Have that user sign in once in their own browser, then share again |
| Batch stays "prepared" | The backend slept before anchoring. Click Refresh a few times to wake it; it will finish on its own |
| Anchoring seems stuck for minutes | Check the health URL; as a last resort, open the audit page again |
| Local: "Docker not running" | Start Docker Desktop and wait for it, then rerun `start-demo.bat`. If it crashes with a "sailor" error, restart Windows |
| Local: port already in use | Run `stop-demo.bat`, then start again |
| Everything weird locally | `stop-demo.bat`, then `start-demo.bat` (always a clean slate) |

**If both fail:** all documents are in `docs/` (PRD, TRD, app flow, schema), and `docs/architecture/dropsafe_overall_architecture.html` is a diagram you can walk through, along with the test output from `pytest` and `npx hardhat test`.
