# DropSafe: Capstone Demo Guide

## 0. Before the exam

1. Open **Docker Desktop** and wait until it says "running".
2. Double-click **`start-demo.bat`** in the `DropSafe` folder (~30–60 s). It:
   - starts Postgres and Redis (Docker),
   - starts the local blockchain (Hardhat) and redeploys the audit contract,
   - migrates and seeds the database (users, attributes),
   - starts the backend (:8000), the audit-anchoring worker, and the frontend (:5173),
   - opens http://localhost:5173.
3. **Every start is a clean slate by default.** The launcher wipes the database and reseeds the four demo users each time, because the local blockchain and file storage are in-memory and empty on every start. This guarantees every batch you seal is on the current chain, so on-chain verification always works. (Advanced: `start-demo.bat -Keep` keeps the old database, but old batches will then fail on-chain verification.)
4. Afterwards, double-click **`stop-demo.bat`**.

Pre-flight checklist (all verified): sign-in works for all four users; Admin Console loads for Admin only (Alice gets 403); "Verify Hash Chain" reports valid; "Seal & Anchor Batch" turns `prepared` into `anchored` within ~7 s; cold start takes ~25–35 s.

Logs if anything misbehaves: `backend.log`, `worker.log`, `frontend.log`, `hardhat.log`.

Note: the chain and file storage are in-memory by design for dev. Restarting wipes uploaded files and on-chain anchors, so start once and don't restart mid-demo.

## 1. The 60-second pitch

> "DropSafe is a zero-knowledge file vault. Files are encrypted **in the browser** before upload, so the server only ever stores ciphertext. Sharing is governed by **ABAC** (attribute-based access control) plus per-file grants. Every action is written to a **tamper-evident audit log**: events are SHA-256 hash-chained, grouped into **Merkle trees**, and the Merkle root is **anchored on a blockchain**. Anyone can later prove an event existed and was not altered."

Architecture (one line each):

| Layer | Tech | Role |
|---|---|---|
| Frontend | React + Vite + TS | Client-side crypto (WebCrypto), UI, on-chain verification via ethers |
| Backend | FastAPI | Auth (JWT), ABAC policy engine, wrapped-key mgmt, audit ledger |
| Database | PostgreSQL 16 | Users, attributes, documents (metadata only), grants, audit events |
| Cache/queue | Redis 7 | Caching / rate limiting |
| Worker | Python outbox worker | Picks up sealed batches and anchors the Merkle root on-chain |
| Blockchain | Hardhat local EVM + `AuditAnchor` Solidity contract | Immutable store of batch Merkle roots |

Key security ideas to name-drop: envelope encryption (per-file key wrapped per recipient), default-deny authorization, signed attribute credentials, outbox pattern for reliable anchoring, revocation = key-version rotation / grant removal.

## 2. Demo accounts (on the sign-in page, one click each)

| Button | Email | Password | Attributes | Purpose |
|---|---|---|---|---|
| Alice (Owner) | alice@dropsafe.local | AlicePass123! | Engineering, clearance 2, projects apollo/core-infra | File owner / sharer |
| Bob (Finance) | bob@dropsafe.local | BobPass123! | Finance, clearance 1 | Recipient who should be **denied** by policy |
| Charlie (Contractor) | charlie@dropsafe.local | CharliePass123! | Engineering, contractor | Same department as Alice but a contractor, for policy contrast |
| Admin | admin@dropsafe.local | AdminPass123! | admin role | Attribute administration |

Clicking a demo button signs you in directly. Use a different browser profile or an incognito window for the second user so both can be shown side by side.

## 3. Demo script (about 10 minutes)

**A. Landing and sign-in (1 min)**
Show the landing page, then Sign In. Point at the "Quick Demo Accounts" card and explain these are seeded users with different attributes.

**B. Upload and client-side encryption (2 min), as Alice**
1. Click **Alice (Owner)**.
2. Upload a small PDF or image. Show the animated progress stages: *hash, encrypt in browser, wrap key, upload ciphertext*.
3. Say: "The server never sees the plaintext or the file key."
4. Open **My Files**, then the file's details: show size, SHA-256, encryption metadata.

