# DropSafe --- UI Design Specification

**Product:** DropSafe\
**Tagline:** Your Files. Your Control.\
**Document:** `design.md`\
**Purpose:** Source of truth for visual design and frontend UI planning\
**Status:** Design direction and requirements; not proof that features
are implemented

------------------------------------------------------------------------

## 1. Product Overview

DropSafe is a secure cloud file-sharing application designed around:

-   Client-side file encryption
-   Controlled file sharing
-   Attribute-Based Access Control (ABAC)
-   File versioning and access revocation
-   Readable audit history with blockchain-backed audit commitments

The interface must make these concepts understandable without turning
every screen into a technical monitoring console. Users should be able
to understand what is happening to their files, who can access them, and
what actions have occurred.

### Product promise

**Your Files. Your Control.**

Communicate control, clarity, and confidence. Avoid absolute or
unverifiable claims such as "unhackable," "100% secure," or
"military-grade security."

### Design principles

1.  **Brand before decoration:** Use the existing DropSafe logo and
    cloud artwork; do not invent a new identity.
2.  **Clarity before density:** Show the information needed for the
    current task, not every possible metric at once.
3.  **Security that users can understand:** Explain encryption, sharing,
    policy decisions, and audit status in plain language.
4.  **Quiet confidence:** Premium, restrained, atmospheric, and
    purposeful rather than neon or cyberpunk.
5.  **Consistent patterns:** Reuse typography, spacing, buttons, form
    controls, navigation, tables, status badges, and dialogs.
6.  **Honest status:** Show only states supported by actual application
    data. Distinguish pending, completed, failed, and unavailable
    operations.
7.  **Accessible by default:** Maintain readable contrast, keyboard
    navigation, visible focus, clear labels, and reduced-motion support.
8.  **Responsive design:** Support desktop first, then adapt layouts to
    tablet and mobile without hiding essential actions.

------------------------------------------------------------------------

## 2. Existing Visual Assets

The existing asset collection is located in the user's local folder:

`dropsafe-cloud-assets/DropSafe-Design-References/`

Use the current files; do not create replacement asset kits unless
explicitly requested.

### Primary references

  --------------------------------------------------------------------------
  Asset                                  Intended role
  -------------------------------------- -----------------------------------
  `01-Brand/dropsafe-logo.png`           Existing DropSafe brand mark and
                                         wordmark

  `02-Atmosphere/cloud-background.png`   Cinematic cloud artwork and
                                         atmospheric reference
  --------------------------------------------------------------------------

### Supporting references

  -----------------------------------------------------------------------------------
  Asset group                                     Intended role
  ----------------------------------------------- -----------------------------------
  `03-Background-Textures/`                       Subtle grain, vignette, and surface
                                                  treatments

  `04-Security-Icons/`                            Security-related interface icons

  `05-File-Icons/`                                File-type icons

  `06-Empty-State-Illustrations/`                 Empty, no-results, and
                                                  no-accessible-files states

  `07-Animations/Cloud/`                          Existing cloud-animation reference

  `07-Animations/Upload/`                         Existing upload-animation reference

  `08-Optional-Components/Toast-Notifications/`   Existing toast implementation
                                                  reference

  `09-App-Icons/`                                 Favicon and web-app icons
  -----------------------------------------------------------------------------------

### Asset-use rules

-   Preserve the original logo and cloud artwork.
-   Do not stretch, distort, or recolor the logo without an explicit
    design reason.
-   Use the cloud artwork as a hero/atmospheric feature on the public
    landing page.
-   Use a more restrained background treatment inside authenticated
    application screens so file information remains readable.
-   Keep decorative textures subtle; they must not reduce contrast or
    make text noisy.
-   Use supplied icons consistently. If Stitch cannot import SVG
    references, use the logo and cloud image first; SVGs can be
    integrated during implementation.
-   Do not treat HTML previews, CSS files, or React components as image
    references. They are implementation resources for later.
-   Respect reduced-motion preferences. Animation must never be required
    to understand status or complete a task.

------------------------------------------------------------------------

## 3. Visual Direction

### Overall character

The DropSafe interface should feel:

-   Premium
-   Minimal
-   Dark
-   Cinematic
-   Atmospheric
-   Trustworthy
-   Modern
-   Calm and technically capable

