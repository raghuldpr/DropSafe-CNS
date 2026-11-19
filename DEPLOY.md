# Hosting DropSafe for free (no credit card)

Architecture:

```
Browser ──► Cloudflare Pages (React app)
               └─ /api/*  ──► Pages Function (functions/api/[[path]].js) ──► Hugging Face Space (FastAPI + anchoring worker)
                                                                               ├─► Neon Postgres (data + encrypted file blobs)
                                                                               └─► Sepolia testnet (audit anchors)
Browser ──► public Sepolia RPC (reads the AuditAnchor contract directly for proof verification)
```

Free-tier limits change. Check each provider's current terms when you sign up. Nothing here needs a credit card as far as I know, but verify at signup.

Redis is not used by the application code, so it is not part of this stack.

## 0. Prerequisites

- GitHub account with this repository pushed (already done).
- Accounts: [Neon](https://neon.tech), [Hugging Face](https://huggingface.co), [Cloudflare](https://dash.cloudflare.com) (Pages).
- Node.js 20+ installed locally (for the contract deploy step).

## 1. Database: Neon

1. Create a Neon project (any region near you).
2. Copy the connection string. Rewrite the scheme for the psycopg driver and keep SSL:
   `postgresql+psycopg://USER:PASSWORD@ep-xxxx.neon.tech/neondb?sslmode=require`
3. Keep it for step 4. Tables are created automatically on first backend boot (Alembic migration), and the encrypted file blobs go into a `storage_objects` table (free tier is ~0.5 GB, plenty for a demo).

## 2. Blockchain: Sepolia testnet

Public testnet, so proofs verify from any visitor's browser and anchors survive restarts.

1. Generate a throwaway wallet:
   ```powershell
   cd blockchain
   npx hardhat run scripts/new-wallet.ts
   ```
   Save the address and private key. **Test wallet only. Never reuse it anywhere else.**
2. Fund the address with Sepolia test ETH from any free faucet (search "Sepolia faucet"). Faucets can be slow or rate-limited, so do this early. A small amount is enough for hundreds of anchors.
3. Deploy the contract:
   ```powershell
   $env:ANCHOR_SIGNER_PRIVATE_KEY = "0xYourTestWalletPrivateKey"
   $env:SEPOLIA_RPC_URL = "https://ethereum-sepolia-rpc.publicnode.com"
   npx hardhat run scripts/deploy.ts --network sepolia
   ```
   Note the printed `ANCHOR_CONTRACT_ADDRESS`.

Important: each batch number can be anchored on a contract only once. If you ever reset the Neon database (batch numbers restart at 1), deploy a **new** contract and update both the backend secret and the Pages variable below.

## 3. Backend: Hugging Face Space

1. On Hugging Face create a **new Space**: SDK **Docker**, blank template, hardware **CPU basic (free)**. Visibility public is simplest (the Pages Function calls it from the internet).
2. Space **Settings > Variables and secrets**: add everything from [`backend/.env.hosted.example`](backend/.env.hosted.example) as **Secrets** (especially `SECRET_KEY`, `DATABASE_URL`, `ANCHOR_SIGNER_PRIVATE_KEY`, `EVM_SIGNER_PRIVATE_KEY`).
   - Generate `SECRET_KEY`: `python -c "import secrets;print(secrets.token_urlsafe(48))"`
   - `ALLOWED_ORIGINS` = your Pages URL (step 4).
3. Publish the backend (needs a Hugging Face access token with **write** scope as the git password):
   ```powershell
   .\deploy\publish-space.ps1 -SpaceUrl https://huggingface.co/spaces/<your-user>/<your-space>
   ```
4. Open the Space's **Logs** tab. A healthy boot shows migrations, seeding, the worker starting, then Uvicorn on port 7860.
5. Check: `https://<your-user>-<your-space>.hf.space/api/v1/health` returns `"status":"healthy"` and `"database":"connected"`.

Notes:
- A free Space pauses after roughly two days without visitors and wakes on the next request (takes a minute or two). Open it the day before your exam, or add a free uptime pinger (for example UptimeRobot) hitting the health URL every 5 minutes.
- The Space runs the API and the anchoring worker in one container (`backend/start-hosted.sh`).

## 3b. Backend alternative: Zoho Catalyst AppSail (no Docker needed)

This is the route actually used for the capstone deployment. It uses Catalyst's managed Python 3.12 runtime, so no local Docker build is required.

One-time setup:
1. Create a Catalyst project named `DropSafe` in https://console.catalyst.zoho.com (free tier; no card needed at signup per Zoho's pricing page).
2. Log in with the CLI: `npx zcatalyst-cli login`.
3. Link the project folder (replace the IDs with yours from `npx zcatalyst-cli project:list`):
   ```powershell
   cd deploy\catalyst\project
   npx zcatalyst-cli init --org <org_id> --project <project_id>
   npx zcatalyst-cli appsail:add --name dropsafe-api --stack python_3_12 --source "<abs path to deploy\catalystuild>" --build "./" --command "sh start-catalyst.sh"
   ```
4. Keep your private values outside the repo in `%USERPROFILE%\.dropsafe\`: `neon.json` (`database_url`), `sepolia-wallet.json` (`private_key`, `contract_address`). `catalyst-env.json` (random `SECRET_KEY`, `allowed_origins`) is created on the first deploy.
5. Create the tables and demo users once from your PC (the same `SECRET_KEY` must be used so signed credentials verify):
   ```powershell
   cd backend
   $env:DATABASE_URL = "<neon string>"; $env:SECRET_KEY = "<secret_key from catalyst-env.json>"
   .\.venv\Scripts\python.exe -m alembic upgrade head
   .\.venv\Scripts\python.exe seed.py
   ```

Every deploy after that is one command:
```powershell
deploy\catalystuild-appsail.ps1   # only needed when dependencies change (deploy.ps1 runs it)
deploy\catalyst\deploy.ps1
```
`deploy.ps1` bundles the backend with Linux wheels, writes the environment variables into the git-ignored `buildpp-config.json`, and runs `catalyst deploy`. The service URL is printed by the CLI and shown in the console under AppSail.

Notes:
- Free-tier AppSail runtime is limited (about 900 GB-minutes per month); at 512 MB that is roughly 30 hours of running time, so check Zoho's current limits and the console's usage page.
- Use `catalyst deploy` (project-level) rather than `deploy appsail` with flags: only the former applies the environment variables from `app-config.json`.
- The Catalyst CLI has no log viewer; read logs in the console (AppSail > dropsafe-api > Logs).

## 4. Frontend: Cloudflare Pages

1. Cloudflare dashboard > **Workers & Pages > Create > Pages > Connect to Git**, pick the `DropSafe-CNS` repository.
2. Build settings:
   - **Root directory:** `frontend`
   - **Build command:** `npm run build`
   - **Build output directory:** `dist`
3. **Environment variables** (Production), from [`frontend/.env.production.example`](frontend/.env.production.example):
   - `VITE_API_BASE_URL` = `/api/v1`
   - `VITE_BLOCKCHAIN_RPC_URL` = `https://ethereum-sepolia-rpc.publicnode.com`
   - `VITE_CHAIN_ID` = `11155111`
   - `VITE_AUDIT_ANCHOR_CONTRACT_ADDRESS` = your Sepolia contract address
   - `BACKEND_URL` = `https://<your-user>-<your-space>.hf.space` (used by the proxy function at runtime)
4. Deploy. Then put the resulting `https://<project>.pages.dev` URL into the Space's `ALLOWED_ORIGINS` secret and restart the Space.

The folder `frontend/functions/api/` is picked up automatically and forwards `/api/*` to the backend, so the browser sees one origin (first-party cookies, no CORS).

## 5. Smoke test

1. Open the Pages URL, click **Alice (Owner)** on the sign-in page.
2. Upload a small file, open it, share it with Bob.
3. Audit Log > **Verify Hash Chain** > **Seal & Anchor Batch**. After about 30 seconds (Sepolia block time) the batch shows `anchored`. Open an event proof and check on-chain verification.
4. As Admin, open the Admin Console.

## Security notes for a public deployment

- The seeded demo accounts have publicly documented passwords. That is fine for a demo, but set `SEED_DEMO_DATA=false` (and delete those users) before storing anything you care about.
- The signer key is a throwaway Sepolia key held in the Space's secrets. Never commit it.
- Rotate `SECRET_KEY` by redeploying; it invalidates all sessions and changes the attribute-authority key derivation (existing credentials re-sign on next admin change).

## Alternative: share your laptop demo through a free tunnel

For the live exam, the safest option may be running locally and sharing it:

```powershell
winget install Cloudflare.cloudflared
.\start-demo.ps1 -Public
```

This prints a public `https://*.trycloudflare.com` URL that works only while your laptop is on. The local Hardhat chain is reachable through the same URL (`/rpc`), so on-chain verification works for remote viewers too. Anyone with the link can use the demo, so share it only with the people who need it. `stop-demo.bat` closes the tunnel.