**C. Sharing with ABAC (3 min)**
1. From file details, click **Share**. Share with **Bob** (optionally set an expiry).
2. Open **Access Policies**. Show the rule builder (department / clearance / project conditions) and explain default-deny: a grant alone isn't enough, the attributes must satisfy the policy.
3. In a second window, sign in as **Bob**. Open **Shared with me**. Show what happens when the policy blocks him (**Access Denied** page, with no information leak).
4. Sign in as **Charlie** to contrast: same department as Alice but a contractor, so different outcome. Use this to show attributes beat job titles.
5. Back as Alice, use **Shared by me** to **Revoke** Bob's grant. Bob can no longer open or download it.

**D. Audit and blockchain (3 min), as Alice or Admin**
1. Open **Audit Log**. Every upload, share, denial and revocation is listed.
2. Click **Verify Hash Chain** and show the green "valid" result. Explain each event includes the previous event's hash, so editing history breaks the chain.
3. Click **Seal & Anchor Batch**. This builds a Merkle tree over the new events and queues an anchoring job. After ~5 s the batch shows **anchored**, and the worker has written the root to the local chain.
4. Go to the **Merkle Batches & On-Chain Anchors** tab and open an event's proof. Show the Merkle path, then the **on-chain verification** result (the root is read straight from the smart contract, not from our database).
5. Say: "Even a database admin can't silently alter history, because the root is on the chain."

**E. Admin (1 min)**
Click **Admin** on the sign-in card, then **Admin Console** in the sidebar (only admins see this item; Alice gets Access Denied, and the backend returns 403 for her token). Show:
1. The user table with each person's roles and ABAC attributes.
2. Select Bob, then set `clearance_level` to 3 and save. A green banner confirms it, and the credential is re-signed.
3. Open **Audit Log**: the `admin.user_attribute.assigned` event is there.
4. Back in the Admin Console, set Bob back to 1 (or just restart: every start resets to a clean slate).
This is the answer to "who decides the attributes that ABAC trusts?": only an admin, with every change audited.

## 4. Likely examiner questions

- **Why blockchain, not just a log?** A DB log can be rewritten by whoever controls the DB. The on-chain Merkle root gives independent, tamper-evident anchoring without storing sensitive data on-chain (only a hash).
- **Why Merkle batches?** One transaction covers thousands of events, which keeps gas cost low, and each event still gets an inclusion proof.
- **What does the server know?** Metadata, wrapped keys, policies, audit events. Never plaintext or unwrapped keys.
- **What does revocation not do?** It can't erase a copy already downloaded. It stops future access and key issuance.
- **Why a local Hardhat chain?** It's a deterministic EVM for the demo. The same contract deploys to Sepolia by config (`npm run deploy:sepolia`).
- **Public share links?** Documented as a design decision, deliberately not implemented to avoid leaking the file key in a URL.
- **Evidence of testing?** Hardhat contract tests (`npx hardhat test` in `blockchain/`), backend scripts in `backend/scripts/` (auth, crypto integrity, ABAC sharing, upload roundtrip, real blockchain anchoring), and pytest in `backend/tests`.

## 5. Troubleshooting

| Symptom | Fix |
|---|---|
| Script says Docker not running | Start Docker Desktop, wait for it, rerun |
| Page loads but login fails | Check `backend.log`; rerun `start-demo.bat` |
| Batch stays "prepared" | Worker not running: check `worker.log`; rerun the launcher |
| Port already in use | Run `stop-demo.bat` first, then start again |
| Cloud background missing | `frontend/public/assets/cloud-background.png` must exist |
| On-chain verification fails for an old batch | Stale batch from a previous chain session. Only possible after `-Keep`; start normally to get a clean slate |
| Everything weird | `stop-demo.bat`, then `start-demo.bat` (always a clean slate) |

Fallback if the live demo fails: all documents are in `docs/` (PRD, TRD, app flow, schema) and `docs/architecture/dropsafe_overall_architecture.html` is a diagram to walk through.