It must not look like a generic AI-generated SaaS dashboard or an
overloaded cybersecurity control room.

### Color system

Use these as initial design tokens. Tune exact values after reviewing
the reference artwork and the first Stitch result.

  --------------------------------------------------------------------------
  Token                      Suggested value         Use
  -------------------------- ----------------------- -----------------------
  `--color-canvas`           `#08090B`               Main page background

  `--color-surface`          `#101216`               Primary panels and
                                                     navigation

  `--color-surface-raised`   `#171A20`               Raised cards, menus,
                                                     dialogs

  `--color-surface-hover`    `#1D2129`               Hovered interactive
                                                     surfaces

  `--color-border`           `#292E37`               Subtle borders and
                                                     separators

  `--color-text-primary`     `#F4F5F7`               Main headings and
                                                     important text

  `--color-text-secondary`   `#B2B7C1`               Body copy and
                                                     supporting labels

  `--color-text-muted`       `#858C99`               Nonessential metadata;
                                                     use sparingly

  `--color-accent`           `#8CB8FF`               Primary interactive
                                                     accent

  `--color-accent-strong`    `#5D97F6`               Primary buttons and
                                                     selected states

  `--color-success`          `#65C995`               Successful operations

  `--color-warning`          `#E7B76A`               Warnings and pending
                                                     attention

  `--color-danger`           `#F07878`               Errors and destructive
                                                     actions

  `--color-focus`            `#A9CBFF`               Visible keyboard focus
  --------------------------------------------------------------------------

These are starting values, not immutable brand requirements. Keep accent
colors restrained. Do not use blue glow effects on every component.

### Gradients and effects

-   Prefer near-black solid surfaces.
-   Use a restrained cool-blue gradient only for a primary CTA or a
    small highlighted region if it improves hierarchy.
-   Use cloud lighting, vignette, and grain selectively.
-   Avoid multiple competing gradients, excessive bloom, glowing borders
    on every card, and glassmorphism everywhere.
-   Do not place small text over a detailed cloud image unless a
    sufficiently dark, calm region provides strong contrast.

### Typography

Use a modern sans-serif typeface. Suitable choices include Inter, Geist,
or a system sans-serif stack. Use one primary family unless there is a
clear reason to introduce another.

Suggested desktop scale:

  ------------------------------------------------------------------------
  Role                                Suggested size Notes
  --------------------- ---------------------------- ---------------------
  Hero headline                            56--72 px Responsive; short,
                                                     deliberate line
                                                     breaks

  Page title                               30--36 px Clear and prominent

  Section heading                          18--22 px Medium or semibold

  Body text                                15--17 px Comfortable reading
                                                     width

  Button text                              14--16 px Medium weight

  Table/file row text                      14--15 px Readable at normal
                                                     zoom

  Metadata                                 12--13 px Use sparingly; never
                                                     carry essential
                                                     meaning alone
  ------------------------------------------------------------------------

Typography rules:

-   Avoid tiny text and dense monospace labels.
-   Avoid arbitrary line breaks and narrow text containers.
-   Use comfortable line-height: approximately 1.45--1.7 for body text.
-   Do not shrink text to fit a crowded layout; simplify the content or
    change the layout instead.
-   Keep important labels and filenames on one line where practical,
    with deliberate truncation and a tooltip when needed.

### Spacing and shape

Use a consistent 4 px base spacing system with common steps such as 4,
8, 12, 16, 24, 32, 48, and 64 px.

Suggested shape rules:

-   Buttons and inputs: 8--12 px radius
-   Standard cards: 12--16 px radius
-   Large hero panels: 16--24 px radius when needed
-   Pills: full radius, used only for status/category labels
-   Borders: thin and low contrast
-   Shadows: subtle and purposeful, mainly for overlays and raised
    surfaces

Do not wrap every piece of content in its own card.

------------------------------------------------------------------------

## 4. Layout System and Navigation

### Public pages

Public pages use a slim top navigation, generous whitespace, and a
strong hero composition. The cloud artwork can be prominent here.

### Authenticated application shell

Desktop application layout:

-   Left sidebar: approximately 224--256 px wide
-   Top bar: approximately 64--76 px high
-   Main content: flexible width with a comfortable maximum reading
    width where appropriate
