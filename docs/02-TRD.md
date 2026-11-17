# DropSafe — Technical Requirements Document

**Document:** `02-TRD.md`  
**Status:** Initial technical baseline  
**Product tagline:** Your Files. Your Control.  
**Related document:** `01-PRD.md`  
**Purpose:** Establish a consistent, practical architecture for the DropSafe cryptography capstone. This document specifies technologies and boundaries; it does not contain application code.

---

## Decision Status Legend

- **Confirmed** — established in the project discussions or PRD.
- **Recommended baseline** — selected here as the practical default for implementation.
- **Open decision** — needs a deliberate choice before the relevant implementation phase; do not silently substitute another design.

## 1. Technical Architecture Overview

### 1.1 System overview

DropSafe is a responsive web application for encrypted file storage, policy-controlled sharing, and verifiable security auditing. The browser encrypts and decrypts file content. The backend authenticates users, evaluates authorization, coordinates metadata and storage access, and records audit events. Ciphertext is stored in object storage. Audit commitments are batched and anchored to a local development chain and, if available, an Ethereum test network.

```text
React + TypeScript browser
  ├─ Web Crypto API: AES-GCM, RSA-OAEP, ECDSA, PBKDF2
  ├─ HTTPS REST API calls
  └─ Direct ciphertext transfer using short-lived presigned URLs
          │
          ▼
FastAPI backend ─────────────── PostgreSQL
  ├─ Authentication/JWT          ├─ Users and public-key directory
  ├─ ABAC + file permissions      ├─ Document metadata and versions
  ├─ Sharing/link authorization   ├─ Wrapped per-recipient keys
  ├─ Presigned URL issuance       ├─ Policies, shares, and audit outbox
  └─ Audit APIs                   └─ Audit batches and anchor records
          │
          ├──────── Object storage (Cloudflare R2): ciphertext only
          │
          └──────── Audit worker → Merkle batches → Solidity contract
                                           ├─ Hardhat local chain
                                           └─ Optional Ethereum Sepolia
```

### 1.2 Trust boundaries

| Component | Trusted responsibilities | Must not do |
|---|---|---|
| Browser/client | Encrypt/decrypt content; generate and use user keys; verify signatures and current document version; wrap document keys for eligible recipients | Trust an API response alone when it would add an unauthorized recipient; expose plaintext keys to application logs |
| FastAPI backend | Authentication, policy enforcement, metadata, share state, signed-key directory responses, storage authorization, audit coordination | Receive plaintext file contents or unwrapped document keys during normal operation |
| PostgreSQL | Durable structured metadata, authorization state, wrapped keys, audit/outbox state | Store plaintext file contents or plaintext document keys |
| Object storage | Store encrypted file chunks/manifests | Be treated as the authorization authority; store plaintext files |
| Blockchain | Publicly anchor a commitment to a defined audit batch | Store files, secrets, personal data, or full audit records; be treated as proof that events were truthful or complete |
| Admin/attribute authority | Assign and sign trusted attributes and key bindings | Allow ordinary users to self-assign privileged attributes |

### 1.3 Core data flow

1. The user authenticates with the API.
2. The browser generates a random document data-encryption key (DEK), encrypts the file with AES-256-GCM, and creates a canonical manifest for its encrypted chunks.
3. The browser uploads ciphertext to object storage using short-lived, narrowly scoped presigned URLs. The API receives metadata and the encrypted manifest, not file plaintext.
4. For each recipient, the browser obtains a signed public-key/attribute binding, independently checks the signed attributes and eligibility information, and wraps the DEK using that recipient's RSA-OAEP public key.
5. The backend checks both ABAC eligibility and file-specific permissions for each protected operation. The browser must never treat a server-provided recipient list by itself as sufficient authorization evidence.
6. Audit events are written to a durable database/outbox. A worker builds deterministic Merkle batches and anchors their roots. Verification compares event inclusion proofs with the stored/anchored commitment.
7. A recipient downloads ciphertext only after authorization, unwraps their DEK locally, verifies the manifest/signature/version, and decrypts in the browser.

### 1.4 MVP architecture principles

- Prefer a modular monolith (one FastAPI service) over microservices.
- No Kubernetes, message broker, separate identity provider, or separate key-management service is required for the MVP.
- Blockchain is an audit-verification enhancement; core file authorization must continue to work if the chain or RPC endpoint is unavailable.
- Complete the end-to-end encrypted upload → sharing → authorized download → decryption flow before building advanced dashboard features.
- The PRD remains the source of product scope. This TRD may specify implementation details but must not silently remove product requirements.

## 2. Frontend Framework

**Recommended baseline: React + TypeScript + Vite.**

| Technology | Responsibility and connection | Cost/limitations |
|---|---|---|
| React | Component-based UI for authentication, file workspace, upload flow, sharing, policy, and audit screens | Open source; no runtime license fee |
| TypeScript | Static type checking for UI state and API contracts; reduces accidental data-shape mismatches | Open source |
| Vite | Local development server and production frontend build | Open source; production assets can be hosted as static files |
| React Router | Client-side routes and guarded page layouts | Open source; guards are UX only—backend endpoints must independently authorize every request |
| Fetch API or a small typed wrapper | Calls the FastAPI REST API | Native browser capability; do not add a large data-fetching framework unless the app needs it |
| Web Crypto API | Native cryptographic primitives in secure browser contexts | No library license fee; browser support and secure-context requirements apply |

