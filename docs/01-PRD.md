# DropSafe — Product Requirements Document

**Document:** `01-PRD.md`  
**Status:** Initial baseline — decisions consolidated from project discussions  
**Product tagline:** Your Files. Your Control.  
**Product type:** Secure cloud file-sharing web application  
**Primary objective:** Deliver a polished, usable file-sharing experience while demonstrating meaningful cryptographic security, attribute-based authorization, and tamper-evident audit verification.

---

## 1. App Name

**DropSafe**

DropSafe is a secure cloud file-sharing application that combines familiar file-management workflows with security controls that are visible and understandable to ordinary users.

## 2. Tagline

**Your Files. Your Control.**

Supporting brand message: **Encrypted files. Controlled access. Verifiable activity.**

---

## 3. Problem Statement

People need to store and share documents conveniently, but file-sharing workflows can make it difficult to understand who can access a file, what they are allowed to do, and whether important activity records have been altered.

For a security-focused capstone, a further challenge is demonstrating that security controls are part of the working product rather than merely claims in a report.

DropSafe addresses these needs by combining a familiar file-management experience with client-side encryption, policy-based access decisions, explicit sharing and revocation workflows, and verifiable audit commitments.

### Problems to address

- Users need a simple way to upload, organize, download, and share files.
- Owners need meaningful control over which recipients can access a file and which actions they may perform.
- Access decisions should use trusted attributes as well as file-specific permissions.
- Users and evaluators need understandable records of important security events.
- Audit records should be tamper-evident, with blockchain anchoring used to verify commitments rather than to store files or secrets.
- Security messaging must explain limitations honestly, especially around revocation and downloaded copies.

---

## 4. Proposed Solution

Build DropSafe as a responsive web application with a premium, minimal interface. The public landing and upload experience may use atmospheric cloud imagery and restrained glassmorphism. The authenticated workspace should prioritize clarity, whitespace, file-management efficiency, and consistent security status indicators.

Users can create accounts, upload files that are encrypted in their browser before cloud storage, manage files, and share them with registered users or through protected share links. The application evaluates access policies on the server. Important events are recorded in an audit system, and batches of audit records can be anchored to a blockchain so their commitments can later be verified.

The product should make routine tasks easy while allowing users to inspect more detailed security information when needed.

### Core product principles

1. **Simple by default:** Everyday file actions should not require users to understand cryptographic internals.
2. **Security enforced, not decorative:** Hiding a UI control is not authorization; protected operations must be checked by the backend.
3. **Progressive disclosure:** Show concise security states first, with detailed policy and audit information available on demand.
4. **Honest status:** Never display success or verification claims without corresponding confirmed results.
5. **Privacy-aware auditability:** Keep file contents, passwords, and secret keys out of public audit data and blockchain transactions.
6. **Achievable delivery:** Build and test the full core workflow before adding convenience features or advanced polish.

---

## 5. Core Value Proposition

**DropSafe makes secure file sharing feel as straightforward as everyday cloud storage, while giving users clearer control over access and a way to verify audit commitments.**

Value by audience:

- **Individuals and students:** Convenient file storage and sharing with clearer privacy controls.
- **Teams and project groups:** Sharing governed by permissions and trusted user attributes.
- **Businesses and researchers:** A demonstrator for controlled access to sensitive documents.
- **Administrators:** A way to manage trusted user attributes and inspect access-related events.
- **Auditors and evaluators:** Tamper-evident records and verifiable blockchain-anchored commitments.

DropSafe is a capstone prototype, not a claim of production-grade compliance or a replacement for a professionally audited enterprise storage service.

---

## 6. Target User Personas

### Persona A — Individual file owner

**Goal:** Store files and share selected documents without making them broadly accessible.

**Needs:**
- Upload and retrieve files.
- See whether a file is private or shared.
- Choose recipients and permissions.
- Revoke future access when needed.

### Persona B — Recipient or collaborator

**Goal:** Access files shared with them without navigating complicated security settings.