-   Main content padding: approximately 28--40 px on desktop
-   File tables and complex views may use more width than settings/forms

Sidebar navigation order:

1.  Overview
2.  My Files
3.  Shared with Me
4.  Shared by Me
5.  Access Policies
6.  Audit Log
7.  Settings

Shell rules:

-   Keep the existing DropSafe logo at the top.
-   Use a clear selected state for the current navigation item.
-   Use a slim, consistent icon style and readable labels.
-   Avoid numerous navigation badges and technical labels.
-   Top bar may include search, notifications, and account controls.
-   Keep "Upload files" prominent on file-oriented screens.
-   On small screens, collapse the sidebar into an accessible navigation
    drawer or compact navigation pattern.
-   Preserve page context and avoid unnecessary navigation resets.

------------------------------------------------------------------------

## 5. Screen Inventory and Requirements

Design and approve one screen at a time. Do not ask the design tool to
generate the entire application in one request.

### Screen 1 --- Public Landing Page

**Purpose:** Explain DropSafe and guide visitors to start or sign in.

**Content and hierarchy:**

1.  Slim navigation:
    -   Existing DropSafe logo
    -   Features
    -   Security
    -   Sign In
    -   Get Started
2.  Hero:
    -   Headline: **"Your Files. Your Control."**
    -   Supporting text: "Store, share, and manage your files with
        client-side encryption and access controls designed around you."
    -   Primary CTA: **Get Started**
    -   Secondary CTA: **Explore Security**
    -   Existing cinematic cloud artwork as the visual centerpiece
3.  Three concise product principles:
    -   Client-Side Encryption
    -   Controlled File Sharing
    -   Auditable Activity
4.  Short product explanation or feature section, only if the layout
    needs it.
5.  Minimal footer:
    -   DropSafe
    -   Privacy
    -   Security
    -   Documentation

**Visual requirements:**

-   The cloud artwork establishes the atmosphere.
-   The hero headline is prominent and readable.
-   Do not place an oversized dashboard mockup in the hero unless
    specifically requested later.
-   Do not fill the page with fake statistics, random technical
    identifiers, or decorative widgets.
-   Keep the page balanced and avoid excessive floating elements.
-   Explain product capabilities without claiming unverified security
    guarantees.

### Screen 2 --- Authentication

Create consistent Login, Register, and Account Recovery states.

**Login fields:** - Email address - Password - Show/hide password
control - Sign In - Link to registration - Link to account recovery

**Registration fields:** - Name, if required by the product model -
Email address - Password - Confirm password only if the selected UX
requires it - Clear password guidance - Create Account - Link to login

**Requirements:** - Simple forms with readable labels and errors. - Use
the DropSafe brand and a restrained atmospheric background. - Do not let
artwork compete with form controls. - Provide clear loading, success,
validation, and failure states. - Do not imply that email verification,
MFA, or recovery mechanisms exist until implemented. - Do not expose
secrets in error messages.

### Screen 3 --- Overview Dashboard

**Purpose:** Provide a calm summary of the user's workspace.

**Header:** - Title: "Overview" - Supporting text: "Your secure
workspace, all in one place." - Primary action: "Upload files" -
Optional secondary action: "Share a file"

**Summary row:** - Total files - Files shared with others - Recent
activity

Use only a small number of metrics. Avoid decorative charts unless they
answer a real user question.

**Main content:** - Recent files section, approximately five rows -
Compact recent activity section, approximately three events - Small
security summary for encryption, access control, and audit status

Sample filenames: - `Project-Proposal.pdf` - `Research-Notes.docx` -
`Product-Design.png` - `Budget-Overview.xlsx` - `Meeting-Recording.zip`

A file row may contain: - File icon - Filename - File size - Last
modified date - Encryption status - Overflow menu

**Requirements:** - Avoid a wall of cards. - Make the file list the
primary content. - Do not invent blockchain metrics, fake transaction
hashes, or meaningless identifiers. - Distinguish actual system state
from illustrative placeholder data. - Ensure table columns remain
aligned and readable.

### Screen 4 --- My Files

**Purpose:** Browse, search, filter, upload, and manage files.

Include: - Page title and concise helper text - Upload files action -
Search field - Useful filters (e.g., file type, ownership, or status if
supported) - File list/table - Empty state when there are no files -
Loading and error states - File row actions appropriate to the user's
permissions