**Frontend responsibilities**
- Present the interface and validate input for usability.
- Keep file plaintext and raw DEKs in memory only as long as necessary.
- Encrypt before upload and decrypt only after successful authorization and integrity verification.
- Verify signed public-key/attribute bindings, owner signatures, chunk authentication, manifest integrity, and current version.
- Never place secrets, access tokens, decrypted content, or private keys in localStorage, URLs, analytics, or logs.

**State management:** Start with React state/context for local UI state and a small API client for server state. Add a dedicated state library only if real complexity justifies it.

**Build rule:** UI route protection is not security enforcement. All sensitive actions require backend authorization.

## 3. Programming Language

| Layer | Language | Reason |
|---|---|---|
| Frontend | TypeScript | Types for API responses, crypto metadata, and UI states |
| Backend and worker | Python 3.12+ (use one supported version consistently) | Accessible for a student capstone; strong FastAPI, testing, database, and Web3 tooling |
| Smart contracts and blockchain tooling | Solidity 0.8.x and TypeScript for Hardhat scripts/tests | Standard Ethereum contract ecosystem |
| Database | PostgreSQL SQL | Relational constraints and transactions for authorization/audit state |
| Documentation | Markdown | Version-controlled, readable project documentation |

Pin exact versions in lockfiles and dependency manifests at implementation time. Do not let an AI coding agent casually upgrade major versions mid-project.

## 4. Styling Framework

**Recommended baseline: Tailwind CSS with a small reusable component layer.**

- **Why:** Efficient implementation of a responsive, monochrome workspace without maintaining a large bespoke stylesheet.
- **Responsibility:** Layout, spacing, typography, responsive breakpoints, focus states, and visual tokens.
- **Connection:** React components use shared design tokens and reusable controls; styling has no authorization or cryptographic responsibility.
- **Cost:** Open source. Build-time tooling only.
- **Guidelines:** Use accessible contrast, visible keyboard focus, semantic HTML, reduced-motion preferences, and explicit loading/empty/error/success states. Keep the workspace minimal and consistent with the PRD; do not add animation libraries unless necessary.

A component library is optional, not mandatory. Avoid mixing several UI libraries. If a component library is chosen during implementation, document it and keep the visual system consistent.

## 5. Backend Framework or Runtime

**Recommended baseline: Python + FastAPI, run as a modular monolith.**

| Dependency | Responsibility | Notes/cost |
|---|---|---|
| FastAPI | REST API, request validation, dependency injection, OpenAPI docs | Open source |
| Uvicorn | ASGI development/runtime server | Open source; production process setup depends on hosting |
| Pydantic | Validate request/response schemas and configuration | Open source |
| SQLAlchemy 2.x | Database access and transaction boundaries | Open source |
| Alembic | Versioned database schema migrations | Open source |
| Psycopg 3 | PostgreSQL driver | Open source |
| Argon2 library | Password hashing | Open source; use Argon2id with appropriate parameters |
| PyJWT or a maintained JWT library | Token creation and verification | Open source; pin and audit dependency |
| Web3.py | Interact with local/test Ethereum JSON-RPC endpoints | Open source; RPC service may impose quotas or require a paid plan |

Keep modules separated by responsibility (authentication, users/keys, files, sharing, policies, audit, storage). Do not split into microservices for the capstone.

**Backend must never accept a plaintext DEK as part of a normal API contract.** It may store recipient-wrapped DEKs, encrypted manifests, signatures, ciphertext digests, and metadata. Any endpoint accepting file bytes should be avoided in favor of direct browser-to-object-storage ciphertext uploads unless a clearly documented local fallback is necessary.

## 6. Database and Data Storage

### 6.1 PostgreSQL

**Purpose:** Structured, durable state for users, public-key registrations, documents, versions, encrypted manifests, wrapped recipient keys, sharing, policies, audit events, Merkle batches, and blockchain anchors.

Recommended local development uses Docker Compose and a local PostgreSQL container. A hosted PostgreSQL provider is optional; Supabase can be considered for its database hosting, but use only one primary PostgreSQL instance.

**Cost/limits:** Self-hosted locally is free apart from the developer's machine. Hosted providers may have storage, compute, inactivity, backup, or payment-method restrictions. Verify current plans before committing to a provider.

### 6.2 Object storage

**Recommended baseline: Cloudflare R2**, with a local S3-compatible option (such as MinIO) only if needed for offline development.

- Store ciphertext chunks and encrypted manifests only.
- Store object keys and object metadata in PostgreSQL; do not store file contents in PostgreSQL.
- Use short-lived presigned URLs scoped to one object and one method.
- Validate object ownership and current authorization before issuing a URL.
- Configure bucket CORS for the deployed frontend origin, restrict methods/headers, and never expose bucket credentials to the browser.
- Use non-guessable object identifiers; never treat an unguessable identifier as authorization.

**Cost/limits:** R2 pricing and free allowances may change; storage, operations, and internet egress policies depend on the current plan. Account/API credentials are required. Do not promise zero cost or unlimited uploads.

### 6.3 Data model (logical)