**Needs:**
- Find files shared with them.
- Understand available actions.
- Receive clear explanations when access is unavailable.
- Download and decrypt files when authorized and appropriately provisioned with key material.

### Persona C — Administrator

**Goal:** Maintain trustworthy user attributes used in access decisions.

**Needs:**
- Manage users and their trusted attributes.
- Assign attributes such as department, role, project membership, or clearance where appropriate.
- Avoid accidentally granting privileged access by default.
- Review relevant changes.

### Persona D — Auditor or project evaluator

**Goal:** Inspect security events and verify audit commitments.

**Needs:**
- Filter and inspect audit records.
- Distinguish recorded events from anchored and verified commitments.
- Inspect verification results and supporting references.
- See clear failure, pending, and unavailable states.

---

## 7. Core Features — Must Have

The first release should prioritize the following features. Features that depend on blockchain infrastructure may be developed after the primary encrypted upload-and-sharing workflow is working, but they remain part of the capstone delivery objective.

### 7.1 Authentication and user accounts

**What it does:** Allows users to register, sign in, sign out, and access their own workspace.

**Why needed:** File ownership, recipient identity, and authorization require authenticated accounts.

**Who uses it:** All users; administrators have additional authorized capabilities.

**Expected behavior:**
- Validate registration and sign-in inputs.
- Provide clear loading, error, and success states.
- Prevent unauthenticated users from accessing protected workspace data.
- New accounts receive only safe default attributes and permissions.
- Do not disclose whether a particular email address is registered through overly revealing recovery or error messages.

**Acceptance criteria:**
- [ ] A user can register with valid details and sign in.
- [ ] Invalid credentials are rejected with a clear, non-sensitive message.
- [ ] Signing out ends the user's authenticated session according to the implemented session design.
- [ ] Protected endpoints reject unauthenticated requests.
- [ ] New accounts do not receive privileged attributes automatically.

### 7.2 File upload, listing, download, and deletion

**What it does:** Provides core cloud file-management operations.

**Why needed:** These are the foundation of the product's Dropbox-like experience.

**Who uses it:** Authenticated users, subject to file ownership and access rules.

**Expected behavior:**
- Users can upload, list, download, and delete files they own or are authorized to access.
- File metadata includes a stable identifier, name, size, owner, timestamps, version information where implemented, and encryption state.
- Downloads are available only after server-side authorization.
- Deletion requires confirmation where it is destructive.
- The interface shows loading, progress, failure, retry, and empty states.

**Acceptance criteria:**
- [ ] An authorized user can upload a supported file and find it in their file list.
- [ ] The owner can download and recover the original content through the authorized decryption flow.
- [ ] An unauthorized user cannot download or delete the file by changing a file identifier.
- [ ] A failed operation is not presented as successful.
- [ ] Deletion updates the visible file list and is enforced by the backend.

### 7.3 Client-side encryption and key handling

**What it does:** Encrypts file content in the user's browser before encrypted content is sent to cloud storage.

**Why needed:** It is a central security objective of DropSafe.

**Who uses it:** File owners and authorized recipients.

**Expected behavior:**
- The UI communicates that encryption occurs before upload.
- Upload completion is shown only after the required encryption and storage steps succeed.
- Recipients can decrypt only when they have the appropriate authorized key material.
- Key-protection and recovery screens explain the consequences of losing required key material.
- The UI never exposes secret keys in ordinary views or audit records.

**Acceptance criteria:**
- [ ] The uploaded object contains encrypted content rather than the original plaintext.
- [ ] A valid authorized recipient can decrypt a downloaded file and reproduce its original content.
- [ ] Modified ciphertext is rejected or reported as an integrity/decryption failure.
- [ ] Encryption failure prevents the app from reporting a successful secure upload.
- [ ] The interface does not claim that the server can recover a user's private key unless a real recovery mechanism exists.

### 7.4 Secure sharing with registered users and protected links

**What it does:** Lets an owner share a file with specific registered users and, when enabled, create a protected shareable link.

**Why needed:** Users need both direct collaboration and a convenient link-based sharing option.

