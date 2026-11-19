# DropSafe

**Your Files. Your Control.**

DropSafe is a zero-knowledge encrypted file vault with attribute-based access control (ABAC) and a blockchain-anchored audit trail. Files are encrypted in the browser before upload, so the server only ever stores ciphertext. Every action is written to a hash-chained audit ledger, batched into Merkle trees, and the Merkle roots are anchored on an EVM blockchain, so history cannot be silently altered.

Built as a Cryptography and Network Security (CNS) capstone project.

## Live demo

| | |
|---|---|
| Web app | https://dropsafe-cns.pages.dev |
| API health | https://dropsafe-api-50047831488.development.catalystappsail.in/api/v1/health |
| Audit contract (Sepolia testnet) | [`0xcF21E2e72D327a2a698cB4F10271599995Def5b8`](https://sepolia.etherscan.io/address/0xcF21E2e72D327a2a698cB4F10271599995Def5b8) |

Use the one-click **Quick Demo Accounts** on the sign-in page (see [Demo accounts](#demo-accounts)). The first sign-in in a new browser takes a few seconds while the browser generates its encryption keys. The hosted version runs on free tiers: the backend scales to zero when idle and wakes on the next request, and anchoring on Sepolia takes about 40 seconds.

## Features

- **Client-side encryption:** per-file keys, wrapped per recipient (envelope encryption). The server never sees plaintext or unwrapped keys.
- **Sharing with ABAC:** per-file grants combined with attribute policies (department, clearance, project, contractor status). Default-deny.
- **Revocation and expiry:** remove a recipient's access or set an expiry date.
- **Tamper-evident audit log:** SHA-256 hash-chained events, verifiable from the UI.
- **Merkle batches and on-chain anchoring:** a background worker anchors batch roots in a Solidity contract. The UI verifies inclusion proofs against the chain.
- **Admin Console:** admins assign trusted attributes and roles. Each change re-signs the user's credential and is audited.

## How it works

1. **Upload:** the browser generates a random file key, encrypts the file (AES-GCM), wraps the key for the owner (RSA-OAEP), signs the upload (ECDSA P-256) and sends only ciphertext.
2. **Share:** the owner wraps the file key for the recipient. The server checks the file grant and the ABAC policy against the recipient's signed attribute credential before issuing access.
3. **Receive:** the recipient downloads the ciphertext and unwraps the key locally. After revocation the server refuses further access.
4. **Audit:** every event is chained to the previous one by hash. Batches of events form a Merkle tree, and the root is written to the `AuditAnchor` contract. Anyone can verify an event's inclusion proof against the on-chain root.

## Architecture

| Layer | Local demo | Hosted demo (free tiers) |
|---|---|---|
| Frontend | React 19, Vite, TypeScript, ethers (port 5173) | Cloudflare Pages |
| API proxy | Vite dev proxy | Cloudflare Pages Function (`/api` to backend) |
| Backend | FastAPI, SQLAlchemy (async), Alembic (port 8000) | Zoho Catalyst AppSail, Python 3.12 |
| Worker | Python outbox worker (batch anchoring) | Runs inside the same AppSail service |
| Database | PostgreSQL 16 in Docker | Neon Postgres |
| File storage | In-memory | Ciphertext in Postgres (`STORAGE_BACKEND=postgres`) |
| Blockchain | Hardhat local node (port 8545) | Sepolia testnet |

`docker-compose.yml` also starts Redis 7, which the application code does not use yet. It is provisioned for future caching and rate limiting.

## Prerequisites (local)

- Windows 10/11 with PowerShell
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (running)
- Python 3.13 and Node.js 20+

## Quick start (one click, local)

First-time setup:

```powershell
# Backend
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
cd ..

# Frontend and contracts
cd frontend;   npm install; cd ..
cd blockchain; npm install; cd ..
```

Copy `.env.example` to `.env` in the project root and in `backend/`. The defaults work for local development.

Then, with Docker Desktop running, double-click **`start-demo.bat`** (or run `.\start-demo.ps1`). It:

1. starts PostgreSQL and Redis in Docker,
2. starts a local Hardhat chain and deploys the `AuditAnchor` contract,
3. migrates and seeds the database with demo users,
4. starts the backend, the anchoring worker and the frontend,
5. opens http://localhost:5173.

Every start is a clean slate, because the local chain and file storage are in-memory. Use `start-demo.bat -Keep` to keep the existing database. Stop everything with **`stop-demo.bat`**. To share the running local demo through a free public `https` link, run `.\start-demo.ps1 -Public` (needs `cloudflared`).

Logs are written to `backend.log`, `worker.log`, `frontend.log` and `hardhat.log`.

## Demo accounts

Created by `backend/seed.py`. The sign-in page has one-click buttons for them. They exist on the live demo too, so treat everything uploaded there as public.

| User | Email | Password | Attributes |
|---|---|---|---|
| Alice (owner) | alice@dropsafe.local | AlicePass123! | engineering, clearance 2 |
| Bob (finance) | bob@dropsafe.local | BobPass123! | finance, clearance 1 |
| Charlie (contractor) | charlie@dropsafe.local | CharliePass123! | engineering, contractor |
| Admin | admin@dropsafe.local | AdminPass123! | admin role |

The walkthrough for presenting the project is in [DEMO-GUIDE.md](DEMO-GUIDE.md).

## Hosting for free

[DEPLOY.md](DEPLOY.md) documents the card-free hosted setup step by step: Neon for the database, a Sepolia wallet and contract for anchoring, the backend on Zoho Catalyst AppSail (no Docker needed) or a Hugging Face Space, and the frontend on Cloudflare Pages deployed with Wrangler.

## Testing

```powershell
# Backend: 86 tests (in-memory SQLite, safe to run while the demo is up)
cd backend
.\.venv\Scripts\python.exe -m pytest -q

# Smart contract: 5 tests
cd ..\blockchain
npx hardhat test
```

End-to-end checks against a running instance (local or hosted) live in `backend/scripts/`: client-side encryption round trip, sharing and ABAC with revocation, cryptographic integrity (tamper and wrong-key rejection), and real blockchain anchoring. Point the `BASE_URL` constant at the instance under test.

## Project structure

```
backend/      FastAPI app, ABAC policy engine, audit ledger, outbox worker, migrations
frontend/     React UI, client-side crypto (WebCrypto), on-chain verification, Pages Function proxy
blockchain/   Hardhat project and AuditAnchor.sol contract, Sepolia deploy helpers
deploy/       Catalyst bundling and deploy scripts, Hugging Face Space publisher
docs/         PRD, TRD, app flow, UI/UX, database schema, architecture diagrams
```

## Security notes

- This is a demonstration project. The local Hardhat accounts and their private keys are publicly known. Never use them with real funds.
- The hosted demo signs anchor transactions with a throwaway Sepolia test wallet whose key lives only in the host's private settings. Never reuse that key elsewhere.
- `.env` files and private deploy settings are git-ignored. Do not commit real secrets. Replace `SECRET_KEY` and signer keys before any real deployment.
- Demo account passwords are published in this README, so do not store anything sensitive on the hosted demo.
- Revocation stops future access and key issuance. It cannot erase a copy a recipient already downloaded.
- Public share links are intentionally not implemented, to avoid leaking file keys in URLs (see `docs/02-TRD.md`).

## Documentation

See the [`docs/`](docs/) folder: product requirements, technical design, app flow, UI/UX, backend schema, and architecture diagrams.