| Entity | Important fields (illustrative, not final schema) |
|---|---|
| User | id, email, password_hash, status, role, created_at |
| UserKey | user_id, key_type, public_key, key_fingerprint, key_version, status |
| AttributeBinding | user_id, attributes, issuer, issued_at, signature, binding_version |
| Document | id, owner_id, current_version, status, created_at |
| DocumentVersion | document_id, version, encrypted_manifest, ciphertext_digest, owner_signature, key_version, created_at |
| ObjectChunk | document_version_id, chunk_index, object_key, ciphertext_size, ciphertext_digest |
| WrappedDocumentKey | document_version_id, recipient_user_id or link_id, wrapped_dek, recipient_key_version, status |
| Share | id, document_id, recipient/link reference, permissions, policy reference, expiry, revoked_at |
| ABACPolicy | id, policy_version, canonical_policy, status, created_by |
| AuditEvent | id/sequence, actor, action, resource reference, result, timestamp, canonical_payload, previous_hash, event_hash |
| AuditBatch | batch_id, sequence range, merkle_root, status, created_at |
| BlockchainAnchor | batch_id, chain_id, contract_address, transaction_hash, block_number, anchor_status |
| OutboxJob | id, job_type, payload reference, attempts, next_attempt_at, status |

Schema constraints, unique indexes, foreign keys, and transaction rules must be specified during database implementation. Never store plaintext file content or raw DEKs in any table.

### 6.4 File format and cryptographic metadata

- Content encryption: AES-256-GCM through Web Crypto API.
- Large-file support: chunked encryption; each chunk must use a unique nonce under a given key.
- Bind document ID, version, chunk index, and final-chunk status through authenticated additional data (AAD), using a documented, canonical encoding.
- Store a manifest containing the algorithm/version, chunk ordering, nonce data, sizes, digests, and document/version identifiers. Do not include secret material.
- Key wrapping: RSA-OAEP with SHA-256, using an appropriately generated RSA-3072 recipient encryption key.
- Signatures: ECDSA P-256 for document commitments and authenticated key/attribute bindings where specified.
- Use separate encryption and signing key pairs.
- Private keys must be encrypted/protected before persistence or export. Browser PBKDF2 via Web Crypto is the MVP-compatible baseline; select and document iteration parameters. Do not store an unprotected private key in browser storage.
- Owner signature should cover a canonical commitment that binds document ID, version, owner, manifest/ciphertext digest, and relevant key version.
- Recipients must verify signatures against an authenticated owner signing key and reject malformed, stale, or mismatched versions.
- Hashes and signatures require one precise byte encoding and canonical serialization; JSON objects must not be hashed from ad hoc property ordering.

**Important distinction:** This design is browser-side encryption plus RSA key wrapping and ABAC. It is **not** Ciphertext-Policy Attribute-Based Encryption (CP-ABE). Do not claim CP-ABE unless it is separately designed and implemented.

## 7. Authentication and Authorization

### 7.1 Authentication

- Email/password registration and login for the MVP.
- Hash passwords on the server using Argon2id; never encrypt or store plaintext passwords.
- Issue short-lived access tokens. Use a carefully designed refresh/session approach rather than long-lived bearer tokens.
- Recommended browser handling: tokens in Secure, HttpOnly, SameSite cookies where deployment architecture supports it, with CSRF protection for cookie-authenticated state-changing requests. If bearer tokens are used instead, keep access tokens in memory and document the refresh design; do not place long-lived tokens in localStorage.
- Enforce HTTPS in hosted deployments.
- Rate-limit login, registration, password reset (if present), key-registration, and share-link guessing attempts.
- Return generic login and share-denial messages where revealing whether an account/resource exists could leak information.
- Account recovery must not silently bypass the user's private-key protection. If key recovery is not implemented, document that loss of key material can make encrypted files unrecoverable.

### 7.2 Authorization: ABAC + file permissions

Authorization is a two-part decision:

1. **ABAC eligibility:** trusted subject attributes, resource attributes, action, and relevant environment context are evaluated against a versioned policy.
2. **File-specific permission:** the share/owner grant must permit the requested operation (for example, view/download or reshare, if supported).

Both checks must pass. Default deny. Enforce checks server-side on every sensitive endpoint, including metadata, presigned URL issuance, share mutation, deletion, policy administration, and audit detail retrieval. Do not rely on hidden buttons or frontend route guards.

- Parse policies into a validated, bounded JSON policy structure/AST; do not execute arbitrary policy strings or Python expressions.
- Assign safe default attributes to new accounts. Only authorized administrators/attribute authorities can assign privileged attributes.
- Signed key/attribute bindings must bind user ID, public key fingerprint, attributes, issuer, and version. Protect the issuer signing key, and document rotation/compromise recovery.
- The owner client must independently verify the signed recipient identity/key/attributes and re-check eligibility before wrapping the DEK. A compromised backend must not be able to silently add an ineligible recipient just by altering the recipient list.
- Admin, ordinary user, and any auditor roles must have explicit capabilities. Keep the role model minimal and test each role.
- Use object-level ownership checks on every document/share/version ID to prevent IDOR/BOLA vulnerabilities.

### 7.3 Protected shareable links

Protected links are part of the PRD. Use random, high-entropy link tokens, store only a hash of the token server-side, apply expiry and revocation, rate-limit attempts, and scope each link to a specific document/version and permitted actions. If link access includes a decryption capability, design carefully so the secret is not exposed to server logs, referrers, analytics, or accidental URL collection. Do not put a raw DEK into a query string. Final link-secret/key-delivery details are an **open security design decision** to resolve before implementing public links.

### 7.4 Revocation and versions

- Revocation blocks future API authorization and future presigned URL issuance; use short URL lifetimes.
- Revocation cannot erase plaintext or keys a recipient already downloaded.
- Stronger revocation requires rotating the DEK and re-encrypting into a new document version, then rewrapping keys for remaining recipients.
- Bind signatures/manifests to the version and key version. Clients must reject stale/rollback versions when the current signed version is available.
- Define the expected behavior of already-issued URLs and in-flight downloads in tests and documentation.