**Who uses it:** File owners, invited recipients, and authorized administrators where applicable.

**Expected behavior:**
- Owners select recipients and the actions they may perform.
- Link sharing is a separate, explicit sharing mode.
- Protected links follow the configured requirements, such as recipient authentication, expiration, or a secret token, as implemented.
- A link does not silently bypass file authorization policies.
- The UI clearly shows whether access is direct-recipient sharing or link-based sharing.
- Only implemented permission types are displayed.

**Acceptance criteria:**
- [ ] An owner can share a file with an eligible registered user.
- [ ] An eligible recipient can retrieve the file only when both policy and file permissions allow it.
- [ ] A protected link enforces its configured access conditions.
- [ ] An expired, revoked, or invalid link is rejected.
- [ ] The UI never displays a share URL unless one has actually been created.

### 7.5 Combined permissions and Attribute-Based Access Control (ABAC)

**What it does:** Uses trusted user and resource attributes to determine eligibility, while file permissions determine which actions an eligible user may perform.

**Why needed:** This is a core differentiator and capstone security requirement.

**Who uses it:** File owners, recipients, and administrators.

**Expected behavior:**
- The server evaluates policies for each protected operation.
- The default decision is deny unless a valid policy and applicable permission allow the action.
- Policies can use approved attributes such as department, role, project membership, account status, or clearance where configured.
- The UI presents policies in understandable forms rather than requiring users to write code.
- Unauthorized requesters receive a generic denial; authorized owners or administrators may see more detailed explanations.
- Frontend visibility is never treated as the security boundary.

**Acceptance criteria:**
- [ ] An eligible user with the required file permission can perform the allowed action.
- [ ] A user who fails a required policy condition is denied even if they know the file identifier or URL.
- [ ] A user who satisfies attributes but lacks the required file permission is denied.
- [ ] Missing, invalid, or untrusted attributes do not grant access.
- [ ] Policy changes affect subsequent authorization decisions according to the defined policy-update behavior.

### 7.6 Administrator-managed user attributes

**What it does:** Provides a small administration interface for managing trusted attributes used in access decisions.

**Why needed:** ABAC is meaningful only if attributes come from an appropriately trusted source.

**Who uses it:** Authorized administrators.

**Expected behavior:**
- Administrators can view users and assign or update supported attributes.
- Privileged attributes are not self-assigned by ordinary users.
- Attribute changes are validated and audited.
- The interface clearly distinguishes account profile fields from trusted authorization attributes.

**Acceptance criteria:**
- [ ] An authorized administrator can update supported attributes.
- [ ] An ordinary user cannot modify their own trusted authorization attributes.
- [ ] Attribute changes are reflected in subsequent policy evaluations.
- [ ] Unauthorized administrative requests are rejected by the backend.
- [ ] Attribute changes produce audit events.

### 7.7 Access revocation and key-version behavior

**What it does:** Lets an owner remove a recipient's future authorized access and supports stronger protection through key rotation and re-encryption when implemented.

**Why needed:** Sharing control is incomplete without a way to withdraw access.

**Who uses it:** File owners and appropriately authorized administrators.

**Expected behavior:**
- Revoking a recipient blocks future authorized retrieval through DropSafe once the change takes effect.
- The UI explains that revocation cannot erase copies or plaintext already downloaded.
- Where stronger post-revocation confidentiality is required, the application can create a new document version using a new key and grant that key only to eligible recipients.
- The UI distinguishes access revocation from cryptographic re-keying.

**Acceptance criteria:**
- [ ] A revoked recipient cannot retrieve the file through protected DropSafe endpoints after revocation takes effect.
- [ ] Revocation is recorded in the audit system.
- [ ] The confirmation UI explains the limitation of previously downloaded copies.
- [ ] If key rotation is offered, the new version uses new key material and only eligible recipients receive access to it.
- [ ] The interface does not claim that already downloaded plaintext has been erased.

### 7.8 Audit log and integrity verification

**What it does:** Records important file and security events and provides a way to inspect audit integrity.

**Why needed:** Users and evaluators need evidence of key application events and a way to detect certain forms of tampering.

