# DropSafe

**Your Files. Your Control.**

DropSafe is a zero-knowledge encrypted file vault with attribute-based access control (ABAC) and a blockchain-anchored audit trail. Files are encrypted in the browser before upload, so the server only stores ciphertext. Every action is written to a hash-chained audit ledger, batched into Merkle trees, and the Merkle roots are anchored on an EVM blockchain so history cannot be silently altered.

Built as a Cryptography and Network Security (CNS) capstone project.

## Features

- **Client-side encryption:** per-file keys, wrapped per recipient (envelope encryption). The server never sees plaintext or unwrapped keys.
- **Sharing with ABAC:** per-file grants combined with attribute policies (department, clearance, project, contractor status). Default-deny.
- **Revocation and expiry:** remove a recipient's access or set an expiry date.
- **Tamper-evident audit log:** SHA-256 hash-chained events, verifiable from the UI.
- **Merkle batches and on-chain anchoring:** a background worker anchors batch roots in a Solidity contract. The UI verifies inclusion proofs against the chain.
- **Admin Console:** admins assign trusted attributes and roles. Each change re-signs the user's credential and is audited.

## Architecture

| Layer | Technology | Port |
|---|---|---|
| Frontend | React 19, Vite, TypeScript, ethers | 5173 |
| Backend | FastAPI, SQLAlchemy (async), Alembic | 8000 |
| Database | PostgreSQL 16 (Docker) | 5432 |
| Cache | Redis 7 (Docker) | 6379 |
| Worker | Python outbox worker (batch anchoring) | none |
| Blockchain | Hardhat local node, `AuditAnchor.sol` | 8545 |

## Prerequisites

- Windows 10/11 with PowerShell
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (running)
- Python 3.13 and Node.js 20+

## Quick start (one click)

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

Every start is a clean slate, because the local chain and file storage are in-memory. Use `start-demo.bat -Keep` to keep the existing database. Stop everything with **`stop-demo.bat`**. To share the running demo through a free public `https` link, run `.\start-demo.ps1 -Public` (needs `cloudflared`).

Logs are written to `backend.log`, `worker.log`, `frontend.log` and `hardhat.log`.

## Demo accounts

These are local development accounts created by `backend/seed.py`. The sign-in page has one-click buttons for them.

| User | Email | Password | Attributes |
|---|---|---|---|
| Alice (owner) | alice@dropsafe.local | AlicePass123! | engineering, clearance 2 |
| Bob (finance) | bob@dropsafe.local | BobPass123! | finance, clearance 1 |
| Charlie (contractor) | charlie@dropsafe.local | CharliePass123! | engineering, contractor |
| Admin | admin@dropsafe.local | AdminPass123! | admin role |

The walkthrough for presenting the project is in [DEMO-GUIDE.md](DEMO-GUIDE.md).

## Hosting for free

A card-free hosted setup (Cloudflare Pages, Hugging Face Spaces, Neon Postgres, Sepolia testnet) is documented step by step in [DEPLOY.md](DEPLOY.md).

## Running tests

```powershell
# Backend (uses in-memory SQLite, safe to run while the demo is up)
cd backend
.\.venv\Scripts\python.exe -m pytest -q

# Smart contract
cd ..\blockchain
npx hardhat test
```

## Project structure

```
backend/      FastAPI app, ABAC policy engine, audit ledger, outbox worker, migrations
frontend/     React UI, client-side crypto (WebCrypto), on-chain verification
blockchain/   Hardhat project and AuditAnchor.sol contract
docs/         PRD, TRD, app flow, UI/UX, database schema, architecture diagrams
```

## Security notes

- Everything here is for local development and demonstration. The Hardhat accounts and their private keys are publicly known. Never use them with real funds or on a public network.
- `.env` files are git-ignored. Do not commit real secrets. Replace `SECRET_KEY` and signer keys before any non-local deployment.
- Default file storage is in-memory for the demo. Configure an S3-compatible backend for anything persistent.
- Public share links are intentionally not implemented, to avoid leaking file keys in URLs (see `docs/02-TRD.md`).

## Documentation

See the [`docs/`](docs/) folder: product requirements, technical design, app flow, UI/UX, backend schema, and architecture diagrams.