## 8. API Architecture

**Style:** Versioned REST API over HTTPS, JSON for control-plane metadata, binary ciphertext transfer directly to object storage.

Recommended prefix: `/api/v1`.

| Area | Example endpoints (illustrative) | Responsibility |
|---|---|---|
| Authentication | `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, `POST /auth/refresh` | Session lifecycle and account creation |
| Profile/key directory | `GET /users/me`, `GET /users/{id}/key-binding`, `POST /users/me/keys` | Own profile, public key and signed attribute binding |
| Documents | `POST /documents`, `GET /documents`, `GET /documents/{id}`, `DELETE /documents/{id}` | Metadata and owner-visible document operations |
| Upload | `POST /documents/{id}/upload-intents`, `POST /documents/{id}/versions` | Issue authorized upload details and finalize encrypted manifest/version |
| Download | `POST /documents/{id}/download-intents` | Re-check authorization and return short-lived read URL(s) |
| Sharing | `POST /documents/{id}/shares`, `GET /documents/{id}/shares`, `DELETE /shares/{id}` | Create/list/revoke recipient grants |
| Protected links | `POST /documents/{id}/links`, `POST /links/{token}/redeem`, `DELETE /links/{id}` | Create, validate, expire, and revoke links |
| Policies/admin | `/policies`, `/admin/attributes`, `/admin/users/{id}/attributes` | Policy and trusted-attribute administration |
| Audit | `GET /audit/events`, `GET /audit/events/{id}`, `POST /audit/verify` | Event inspection and integrity/proof verification |
| Anchoring | `GET /audit/batches`, `GET /audit/batches/{id}/proof` | Batch status, Merkle proofs, anchor information |

Endpoints are illustrative, not an immutable contract. Final request/response schemas, error codes, pagination, and authorization matrix must be documented in OpenAPI and tests.

### API rules

- Use Pydantic request/response models and reject unexpected fields where appropriate.
- Never return password hashes, private keys, raw link secrets, object-storage credentials, or internal exception traces.
- Use consistent errors: stable machine-readable error code, safe user-facing message, request/correlation ID.
- Add pagination to lists and enforce bounded request sizes.
- Use idempotency or deduplication for upload finalization and audit-worker processing where retries could create duplicate state.
- Avoid accepting arbitrary object-storage keys from clients without verifying document ownership and expected prefix.
- The backend's authorization result must be based on current database state, not client-supplied role/attribute values.

## 9. Third-Party APIs and Services

| Service/API | Purpose | Required credentials | Cost/limits and fallback |
|---|---|---|---|
| Cloudflare R2 API | Store encrypted objects and issue presigned access URLs | R2 account, bucket, access key/secret stored only server-side | Pricing, operations, and free allowances can change; local S3-compatible storage can be used for development |
| Ethereum JSON-RPC endpoint (Sepolia) | Submit and inspect audit-root transactions on a public testnet | RPC URL/API key may be required depending on provider | Quotas, availability, faucet/test-ETH limits, and provider terms vary; keep local Hardhat as the reliable demo fallback |
| Local Hardhat node | Local EVM for contract development and repeatable tests | No external API key | Local-only chain; resets may erase chain state |
| PostgreSQL | Durable application state | Database connection string | Local Docker is free; hosted provider limits and billing vary |
| Optional hosted frontend | Serve built React assets | Deployment account; environment configuration | Free tiers and quotas change; local frontend is sufficient for development |
| Optional hosted backend/database | Demonstration access outside the developer machine | Provider account, secrets, database URL | May sleep, impose quotas, or require payment method; do not assume always-free |
| Optional Supabase | Hosted PostgreSQL if selected | Project credentials/connection details | Use as a hosting choice, not a second database; confirm current limits and network configuration |

**Not required for MVP:** paid identity provider, paid analytics, email delivery provider (unless email verification/password reset is added), managed KMS, enterprise SIEM, or a separate queue service.

No service may be assumed free indefinitely. Review current pricing and quotas at the time of deployment.

## 10. Key Libraries and Dependencies

Use the smallest dependency set that supports the PRD.

### Frontend
- `react`, `react-dom`, `typescript`, `vite`
- `react-router-dom`
- `tailwindcss` and its compatible build integration
- `vitest` and React Testing Library for component/unit tests
- `playwright` for end-to-end browser tests if environment permits
- Prefer native Web Crypto API over a cryptography package for the specified primitives

### Backend
- `fastapi`, `uvicorn`
- `pydantic` and settings support
- `sqlalchemy`, `alembic`, `psycopg`
- Maintained Argon2id password-hashing library
- Maintained JWT/session library as selected by the implementation
- `pytest`, HTTPX test client, and coverage tooling
- `web3` for EVM interactions
- Standard library hashing/HMAC utilities where appropriate

### Smart contracts
- Hardhat, Solidity compiler pinned to a compatible version, TypeScript tooling
- OpenZeppelin Contracts only if a relevant audited utility is needed; do not import unnecessary contract frameworks
- Contract unit tests and deployment scripts

### Dependency policy
- Pin versions and commit lockfiles.
- Avoid unmaintained packages and duplicate libraries with overlapping responsibilities.
- Run dependency vulnerability checks periodically.
- Keep secrets out of source control; commit `.env.example` with names/placeholders only.
- Do not use a cryptographic library as a substitute for a documented protocol design or security tests.

## 11. File and Folder Structure

Proposed repository root: `dropsafe/`.

```text
dropsafe/
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── app/                 # App shell, routes, providers
│   │   ├── components/          # Shared UI components
│   │   ├── features/
│   │   │   ├── auth/
│   │   │   ├── files/
│   │   │   ├── sharing/
│   │   │   ├── access-control/
│   │   │   ├── audit/
│   │   │   └── admin/
│   │   ├── crypto/              # Encryption, chunking, wrapping, signatures
│   │   ├── lib/                 # API client, schemas, utilities
│   │   ├── hooks/
│   │   ├── styles/
│   │   ├── types/
│   │   ├── main.tsx
│   │   └── vite-env.d.ts
│   ├── tests/
│   ├── package.json
│   └── vite.config.ts
├── backend/
│   ├── app/
│   │   ├── api/v1/              # Routers by domain
│   │   ├── core/                # Config, logging, security primitives
│   │   ├── db/                  # Session, base, migrations integration
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/             # Business logic
│   │   ├── repositories/         # Data access (use where it adds clarity)
│   │   ├── policies/             # Validated ABAC AST/evaluator
│   │   ├── storage/              # R2/S3-compatible adapter
│   │   ├── audit/                # Hash chain, canonicalization, Merkle logic
│   │   ├── worker/               # Outbox processing and anchor retries
│   │   └── main.py
│   ├── migrations/
│   ├── tests/
│   ├── requirements.txt or pyproject.toml
│   └── Dockerfile
├── blockchain/
│   ├── contracts/
│   │   └── AuditAnchor.sol
│   ├── scripts/
│   ├── test/
│   ├── hardhat.config.ts
│   └── package.json
├── database/
│   ├── init.sql                  # Optional local bootstrap only
│   └── seed.sql                  # Non-production demo data only
├── docs/
│   ├── 01-PRD.md
│   ├── 02-TRD.md
│   ├── architecture.md
│   ├── threat-model.md
│   ├── api-documentation.md
│   └── demo-runbook.md
├── scripts/
├── .env.example
├── .gitignore
├── docker-compose.yml
├── README.md
└── package.json                 # Optional root workspace scripts
```

Do not duplicate schema ownership between Alembic and manually applied SQL. Use migrations as the canonical production schema history; SQL bootstrap files, if retained, must be limited to local initialization/seed data.

## 12. Naming Conventions

| Area | Convention | Example |
|---|---|---|
| Python modules/functions/variables | `snake_case` | `create_upload_intent` |
| Python classes/Pydantic schemas | `PascalCase` | `DocumentVersionResponse` |
| TypeScript variables/functions | `camelCase` | `verifyOwnerSignature` |
| React components/types | `PascalCase` | `FileCard`, `ShareRequest` |
| Constants | `UPPER_SNAKE_CASE` | `MAX_CHUNK_BYTES` |
| API routes | lowercase plural nouns; consistent resource nesting | `/api/v1/documents/{document_id}/shares` |
| Database tables/columns | lowercase `snake_case` | `document_versions`, `created_at` |
| Environment variables | `UPPER_SNAKE_CASE` | `DATABASE_URL` |
| Solidity contracts/functions | `PascalCase` for contracts, `camelCase` for functions | `AuditAnchor`, `anchorBatch` |
| Tests | `test_*.py`, `*.test.ts` / `*.spec.ts` | `test_revoked_share_denied.py` |
| Cryptographic values | Explicit suffixes/types | `ciphertext_digest`, `wrapped_dek`, `key_version` |

Use UUIDs or similarly non-guessable IDs for external resource identifiers, but never rely on identifier secrecy in place of authorization.

## 13. Environment Variables

Names only are listed here. Values must be provided locally or by the deployment platform and must never be committed.

### Backend
- `APP_ENV`
- `APP_NAME`
- `API_V1_PREFIX`
- `DATABASE_URL`
- `JWT_SIGNING_KEY`
- `JWT_ISSUER`
- `JWT_AUDIENCE`
- `ACCESS_TOKEN_TTL_SECONDS`
- `REFRESH_TOKEN_TTL_SECONDS`
- `COOKIE_SECURE`
- `COOKIE_SAMESITE`
- `CSRF_SECRET`
- `CORS_ALLOWED_ORIGINS`
- `PASSWORD_HASH_MEMORY_COST`
- `PASSWORD_HASH_TIME_COST`
- `PASSWORD_HASH_PARALLELISM`
- `R2_ACCOUNT_ID`
- `R2_BUCKET_NAME`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`
- `R2_ENDPOINT_URL`
- `R2_PRESIGNED_URL_TTL_SECONDS`
- `ATTRIBUTE_ISSUER_SIGNING_KEY`
- `AUDIT_BATCH_SIZE`
- `AUDIT_WORKER_POLL_SECONDS`
- `AUDIT_ANCHOR_MODE`
- `EVM_RPC_URL`
- `EVM_CHAIN_ID`
- `AUDIT_ANCHOR_CONTRACT_ADDRESS`
- `EVM_SIGNER_PRIVATE_KEY`
- `LOG_LEVEL`
- `SENTRY_DSN` (optional)