Avoid cluttering the table with every possible metadata field. Use a
details panel or file page for secondary information.

### Screen 5 --- Upload and Encryption

**Purpose:** Make upload and client-side encryption progress
understandable.

Include: - Drag-and-drop target and file picker - Selected file list -
File name and size - Clear progress stages - Cancel action where safe
and supported - Success and failure states - Retry option when supported

Potential status labels, only when backed by actual events: - Preparing
file - Encrypting in browser - Uploading encrypted data - Finalizing -
Complete - Failed

Requirements: - Never display fabricated progress as if it were real. -
Bind progress indicators to actual encryption/upload events in
implementation. - Make it clear that encryption occurs in the browser
only if that is what the implementation does. - Support keyboard
selection and accessible drag-and-drop alternatives. - Respect
reduced-motion settings.

### Screen 6 --- File Details

**Purpose:** Show metadata, ownership, versions, and actions for one
file.

Include: - Filename and file-type icon - Owner - Size - Created/modified
information - Encryption state when verifiable - Current version and
version history if implemented - Sharing summary - Actions based on
permissions

Keep the main details readable. Place advanced technical information
behind a disclosure or secondary panel.

### Screen 7 --- Share File

**Purpose:** Let a file owner or authorized user configure sharing.

Include: - Selected file summary - Recipient selector - Permission
selector - Expiration or access conditions only if supported - Summary
of who will have access - Clear Share action - Confirmation before
high-impact changes - Success and failure states

Use plain-language permissions. Do not suggest that a link is protected
by a password, expiration, or policy unless that feature is actually
implemented.

### Screen 8 --- Shared with Me

**Purpose:** Show files shared with the current user.

Include: - File list - Owner/shared-by information - Access level - Date
shared - Search and useful filters - Clear empty state - Actions
permitted to the recipient

Do not show owner-only actions to recipients.

### Screen 9 --- Shared by Me

**Purpose:** Help users manage files they have shared.

Include: - Shared file list - Recipient(s) - Permission summary - Share
date - Current access status - Manage access action - Revoke access
action when authorized

Revocation must be explained accurately: it can prevent future
authorized retrieval, but it cannot guarantee deletion of plaintext or
keys already downloaded by a recipient.

### Screen 10 --- Access Policies

**Purpose:** Configure attribute-based access control without forcing
users to understand implementation details.

Include: - Policy list - Policy name and short description - Applicable
resource/action - Conditions expressed in readable language -
Enabled/disabled status if supported - Create/edit policy flow - Preview
or explanation of the policy decision when supported

Requirements: - Default-deny behavior should be reflected in clear UX. -
Show why an action is denied without revealing sensitive policy
internals. - Do not imply a policy has been enforced until the backend
actually enforces it. - Keep complex JSON or AST details out of the main
user experience unless the intended audience explicitly needs an
advanced editor.

### Screen 11 --- Audit Log

**Purpose:** Provide an understandable history of relevant security and
file events.

Include: - Event description - Actor - Resource/file - Timestamp -
Outcome - Filters by date, event type, or outcome when implemented -
Event detail view for additional context

Blockchain-related status, when available, should distinguish: - Pending
anchoring - Anchored/confirmed - Failed or delayed anchoring

Requirements: - Never fabricate transaction hashes, blocks, or
confirmations. - A blockchain outage should not be represented as a
failed file operation if file operations remain available. - Use clear
labels and human-readable dates. - Provide an empty state and
loading/error states.

### Screen 12 --- Settings and Security

Include only settings supported by the product, organized into clear
sections such as: - Profile - Account security - Public key/identity
information, if implemented - Session management, if implemented -
Preferences

Avoid implying that MFA, recovery, key rotation, or session controls
exist until implemented. High-impact changes should have clear
consequences and confirmation steps.

### Shared screen states

Every applicable screen should define: - Default state - Loading state -
Empty state - Error state - Success feedback - Disabled state - Hover
and keyboard-focus state - Responsive state

Use the existing empty-state illustrations where appropriate.

------------------------------------------------------------------------

## 6. Component Guidelines

Create a consistent component system during implementation.

### Buttons

Variants: - Primary - Secondary - Tertiary/ghost - Destructive

Each should have: - Default - Hover - Focus-visible - Active -
Disabled - Loading