**Who uses it:** Authorized users, file owners, administrators, and auditors according to access policy.

**Expected behavior:**
- Record important events such as upload, share, access grant, revocation, policy update, download, and version creation when those actions occur.
- Keep secret keys, passwords, plaintext file contents, and other unnecessary sensitive data out of audit records.
- Distinguish events recorded in the database from events included in an anchored batch and events whose proofs have been verified.
- Show pending, verified, failed, and unavailable states as appropriate.

**Acceptance criteria:**
- [ ] Relevant operations generate the expected audit records.
- [ ] Audit records can be checked for modification using the implemented integrity mechanism.
- [ ] A tampered record or proof causes verification to fail rather than show success.
- [ ] An unavailable blockchain RPC endpoint is shown as unavailable/pending and does not falsely mark a record verified.
- [ ] File upload, download, and authorization do not depend on immediate blockchain availability.

### 7.9 Blockchain-backed audit anchoring

**What it does:** Anchors commitments to batches of audit records on a blockchain and lets the application verify that an expected commitment matches the anchored data.

**Why needed:** It demonstrates the blockchain-auditing objective of the capstone without placing file contents or secrets on-chain.

**Who uses it:** Auditors, administrators, and project evaluators.

**Expected behavior:**
- Audit records are canonicalized before hashing.
- Batches are committed using an integrity structure such as a Merkle root.
- The anchoring system records transaction references and supports retry or pending states.
- The UI explains what was verified and what the proof does not establish.
- Blockchain failure does not prevent ordinary authorized file operations.

**Acceptance criteria:**
- [ ] A batch commitment can be anchored in the configured development or test environment.
- [ ] A record included in the batch can be verified against the stored proof and anchored commitment.
- [ ] A changed record or invalid proof fails verification.
- [ ] Transaction references are shown only when available.
- [ ] The UI does not claim blockchain proves an event was truthful or that no events were omitted.

### 7.10 Responsive and accessible interface

**What it does:** Provides a consistent experience on desktop, tablet, and mobile.

**Why needed:** The application must be practical to use and suitable for a portfolio demonstration.

**Who uses it:** All users.

**Expected behavior:**
- The landing page has a distinctive atmospheric upload experience.
- The authenticated workspace uses a clean, minimal file-management layout.
- File tables adapt to smaller screens.
- All essential actions are keyboard accessible.
- Reduced-motion preferences are respected.
- Loading, empty, error, and success states are designed for all major workflows.

**Acceptance criteria:**
- [ ] Core workflows remain usable at small mobile, tablet, and desktop viewport sizes.
- [ ] Focus indicators and accessible labels are present for interactive controls.
- [ ] Important status information is not conveyed by color alone.
- [ ] Reduced-motion mode avoids nonessential movement.
- [ ] No core workflow depends solely on hover.

---

## 8. Nice-to-Have Features

These features should follow the complete core workflow and should not delay it.

| Feature | Description | Suggested priority |
|---|---|---|
| Folders | Create and organize files in folders | After core workflow |
| Search and filters | Find files by name, type, date, owner, or sharing state | After core workflow |
| Starred files | Mark frequently used files | After core workflow |
| Recent files | Quick access to recently used files | After core workflow |
| File version history | View and retrieve earlier versions | Later phase |
| Recycle bin and restore | Restore deleted files within a defined retention period | Later phase |
| Notifications | Notify users of sharing or access changes | Later phase |
| Dark mode | Optional dark theme for the workspace | Later phase |
| Advanced audit filters | Filter by actor, event, date, or verification status | Later phase |
| Storage analytics | Detailed storage trends and breakdowns | Later phase |
| Team workspaces | Shared team-level file spaces | Later phase |

Features should be moved into the MVP only if time permits and the main security workflow remains complete and tested.

---

## 9. Out of Scope

The first version will not attempt to deliver:

- A full replacement for Dropbox, Google Drive, or enterprise document management systems.
- Native iOS or Android applications.
- Real-time collaborative document editing.
- Offline synchronization across devices.
- Automatic synchronization of local folders.
- A public anonymous file drop with no access controls.
- Arbitrary custom cryptographic algorithms.
- A claim of formal security certification or independent security audit.
- A claim that blockchain proves the truth of events or guarantees that every event was recorded.
- Remote deletion of files or plaintext already downloaded by recipients.
- Enterprise single sign-on or complex organization-wide provisioning.
- Unlimited storage or production-grade service-level guarantees.
- File preview for every file type.
- Guaranteed zero-cost operation regardless of external provider policies.

---

## 10. User Stories

### Account and workspace

- As a user, I want to create an account so that I can maintain my own file workspace.
- As a user, I want to sign in securely so that my files and settings are protected.
- As a user, I want to see my files in one place so that I can manage them efficiently.

### Upload and encryption

- As a file owner, I want my file encrypted before upload so that cloud storage receives encrypted content.
- As a user, I want to see encryption and upload progress so that I understand what the application is doing.
- As a user, I want clear error and retry options so that I can recover from failed uploads.

### Sharing and access control

- As an owner, I want to share with selected users so that access is limited to intended recipients.
- As an owner, I want to create a protected share link so that I can share conveniently while retaining configured access conditions.
- As an owner, I want to set permissions and access policies so that recipients can perform only permitted actions.
- As a recipient, I want to see files shared with me so that I can find authorized content.
- As an owner, I want to revoke access so that future retrieval can be blocked when collaboration ends.

### Administration

- As an administrator, I want to manage trusted attributes so that access decisions use approved user information.
- As an administrator, I want changes to authorization attributes audited so that important changes are reviewable.

### Auditing

- As an authorized user, I want to inspect file activity so that I can understand relevant actions.
- As an auditor, I want to verify audit commitments so that certain changes to recorded data can be detected.
- As an evaluator, I want to demonstrate tamper detection so that the capstone's security claims can be tested.

### Settings and recovery

- As a user, I want to understand how my encryption keys are protected so that I can make informed recovery decisions.
- As a user, I want clear warnings about key loss so that I understand the consequences before changing key settings.

---

## 11. Functional Requirements

Requirements are grouped by domain. These define externally observable behavior, not implementation details.

### FR-01 — Account access

- Users must be able to register, sign in, and sign out.
- Protected resources must require authentication.
- Administrative operations must require administrative authorization.
- Registration must not grant privileged authorization attributes.

### FR-02 — File management

- Users must be able to upload and list files they own.
- Users must be able to download files when authorized.
- Users must be able to delete files when authorized.
- File metadata and content access must be protected by server-side authorization.
- The UI must show operation state and recoverable errors.

### FR-03 — Encryption

- File content must be encrypted in the browser before cloud upload.
- The application must support authorized decryption by users who possess the appropriate key material.
- Integrity failures must be surfaced as errors.
- The application must not expose secret key material through normal UI or audit views.

### FR-04 — Sharing

- Owners must be able to share files with registered users.
- The product must support protected share links in the MVP, subject to configured authentication and access conditions.
- Sharing must not bypass applicable policies or file permissions.
- Only implemented actions may be offered as permissions.

### FR-05 — Authorization

- The application must evaluate trusted attributes and file-specific permissions on protected operations.
- Authorization must default to deny.
- Missing or invalid attributes must not grant access.
- Changing a UI control must not be sufficient to grant access.

### FR-06 — Attribute administration

- Authorized administrators must be able to manage supported user attributes.
- Ordinary users must not be able to self-assign trusted authorization attributes.
- Attribute updates must be validated and recorded.

### FR-07 — Revocation

- Owners must be able to revoke a recipient's future access through DropSafe.
- The UI must communicate that revocation cannot erase previously downloaded copies.
- If key rotation is implemented, the UI must clearly distinguish it from permission revocation.

### FR-08 — Audit records

- Relevant security and file operations must create audit records.
- Audit records must exclude passwords, private keys, document keys, and plaintext file contents.
- The UI must distinguish recorded, pending, anchored, and verified states.

### FR-09 — Blockchain verification