### Frontend build-time configuration
- `VITE_API_BASE_URL`
- `VITE_APP_NAME`

Only public, non-secret configuration belongs in `VITE_*` variables because frontend build variables are visible to users. Never put database, R2, JWT-signing, attribute-issuer, or blockchain signer secrets in frontend variables.

### Blockchain tooling
- `PRIVATE_KEY` (local/test deployment account only; never a mainnet key)
- `SEPOLIA_RPC_URL`
- `ETHERSCAN_API_KEY` (optional, only if contract verification is used)

Keep `.env` files out of Git. Use `.env.example` with variable names and explanatory placeholders, not real values. For local demos, use throwaway keys and test funds only. Do not reuse production secrets.

## 14. Hosting and Deployment

### 14.1 Development baseline

- Docker Compose for PostgreSQL and any required local object-storage emulator.
- Frontend: Vite development server.
- Backend: Uvicorn with FastAPI.
- Blockchain: local Hardhat node.
- Worker: separate process/container using the same backend codebase and configuration.
- `.env` files for local secrets, excluded from version control.

### 14.2 Demonstration deployment options

**Preferred reliable capstone path:** demonstrate locally with Docker Compose, local database, local storage emulator or configured R2, and Hardhat. This keeps the core demo independent of public RPC and cloud availability.