Use concise verb-first labels such as "Upload files," "Share file,"
"Save changes," and "Revoke access."

### Inputs

-   Persistent visible labels
-   Clear placeholder text when helpful
-   Inline validation
-   Accessible error messages
-   Consistent heights and spacing
-   Visible focus rings
-   Password visibility control when appropriate

Do not rely on placeholder text as the only label.

### Cards and panels

-   Use panels to group related content only.
-   Prefer simple sections over a grid of unrelated cards.
-   Use consistent padding and border treatments.
-   Avoid decorative charts and icons without a purpose.

### File rows and tables

-   Align columns consistently.
-   Use supplied file-type icons.
-   Keep row actions predictable.
-   Use clear truncation for long filenames.
-   Provide accessible names for icon-only controls.
-   Make clickable targets sufficiently large.

### Status badges

Use concise text alongside color; never use color alone to communicate
status.

Examples: - Encrypted - Uploading - Shared - Access denied - Pending -
Confirmed - Failed

Only show states the system can actually determine.

### Dialogs and destructive actions

-   Explain the action and its consequence.
-   Keep primary and destructive actions visually distinct.
-   Require confirmation for significant permission changes or
    revocation.
-   Ensure dialogs are keyboard accessible and have a clear cancel path.

### Toasts

Use the existing toast component as an implementation reference if
appropriate. Toasts should be concise, accessible, dismissible, and not
the only place where important errors or outcomes are explained.

------------------------------------------------------------------------

## 7. Interaction and Motion

Motion should be subtle and purposeful.

Appropriate examples: - Brief button feedback - Small hover
transitions - Smooth opening/closing of menus and dialogs - Upload
animation tied to real progress - Restrained atmospheric cloud motion on
the landing page

Rules: - Never use motion to conceal a state change. - Do not animate
every element. - Respect `prefers-reduced-motion`. - Avoid continuous
motion in the authenticated dashboard if it distracts from file work. -
Ensure focus, hover, and disabled states remain visible without
animation.

------------------------------------------------------------------------

## 8. Responsive Behavior

### Desktop

-   Full sidebar and top bar.
-   Spacious file tables.
-   Dashboard sections may sit side by side when there is sufficient
    width.

### Tablet

-   Narrow or collapsible sidebar.
-   Reduce horizontal gaps while preserving readable content.
-   Allow tables to scroll horizontally only where necessary.

### Mobile

-   Compact top bar and accessible navigation drawer.
-   Stack dashboard sections.
-   Keep primary actions easy to reach.
-   Convert dense tables to readable list rows or cards.
-   Avoid horizontal overflow.
-   Use appropriately sized tap targets.
-   Keep file actions available without hover.
-   Make upload and share flows usable on touch screens.

Test at common viewport widths rather than relying only on a single
desktop screenshot.

------------------------------------------------------------------------

## 9. Accessibility and Readability

Target WCAG 2.2 AA where practical.

-   Provide sufficient text contrast.
-   Ensure keyboard access to navigation, forms, menus, tables, dialogs,
    and actions.
-   Use semantic headings and landmarks.
-   Give meaningful accessible names to icon-only controls.
-   Associate form labels and errors with their inputs.
-   Preserve visible focus indicators.
-   Do not convey security state by color alone.
-   Support zoom and responsive reflow.
-   Use reduced-motion preferences.
-   Use alt text for meaningful images; mark decorative artwork as
    decorative.
-   Avoid tiny metadata and overly dense layouts.

Visual polish must never come at the cost of legibility.

------------------------------------------------------------------------

## 10. Security UX Constraints

The interface must accurately represent the actual security
architecture.

-   The browser is intended to encrypt file content before upload.
-   The server should not receive plaintext files or raw data-encryption
    keys in the intended architecture.
-   Access control decisions must be enforced by the backend, not merely
    hidden in the frontend.
-   The UI must not treat client-side visibility as authorization.
-   Do not expose secrets in URLs, logs, toast messages, or audit event
    descriptions.
-   Do not display a file as encrypted until the relevant operation has
    actually succeeded.
-   Distinguish file-upload status from blockchain audit-anchoring
    status.
-   If audit anchoring is delayed or unavailable, communicate that
    separately from file availability.