- The system must support anchoring audit batch commitments in a configured test environment.
- The system must validate the relevant commitment/proof before displaying a verified state.
- Verification failures and service unavailability must be clearly distinguished.
- Blockchain availability must not be required for routine file authorization and transfer.

### FR-10 — Responsive interface

- Core workflows must be usable on desktop, tablet, and mobile.
- The interface must provide loading, empty, error, and success states.
- Keyboard focus and accessible labels must be provided for core controls.
- Reduced-motion preferences must be respected.

### FR-11 — Protected share links

- Link-based sharing must have explicit access conditions.
- Invalid, expired, or revoked links must be rejected.
- A link must not bypass authentication or ABAC conditions when those are required by its configuration.
- Link creation and revocation must be auditable.

### FR-12 — Search and organization

This is a post-MVP requirement unless core delivery is complete early:
- Users should be able to search their accessible files by name.
- Folder, starred, and advanced filter behavior may be added in a later iteration.

---

## 12. Non-Functional Requirements

### Security

- Enforce authorization on the server for every protected file, sharing, policy, and administrative operation.
- Protect against insecure direct object reference (IDOR) by checking the caller's access to each requested resource.
- Use established cryptographic primitives and vetted libraries; do not invent cryptographic algorithms.
- Avoid logging secrets or plaintext file contents.
- Treat browser-side script injection as a significant risk because malicious scripts could access plaintext or key material available to the page.
- Ensure cryptographic integrity failures are not silently ignored.
- Use secure transport for deployed environments.
- Keep privileged configuration and signing secrets out of client bundles and version control.

### Privacy

- Collect only metadata required for the product.
- Do not place files, passwords, or secret keys on-chain.
- Avoid revealing detailed policy conditions to unauthorized requesters.
- Document what metadata is stored and what appears in audit records.

### Reliability

- A failed upload, share, revoke, or verification operation must not be presented as successful.
- Retry behavior must avoid inconsistent duplicate records where possible.
- Blockchain or RPC downtime must not block normal authorized file operations.
- Audit anchoring should support pending status and retry.

### Performance

- Common workspace screens should remain responsive with a practical capstone-scale file collection.
- Upload progress should reflect actual transfer progress when measurable.
- Large-file handling should avoid unnecessarily loading the entire file into memory when the implementation supports chunking.
- Background effects should not prevent users from operating the interface.

### Accessibility and usability

- Core workflows must be keyboard operable.
- Focus indicators and accessible labels must be present.
- Status must not be communicated through color alone.
- Reduced-motion preferences must be supported.
- Error messages should state what happened and, where safe, what the user can do next.

### Maintainability

- Requirements and user-visible behavior should be documented.
- Security-critical behavior should have automated tests.
- The application should support local development and a reproducible demonstration setup.
- UI components and interaction patterns should remain consistent across screens.

---

## 13. Success Metrics

The MVP is successful when the following outcomes can be demonstrated.

### Core workflow

- [ ] A user can register and authenticate.
- [ ] A file is encrypted before its content is uploaded.
- [ ] An authorized owner can upload, list, download, decrypt, and delete their file.
- [ ] A file can be shared with an eligible registered recipient.
- [ ] A protected share link enforces its configured access conditions.
- [ ] A recipient without required attributes or permissions is denied.
- [ ] Revocation blocks future authorized retrieval through DropSafe.
- [ ] The owner can inspect the resulting audit events.

### Cryptographic and audit demonstrations

- [ ] A ciphertext integrity or decryption failure is detected.
- [ ] Unauthorized resource access is rejected, including attempts to use another file's identifier.
- [ ] A changed audit record or invalid proof fails verification.
- [ ] A valid audit commitment can be verified against a blockchain-anchored batch.
- [ ] The UI distinguishes pending or unavailable verification from verified status.

### UX and delivery

- [ ] Core workflows work at mobile, tablet, and desktop widths.
- [ ] The application includes loading, empty, error, and success states for major workflows.
- [ ] A new developer can follow the setup documentation and run the local demonstration.
- [ ] The project includes a report and demo scenario explaining design choices, limitations, and tested security properties.
- [ ] The initial implementation stays within the intended minimal-cost budget, subject to provider account and free-tier requirements.