**Optional hosted demo:** static frontend hosting plus a hosted FastAPI process, PostgreSQL, and R2. Choose providers only after checking current free-tier quotas, sleep behavior, region availability, payment requirements, and egress/operation charges. Do not treat a free tier as a guaranteed production SLA.

**Optional public audit anchor:** deploy the contract to Sepolia using test funds and a testnet RPC provider. Keep local-chain tests as the source of repeatable correctness. Testnet availability, faucets, RPC quotas, and explorers are external dependencies.

### 14.3 Deployment controls

- Enforce HTTPS and correct secure-cookie settings in hosted environments.
- Restrict CORS to known frontend origins.
- Use separate development/test/demo configuration.
- Apply database migrations as a controlled deployment step.
- Do not expose database ports or object-storage credentials publicly.
- Use health/readiness endpoints without revealing secrets.
- Back up database state when using a hosted demo; understand that local chain resets require redeployment/re-anchoring.
- Set explicit maximum upload size, chunk size, and request limits in configuration.

## 15. Security Requirements

### 15.1 Cryptographic correctness

- Use Web Crypto API primitives as specified; do not invent custom ciphers or modes.
- Generate cryptographically random DEKs and nonces using secure randomness.
- Never reuse an AES-GCM nonce with the same key. Chunk index/version must be bound through AAD and manifest validation.
- Validate nonce lengths, tag handling, chunk count/order, manifest fields, and size limits before decryption.
- Keep plaintext and DEKs out of API requests, database records, logs, crash reports, URLs, and telemetry.
- Separate encryption and signing keys.
- Verify signed recipient identity/public-key/attribute bindings before wrapping keys; verify owner signatures before trusting manifests.
- Use canonical byte encoding for signed/hashed data. Document domain separation and exact signed fields.
- Use PBKDF2 only as the browser-compatible key-protection baseline with an explicit iteration count and salt. The server uses Argon2id for passwords; these are different use cases.
- Avoid claiming formal end-to-end security without threat-model review and adversarial tests.

### 15.2 Web and API security

- HTTPS in hosted deployment; secure cookie attributes and CSRF protection if cookies are used.
- Strict CORS allowlist.
- Content Security Policy (CSP), appropriate security headers, and minimal third-party scripts to reduce XSS risk.
- Treat XSS as a critical risk: injected JavaScript can access plaintext and browser-held keys while the app is open.
- Validate and normalize inputs; enforce upload size and content-type policy.
- Rate-limit authentication, link redemption, key registration, and sensitive admin operations.
- Protect against IDOR/BOLA by checking owner/share/policy authorization for every object-level action.
- Avoid leaking resource existence through denial responses where relevant.
- No secrets in logs or frontend bundles.
- Dependency pinning and vulnerability checks.
- Never use untrusted user data as HTML without safe escaping.
- Protect admin endpoints with explicit role and policy checks, not just UI hiding.

### 15.3 Audit and blockchain security

- Define one canonical serialization for audit event hashes and Merkle leaves.
- Use a hash chain in the database to make ordinary edits/deletions detectable within the retained chain.
- Build deterministic Merkle batches and persist leaf ordering, batch sequence, root, and proof material or enough data to recompute it.
- The contract should store minimal commitments, with events for anchor transactions; never store file contents, DEKs, user secrets, or unnecessary personal information on-chain.
- Worker retries must be idempotent. Use a transactional outbox so an audit event is not lost merely because the chain/RPC is down.
- Record chain ID, contract address, transaction hash, block number, and anchor status.
- Verify proofs against the anchored root and correct chain/contract.
- Provide a pending/failed anchor state; do not imply an event is blockchain-verified before confirmation.
- A blockchain commitment proves that a commitment was anchored by a time, not that its event was truthful, that all events were captured, or that the database was never compromised before anchoring. Document omissions and trust assumptions.

### 15.4 Revocation limitations

Revocation stops future authorization and future URL issuance. It cannot revoke plaintext or keys already copied by a recipient, and a previously issued presigned URL may work until it expires. The UI and report must communicate these limits. For stronger revocation, rotate the key and create a newly encrypted version.

### 15.5 Security test gate

Before claiming MVP security, test:
- Unauthenticated access to every protected endpoint.
- Cross-user object ID substitution and owner/share isolation.
- Denial after share revocation and policy changes.
- Expired/revoked link handling and brute-force rate limits.
- Tampered ciphertext, nonce, manifest, signatures, chunk ordering, and version rollback.
- Recipient public-key substitution and invalid/forged attribute binding.
- Audit event modification, deletion, reordering, duplicate processing, and failed/retried anchoring.
- Leakage of tokens/keys/plaintext through logs, URLs, browser storage, and errors.