-   Revocation prevents future authorized access only to the extent
    supported by the implementation; it cannot erase previously
    downloaded plaintext.
-   Do not present illustrative or mock data as live operational data.
-   Do not claim the product has been independently audited or is immune
    to attack.

------------------------------------------------------------------------

## 11. Stitch Workflow

Use Google Stitch to establish and refine visual design before
implementation.

Official tool: https://stitch.withgoogle.com/

### Project setup

Create a new project: **DropSafe --- Secure Cloud File Sharing**

Use the existing logo and cloud background as primary references. Add
selected icons as secondary references where supported.

### Design sequence

1.  Landing page
2.  Authentication
3.  Dashboard
4.  My Files
5.  Upload and Encryption
6.  File Details
7.  Share File
8.  Shared with Me
9.  Shared by Me
10. Access Policies
11. Audit Log
12. Settings and Security

Design one screen at a time. Review each result before moving to the
next.

### Review checklist for every screen

-   Does it preserve the DropSafe visual identity?
-   Is the purpose of the screen immediately clear?
-   Is the main action obvious?
-   Is the typography readable?
-   Are spacing and alignment consistent?
-   Is the screen overloaded with cards or metadata?
-   Are labels realistic and meaningful?
-   Are all displayed security states honest?
-   Does it use the supplied assets appropriately?
-   Does it handle empty, loading, error, and responsive states?

If Stitch repeatedly produces generic or overcrowded layouts, stop
prompting it to regenerate everything. Refine the composition with
targeted instructions or move to direct implementation with visual
references.

------------------------------------------------------------------------

## 12. Frontend Implementation Handoff

After the design is approved, implement it in Google Antigravity.

Expected frontend direction: - React - TypeScript - Reusable
components - Centralized design tokens - Semantic HTML - Accessible
interactions - Responsive layouts - Existing DropSafe assets stored in
the public asset directory - Browser preview and screenshot review
during refinement

Possible asset layout in the implementation:

``` text
frontend/
  public/
    brand/
      dropsafe-logo.png
    backgrounds/
      cloud-background.png
    icons/
      security/
      files/
    illustrations/
    favicon/
  src/
    components/
    pages/
    layouts/
    styles/
    features/
```

Treat this as a suggested structure, not a requirement to create folders
before the project exists.

### Handoff requirements

Provide Antigravity with: 1. The approved screen designs or screenshots.
2. This `design.md`. 3. The existing asset folder. 4. The approved
screen flow. 5. The component and responsive rules. 6. The security UX
constraints.

Build the UI with realistic but clearly identified mock data until
backend integration is ready. Do not imply mock actions are real
security operations.

------------------------------------------------------------------------

## 13. Acceptance Criteria

The design phase is complete when:

-   The landing page uses the existing logo and cloud artwork
    appropriately.
-   The main visual language is consistent across all designed screens.
-   Text is readable and has deliberate line breaks.
-   Navigation, buttons, forms, file lists, and status badges use
    consistent patterns.
-   The dashboard is calm and functional rather than overloaded.
-   Core file-sharing workflows are represented.
-   Empty, loading, error, success, and disabled states are considered.
-   Desktop and mobile layouts are planned.
-   Security claims and status labels are accurate and not overstated.
-   The approved designs can be handed to Antigravity with this
    specification and the existing assets.

------------------------------------------------------------------------

## 14. Non-Goals for This Document

This document does not: - Implement frontend or backend code. - Confirm
that any security feature is already implemented. - Replace the
technical requirements or backend architecture documents. - Require new
asset kits. - Require all screens to be generated in one Stitch
prompt. - Require a particular visual detail to remain unchanged if
later review demonstrates that it harms usability.

------------------------------------------------------------------------

## 15. Immediate Next Step

1.  Open a new Google Stitch project named **DropSafe --- Secure Cloud
    File Sharing**.
2.  Attach `dropsafe-logo.png` and `cloud-background.png` as primary
    visual references.
3.  Use the landing-page requirements in Section 5 as the first screen
    brief.
4.  Generate one landing page.
5.  Review the result against the checklist in Section 11.
6.  Refine it before designing authentication or the dashboard.

**Design north star:** A calm, cinematic, premium file-sharing
experience where the DropSafe cloud identity creates atmosphere, while
typography, spacing, and clear interactions make the product easy to
trust and use.