### Suggested evaluation measures

For the project demo, record:
- Number of core workflow tests passing.
- Number of authorization-negative tests passing.
- Successful and failed audit verification test cases.
- Upload/decryption results for representative small and large files.
- Setup steps required for a clean local run.

Do not claim production security based solely on these demonstrations; an independent security review would be required for stronger assurance.

---

## 14. Assumptions and Constraints

### Assumptions

- DropSafe is initially a web application.
- The main objective is a complete, demonstrable capstone and portfolio-quality prototype.
- The primary user experience should resemble familiar cloud file management.
- Security features must be real and testable rather than decorative.
- The initial design uses a monochrome visual identity with atmospheric effects limited to appropriate screens.
- Protected share links are included, but their precise access rules must be documented in the product UI and implementation.
- Blockchain is used for audit commitments, not file storage or access decisions.

### Constraints

- **Budget:** Target ₹0. External providers may require account verification, impose free-tier limits, pause inactive resources, or change their policies.
- **Scope:** The application must prioritize a working end-to-end security workflow over a large collection of partially implemented features.
- **Browser environment:** Client-side cryptography depends on a secure browser context and careful handling of page scripts and key material.
- **Key loss:** If required private key material and recovery options are lost, encrypted files may become unrecoverable.
- **Revocation:** Revocation cannot erase plaintext or copies already downloaded.
- **Blockchain semantics:** An anchored commitment supports integrity/timestamp evidence for the committed data, but does not establish that an underlying event was truthful or that all events were captured.
- **Production readiness:** The capstone is not automatically production-ready or independently security-audited.

---

## 15. Open Questions

These decisions should be resolved during detailed design or implementation planning. They do not prevent the initial PRD from being used as a baseline.

1. **Protected share-link rules:** Will links always require recipient sign-in, or can the owner enable a time-limited bearer link? What expiration limits will be allowed?
2. **Permission model:** Which exact file actions will be supported in the MVP (for example, view/download), and will editing be limited to metadata?
3. **Revocation depth:** Will the MVP implement permission revocation only, or also re-encryption into a new version with a rotated key?
4. **File limits:** What maximum file size and supported file types will be used for the first demonstration?
5. **Recovery model:** Which key recovery/export process will be supported, and what happens if the user loses both the passphrase and recovery material?
6. **Audit scope:** Which read/download events must be recorded, and what metadata is necessary without collecting excessive personal information?
7. **Blockchain environment:** Which test network or local chain will be used for development and demonstration, and how will RPC/faucet limitations be handled?
8. **Account roles:** What minimum roles are required (ordinary user, administrator, auditor), and can one person hold more than one role?
9. **Retention and deletion:** Are deleted files immediately removed from object storage, or is a recycle-bin retention period required?
10. **Deployment:** Will the capstone be demonstrated locally, hosted temporarily, or both?

---

## MVP Delivery Order

To reduce integration risk, build in this order:

1. Authentication, user records, and safe default attributes.
2. File metadata and protected object-storage operations.
3. Browser-side encryption and authorized decryption.
4. Authenticated recipient key directory and key wrapping.
5. Recipient sharing, protected links, and combined permission/ABAC checks.
6. Revocation and auditable policy changes.
7. Audit integrity checks and event-detail screens.
8. Batch commitments, blockchain anchoring, and proof verification.
9. Responsive UI refinement, accessibility checks, and security testing.
10. Project documentation, reproducible setup, and demonstration script.

**Release gate:** Do not treat the MVP as complete until the encrypted upload-to-authorized-download workflow, denial of unauthorized access, revocation behavior, and audit-tamper detection have been demonstrated end to end.

---

## PRD Change Control

This document is the initial product baseline. If implementation reveals a conflict or an important requirement changes, update this document explicitly rather than silently changing the scope. Keep product requirements separate from technical architecture and implementation instructions.