## 16. Performance Requirements

These are **initial engineering targets**, not guarantees. Benchmark on the actual demo hardware and revise with evidence.

| Area | Initial target/constraint | Design response |
|---|---|---|
| Typical API response | p95 under 500 ms for metadata/authz endpoints in a local demo, excluding storage transfer and blockchain RPC | Indexed queries, bounded responses, no synchronous chain calls in normal request path |
| Dashboard | Usable first render within 3 seconds on a typical development machine/network | Lazy-load audit/admin areas; avoid oversized dependencies |
| File uploads/downloads | Stream/chunk work so the browser does not need multiple full-file copies in memory | Chunked AES-GCM and direct object-storage transfer |
| Upload limit | Configurable; choose a conservative initial demo limit (e.g. 100 MB) and test it | Explicit UI/backend/storage limits; increase only after measuring |
| Chunk size | Configurable; select and benchmark an initial chunk size during implementation | Ensure each chunk has a unique nonce and authenticated index |
| Audit verification | Verify a batch proof locally without a chain RPC on each page render | Cache public anchor metadata; query chain for explicit refresh/verification |
| Database | Support paginated list endpoints and indexes on owner/resource/status/timestamp fields | Avoid unbounded list queries |
| Worker | Retry transient RPC failures with backoff and expose queue age/status | Outbox, idempotency, bounded batch sizes |

Performance requirements must never weaken authorization, cryptographic verification, or nonce uniqueness. Do not promise a concurrent-user capacity until it is load-tested.

## 17. Error Logging and Monitoring

### 17.1 Logging

- Use structured application logs with timestamp, severity, environment, request ID, and safe event category.
- Never log passwords, access/refresh tokens, raw link tokens, private keys, DEKs, plaintext, or full presigned URLs.
- Redact sensitive query parameters and authorization headers.
- Record security-relevant outcomes (login failure category, authorization denial, share/revoke, signature failure, audit-batch failure) without exposing sensitive details.
- Return a correlation/request ID so a safe client error can be traced in server logs.

### 17.2 Monitoring

- MVP: Python logging, health endpoint, worker status, database connectivity checks, and test results.
- Optional: Sentry or equivalent for exceptions, only after configuring scrubbing and reviewing data collection. An external monitoring service may require an account, DSN, quotas, and paid upgrade.
- Monitor failed uploads, storage errors, failed authentication, policy denial counts, audit outbox age, anchor retries, and invalid proof/signature events.
- Avoid analytics that collect filenames, plaintext, link secrets, or user file contents.

## 18. Technical Constraints

1. Target a practical student-capstone implementation and a near-zero-cost development path, while acknowledging external services may require billing details or incur costs.
2. Browser-side cryptography is mandatory for file-content confidentiality from the backend in normal operation.
3. The backend remains authoritative for account/session state, policy decisions, share state, and storage URL issuance.
4. ABAC is combined with file-level permissions; neither check replaces the other.
5. Blockchain anchoring is for audit commitments, not file storage or primary authorization.
6. Core app operation must not depend on a public testnet being online.
7. Public links require an explicit threat-reviewed secret/key delivery design before implementation.
8. Key loss and account recovery behavior must be documented before a production claim.
9. Browser cryptography requires a secure context (HTTPS or localhost) and compatible browser APIs.
10. Do not claim CP-ABE, guaranteed revocation of downloaded copies, truthful/complete blockchain audit history, or production-grade assurance without implementation and evidence.

## 19. Development Environment Setup

### 19.1 Required tools

- Git and GitHub (or another Git remote).
- Node.js LTS and npm for frontend and Hardhat.
- Python 3.12+ and a virtual environment.
- Docker Desktop or Docker Engine with Compose.
- A supported browser with Web Crypto API.
- Optional: an Ethereum testnet RPC account and test ETH for Sepolia demonstration.
- Optional: R2 account/bucket for cloud object-storage demonstration.

### 19.2 Setup sequence

1. Clone the repository and copy `.env.example` to a local, ignored `.env`.
2. Install frontend dependencies using the committed lockfile.
3. Create a Python virtual environment and install pinned backend dependencies.
4. Start PostgreSQL (and any local object-storage emulator) using Docker Compose.
5. Apply Alembic migrations and seed only non-sensitive demo users/attributes.
6. Start the FastAPI backend and verify health/OpenAPI locally.
7. Start the Vite frontend with its API base URL pointing at the backend.
8. Start a local Hardhat node and deploy `AuditAnchor.sol` for contract tests/demo.
9. Start the audit worker separately and confirm outbox retries work while the chain is unavailable.
10. Run frontend unit tests, backend tests, contract tests, and end-to-end smoke tests.
11. Verify a complete workflow: register/login → upload encrypted file → share → authorized recipient download/decrypt → revoke → confirm denial → inspect audit event → verify Merkle proof/anchor.

### 19.3 Development hygiene

- Keep `.env`, database dumps containing user data, private keys, and real uploaded files out of Git.
- Use synthetic demo data and throwaway keys.
- Pin dependency versions and commit lockfiles.
- Make migrations reproducible.
- Add a short README for one-command startup where feasible.
- Document external credentials as optional steps; local tests should still run without Sepolia credentials.
- Do not place testnet private keys in CI logs or screenshots.

## 20. Technical Risks and Trade-offs

| Risk/trade-off | Impact | Mitigation/decision |
|---|---|---|
| Client-side cryptography is easy to implement incorrectly | Data loss or confidentiality/integrity failure | Use standard Web Crypto APIs, define formats precisely, test tampering and edge cases, and document limitations |
| XSS compromises plaintext and browser keys | Critical confidentiality risk | Strict CSP, minimal scripts/dependencies, output escaping, dependency review, short-lived sessions |
| Key loss or device change | User may permanently lose access to encrypted files | Define encrypted key backup/recovery or explicitly document unrecoverability for MVP; never create an insecure server-side plaintext-key escrow silently |
| Recipient key substitution | DEK may be wrapped to an attacker-controlled key | Signed key/attribute bindings, fingerprint display/verification, owner-side verification |
| ABAC complexity | Inconsistent or bypassable authorization | Small validated policy AST, default deny, centralized evaluator, authorization matrix and negative tests |
| Presigned URL remains usable after revocation until expiry | Short window of access remains | Short expiry, no new URLs after revocation, document limitation; proxy downloads only if stricter enforcement becomes necessary |
| Public share-link key distribution | URL leakage can expose access/decryption capability | Keep token and decryption secret separate where feasible; avoid query-string secrets, referrer leakage, analytics/logging; threat-review before release |
| Blockchain/RPC outage or faucet limits | Anchoring may be delayed or unavailable during demo | Local Hardhat fallback, durable outbox, retry/backoff, explicit pending state |
| Audit batching/ordering bugs | Incorrect proof or missed commitment | Canonical serialization, deterministic leaves, sequence numbers, reproducible tests and reconciliation |
| Cloud free-tier changes | Deployment becomes unavailable or unexpectedly costs money | Local-first demo, verify pricing and quotas, cap uploads and storage, avoid production data |
| Large-file memory pressure | Browser crash or slow upload | Chunk processing, avoid duplicate buffers, benchmark supported file size |
| Too much scope | Capstone may not reach a demonstrable secure workflow | Build sequentially; defer search/starred/version-history polish until core security flow works |
| JWT/cookie misconfiguration | Session theft or CSRF | Choose one documented session model, use secure attributes, CSRF protection where applicable, tests |
| Testnet data is not production-grade | Unstable demonstration or misleading trust claims | Treat Sepolia as optional evidence, preserve local tests, display chain/network and confirmation status |

### 20.1 Explicitly unresolved decisions

Resolve these before implementing the affected features. Do not let an AI coding agent make silent assumptions.

1. **Protected-link cryptographic design:** how a recipient obtains decryption capability without exposing a DEK in a query string or to the backend. Consider a fragment-based secret or a separately delivered password, but threat-review the complete flow and browser history/referrer behavior before selecting.
2. **Session model:** Secure HttpOnly cookie + CSRF protection versus short-lived in-memory bearer token plus refresh strategy. Choose one and apply consistently.
3. **Key recovery:** whether the MVP supports user-encrypted key backup, recovery codes, or documents key-loss unrecoverability.
4. **Attribute issuer signing key management:** local development storage, deployment secret storage, rotation, and compromise recovery.
5. **Object storage mode:** local S3-compatible storage for repeatability, R2 for cloud demo, or both behind one adapter.
6. **Blockchain mode:** local Hardhat only for baseline, Sepolia as optional demonstration, or both.
7. **Administrative roles:** exact capabilities for ordinary user, administrator/attribute issuer, and auditor.
8. **Deletion semantics:** immediate object deletion versus soft-delete/recycle-bin retention.
9. **Upload limits and chunk size:** set through measured tests on target hardware.
10. **Hosted deployment provider:** select only after reviewing current cost, quota, region, sleep, and credential requirements.

These are not reasons to pause unrelated development. Implement the unaffected local workflow first, then decide each item before its feature is built.

---

## Architecture decision summary

| Topic | Baseline decision | Status |
|---|---|---|
| Frontend | React + TypeScript + Vite | Confirmed/recommended |
| Styling | Tailwind CSS, minimal reusable components | Recommended |
| Backend | Python + FastAPI modular monolith | Confirmed/recommended |
| Database | PostgreSQL + SQLAlchemy + Alembic | Confirmed/recommended |
| Password hashing | Argon2id | Confirmed |
| Browser file encryption | Web Crypto API, AES-256-GCM chunking | Confirmed |
| Recipient key wrapping | RSA-OAEP-3072 | Confirmed |
| Signatures | ECDSA P-256 | Confirmed |
| Object storage | Cloudflare R2, optional local S3-compatible development adapter | Recommended; hosting mode open |
| Authorization | Server-side ABAC + file-specific permission, default deny | Confirmed |
| Audit integrity | Database hash chain + deterministic Merkle batches | Confirmed/recommended |
| Blockchain | Solidity `AuditAnchor`, Hardhat local, optional Sepolia via Web3.py | Confirmed/recommended |
| Worker | Python outbox/anchor worker | Recommended |
| Deployment | Local-first Docker Compose; hosted demo optional | Recommended |
| Cost | Target ₹0 for development, no guarantee of free hosted operation | Constraint |

## Change control for AI-assisted development

Before changing a technology, dependency family, API contract, cryptographic format, database schema, or trust boundary:

1. Identify the relevant TRD section and explain why a change is necessary.
2. Check consistency with `01-PRD.md`, especially security requirements.
3. Record the decision and its impact in this document or an architecture decision record.
4. Update tests, setup documentation, and environment-variable names together.
5. Never replace a cryptographic primitive, skip a verification step, or move plaintext/key handling to the backend merely to make an implementation easier.
