# DropSafe — UI/UX Design Brief and Lightweight Design System

**Document:** `04-UI-UX.md`  
**Product:** DropSafe — *Your Files. Your Control.*  
**Brand message:** *Encrypted files. Controlled access. Verifiable activity.*  
**Related documents:** `01-PRD.md`, `02-TRD.md`, `03-APP-FLOW.md`  
**Status:** Recommended design baseline for Google Stitch and Google Antigravity  
**Scope:** Visual design, reusable components, responsive behavior, accessibility, and page-specific guidance. This document is a design specification, not application code.

---

## How to Use This Document

Treat this document as the visual source of truth for DropSafe. Use it when generating screens in Google Stitch and when implementing those screens in Google Antigravity.

- **MUST / REQUIRED** means a consistency, usability, accessibility, or security-communication requirement.
- **SHOULD / RECOMMENDED** means the preferred default; change it only when there is a clear usability reason.
- **OPTIONAL** means a restrained enhancement that must not introduce a new product feature.
- Keep the established scope and routes in `03-APP-FLOW.md`. Do not invent new pages or product capabilities.
- When a security state is unknown or has not been verified, show it as **Unknown**, **Pending**, or **Not verified**—never imply success.
- The authenticated workspace should remain predominantly monochrome. Use color semantically, not decoratively.

---

## 1. Design Philosophy

### 1.1 Product purpose

DropSafe is a secure cloud file-sharing web application. It should feel familiar enough for everyday file management while making access control, encryption, and auditability understandable. The interface is also a cryptography capstone, so the implementation must demonstrate real security behavior rather than relying on security-themed visuals.

### 1.2 Design goals

1. **Clarity before spectacle.** Users should immediately understand where their files are, what actions they can take, and whether a security operation succeeded.
2. **Security with progressive disclosure.** Show a concise status in the default view. Let users open details for encryption, access policy, signature verification, audit integrity, and blockchain anchoring.
3. **Trust through precision.** Label exactly what was verified. A successful file upload is not the same as a verified signature or blockchain anchor.
4. **Familiar file management.** Use recognizable patterns for file lists, upload progress, sharing, and action menus.
5. **Consistent behavior.** Shared actions should look and behave the same on every screen.
6. **Accessible by default.** Support keyboard navigation, readable text, screen readers, visible focus, reduced motion, and responsive layouts.
7. **Quiet visual identity.** Use a refined monochrome foundation, careful spacing, restrained borders, and a small number of meaningful status colors.

### 1.3 Avoid

- Neon “cybersecurity” styling, glowing borders, excessive gradients, random glass cards, or decorative padlocks everywhere.
- A different visual style for every page.
- Using green merely to make the product feel secure.
- A single vague “Secure” badge that hides which checks actually passed.
- Color as the only way to communicate a status.
- Fake charts, fake activity, fabricated file metadata, or unimplemented security indicators.
- Motion that delays a user’s task or cannot be reduced.

---

## 2. Overall Visual Direction

### Required direction: Premium monochrome workspace

Use a clean, editorial, productivity-oriented interface with a black/white/neutral-gray foundation. The signed-in workspace should be closer to a calm, well-crafted productivity tool than to a security operations dashboard.

**Brand character**
- Precise, calm, discreet, dependable, contemporary.
- Strong typographic hierarchy and generous but efficient whitespace.
- Thin neutral borders and mostly flat surfaces.
- Small, purposeful use of status colors.
- Clear hierarchy between file content, actions, and security details.

**Landing and upload moments**
- The public landing page may use a restrained atmospheric cloud or abstract upload visual, if it supports the product message.
- The upload area may have a subtle cloud-inspired visual or restrained motion.
- Do not carry heavy illustration or glassmorphism into every authenticated screen.
- Prefer CSS-level subtle effects and static fallbacks over large decorative assets.

**Workspace**
- White or near-white main canvas in light mode.
- Near-black navigation/sidebar or a neutral light sidebar; choose one treatment and keep it consistent across the workspace. Recommended baseline: light sidebar with a subtle divider for a calm, spacious feel.
- File tables/lists remain the primary focus.
- Security information appears as small status badges, detail panels, and audit rows.

---

## 3. Design Inspiration and References

Use these as **pattern-level inspiration**, not as templates to copy.

| Reference | Borrow | Do not copy |
|---|---|---|
| Notion-like productivity tools | Clear hierarchy, quiet surfaces, compact navigation, content-first layouts | Dense, nested navigation that exceeds the MVP |
| Dropbox-like file workflows | Familiar upload, file list, sharing, and download patterns | Any implication that DropSafe has features not specified in the PRD |
| Modern developer tools | Precise statuses, readable metadata, clear copyable identifiers | Dense technical panels as the default experience |
| Shuttle-style atmospheric upload experiences | A restrained cloud/upload visual and a sense of motion | Excessive animation, neon gradients, or distracting backgrounds |

**Rule:** Design references inform the visual language only. The PRD and App Flow determine functionality.

---

## 4. Color Palette

### 4.1 Core palette

The default palette is light monochrome with an optional dark theme. HEX values are design tokens; implementation should use semantic variables rather than hard-coded colors inside individual components.

| Token | HEX | Intended use |
|---|---:|---|
| `--color-primary` | `#171717` | Brand anchor, primary buttons, key emphasis |
| `--color-primary-hover` | `#303030` | Hover state for primary actions |
| `--color-secondary` | `#525252` | Secondary emphasis and supporting controls |
| `--color-background` | `#FFFFFF` | Main light-mode canvas |
| `--color-surface` | `#FAFAFA` | Cards, panels, subtle containers |
| `--color-surface-raised` | `#FFFFFF` | Dialogs, menus, popovers |
| `--color-text` | `#171717` | Main body text and headings |
| `--color-text-muted` | `#525252` | Secondary labels and supporting text |
| `--color-text-subtle` | `#737373` | Non-critical metadata; avoid for small text if contrast is insufficient |
| `--color-border` | `#E5E5E5` | Default separators and outlines |
| `--color-border-strong` | `#A3A3A3` | Strong dividers and outlined controls |
| `--color-primary-action` | `#171717` | Primary action fill |
| `--color-on-primary` | `#FFFFFF` | Text/icons on primary action |
| `--color-success` | `#166534` | Confirmed success |
| `--color-success-bg` | `#F0FDF4` | Success callouts and badges |
| `--color-warning` | `#92400E` | Warning and pending-attention states |
| `--color-warning-bg` | `#FFFBEB` | Warning callouts and badges |
| `--color-error` | `#B91C1C` | Errors, destructive actions, failed checks |
| `--color-error-bg` | `#FEF2F2` | Error callouts and badges |
| `--color-info` | `#1D4ED8` | Informational states |
| `--color-info-bg` | `#EFF6FF` | Informational callouts |
| `--color-focus` | `#2563EB` | Keyboard focus ring |
| `--color-overlay` | `#171717` | Modal backdrop, with transparency in implementation |

### 4.2 Semantic usage rules

- **Primary:** Use monochrome for brand and primary actions. Do not use color accents as decoration.
- **Success:** Use only when the operation or verification actually succeeded.
- **Warning:** Use for pending operations, expiring links, incomplete setup, or a condition that requires attention.
- **Error:** Use for failed operations, denied actions, or failed verification.
- **Info:** Use for neutral guidance and explanations.
- **Unknown / not verified:** Use neutral gray and explicit text. Do not style unknown states as success.
- **Destructive actions:** Use error color for the final destructive action or confirmation detail, not as the default styling for every delete menu item.

### 4.3 Dark mode palette

Dark mode should preserve the same semantic meaning and component hierarchy. Do not simply invert every color.

| Token | HEX | Intended use |
|---|---:|---|
| `--color-background-dark` | `#111111` | Main dark-mode canvas |
| `--color-surface-dark` | `#1A1A1A` | Cards and panels |
| `--color-surface-raised-dark` | `#242424` | Dialogs, menus, raised surfaces |
| `--color-text-dark` | `#F5F5F5` | Primary text |
| `--color-text-muted-dark` | `#D4D4D4` | Secondary text |
| `--color-text-subtle-dark` | `#A3A3A3` | Tertiary metadata |
| `--color-border-dark` | `#404040` | Default borders |
| `--color-border-strong-dark` | `#737373` | Strong borders |
| `--color-primary-dark` | `#F5F5F5` | High-emphasis action fill where appropriate |
| `--color-on-primary-dark` | `#171717` | Text on light primary action |
| `--color-success-dark` | `#4ADE80` | Success indicators |
| `--color-warning-dark` | `#FBBF24` | Warning indicators |
| `--color-error-dark` | `#F87171` | Error indicators |
| `--color-info-dark` | `#60A5FA` | Information indicators |
| `--color-focus-dark` | `#93C5FD` | Focus ring |

Status backgrounds in dark mode should be dark, muted variants with readable foreground colors. Verify contrast in the rendered implementation rather than relying on token names alone.

### 4.4 Contrast rule

Text and interactive controls MUST meet WCAG 2.2 AA contrast requirements: generally 4.5:1 for normal text and 3:1 for large text and meaningful UI boundaries/icons. The subtle text token is not automatically suitable for every small-text use; test actual foreground/background pairs.

---

## 5. Typography System

### 5.1 Font family

**Recommended:** `Inter` with a system sans-serif fallback. If loading a remote font adds unnecessary complexity, use a high-quality system font stack. Do not block initial rendering on a font download.

Suggested stack: `Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`.

Use a monospace stack only for hashes, short technical identifiers, and code-like values—not for regular body text.

### 5.2 Type scale

| Token | Size | Weight | Line height | Use |
|---|---:|---:|---:|---|
| `--text-display` | `40px` / `2.5rem` | 600–700 | 1.1 | Optional landing-page hero heading; desktop only |
| `--text-h1` | `32px` / `2rem` | 600–700 | 1.2 | Main page heading |
| `--text-h2` | `24px` / `1.5rem` | 600 | 1.25 | Major section heading |
| `--text-h3` | `20px` / `1.25rem` | 600 | 1.3 | Card/section heading |
| `--text-h4` | `16px` / `1rem` | 600 | 1.4 | Subsection and dialog heading |
| `--text-body-lg` | `16px` / `1rem` | 400 | 1.6 | Introductory copy |
| `--text-body` | `14px` / `0.875rem` | 400 | 1.5 | Default application text |
| `--text-label` | `14px` / `0.875rem` | 500–600 | 1.4 | Form labels, table headers |
| `--text-small` | `12px` / `0.75rem` | 400–500 | 1.45 | Secondary metadata; use sparingly |
| `--text-mono` | `12px` / `0.75rem` | 400–500 | 1.5 | Short hashes, version IDs, technical details |

### 5.3 Typography rules

- Use sentence case for headings, buttons, labels, and navigation.
- Avoid all-caps labels except for very small, non-essential eyebrow text.
- Use bold for hierarchy, not for whole paragraphs.
- Long explanatory text should be no wider than roughly 65–75 characters per line.
- Keep important security explanations at 14px or larger whenever possible.
- Hashes and identifiers may wrap or use a copy action; never force page-wide horizontal scrolling.
- Do not communicate meaning using typography alone.

---

## 6. Spacing System

Use a consistent 4px base grid. Prefer spacing tokens to one-off values.

| Token | Value | Typical use |
|---|---:|---|
| `--space-1` | `4px` | Icon-to-label gap, micro spacing |
| `--space-2` | `8px` | Compact control spacing |
| `--space-3` | `12px` | Related control/content gap |
| `--space-4` | `16px` | Default component padding/gap |
| `--space-5` | `20px` | Form groups and compact panels |
| `--space-6` | `24px` | Card padding, section spacing |
| `--space-8` | `32px` | Major content groups |
| `--space-10` | `40px` | Large section separation |
| `--space-12` | `48px` | Page-level section spacing |
| `--space-16` | `64px` | Large landing-page spacing |

**Rules**
- Default form field gap: 16–20px.
- Default card padding: 20–24px on desktop, 16px on mobile.
- Keep related labels and controls close; separate unrelated groups more generously.
- Do not use whitespace to push important actions below the fold unnecessarily.
- Compact tables may use 12–16px row padding, but must remain comfortably targetable.

---

## 7. Layout and Grid Rules

### 7.1 Application shell

- Use a consistent application shell for protected routes.
- Recommended desktop structure: left sidebar, top header/content toolbar, main content region.
- Sidebar width: approximately 224–248px when expanded; allow a compact/collapsed state only if it improves usability without hiding essential labels.
- Main content max width: approximately 1200–1360px for file-management views; narrower forms and explanatory content.
- Main content horizontal padding: 32px desktop, 24px tablet, 16px mobile.
- Align page title, supporting text, and primary action consistently across workspace screens.

### 7.2 Grid and density

- Prefer a single-column content flow for forms and detail panels.
- Use two-column layouts only when both columns remain readable and logically related.
- File listing should favor a table/list on desktop and a stacked card/list row on narrow mobile screens.
- Do not shrink labels or buttons merely to preserve a desktop layout.
- Use responsive containers rather than fixed page widths.

### 7.3 Page header pattern

Each authenticated page should normally use:
1. Page title.
2. Optional one-line explanation.
3. Primary action aligned consistently (right on wide screens; below the title on narrow screens).
4. Optional breadcrumb or contextual navigation where the App Flow calls for it.

Do not add summary cards to every page just to fill space.

---

## 8. Border Radius and Shadows

| Token | Value | Use |
|---|---:|---|
| `--radius-sm` | `6px` | Small controls, badges, compact menus |
| `--radius-md` | `8px` | Inputs, buttons, standard cards |
| `--radius-lg` | `12px` | Larger cards and panels |
| `--radius-xl` | `16px` | Optional landing/feature containers |
| `--radius-pill` | `999px` | Status badges and pill controls only when appropriate |

**Shadows**
- Default cards: no shadow or an extremely subtle shadow; rely on borders and surface contrast.
- Dropdowns/popovers: subtle elevation to separate them from content.
- Dialogs: visible but restrained elevation plus a backdrop.
- Avoid layered shadows, colored glows, and large shadows on every card.
- Keep radius and shadow behavior consistent across all routes.

---

## 9. Iconography

- Use one consistent line-icon library (Lucide-style outline icons are recommended).
- Default icon sizes: 16px for dense controls, 18–20px for navigation/actions, 24px for empty states or larger feature callouts.
- Use a consistent stroke weight.
- Pair icons with text for important actions; icon-only buttons require an accessible name and tooltip where helpful.
- Do not use emoji as interface icons.
- Do not use a padlock icon as the sole proof of encryption or access control.
- File-type icons may help scanning, but must not replace the visible filename.
- Status icons must be accompanied by text or an accessible equivalent.

---

## 10. Button Design

### 10.1 Button variants

| Variant | Visual treatment | Intended use |
|---|---|---|
| Primary | Dark fill, white text in light mode; inverse treatment in dark mode | One main action per page/section |
| Secondary | Neutral surface, visible border, strong text | Alternate action |
| Tertiary/Ghost | Transparent surface, text/icon only | Low-emphasis actions and toolbar controls |
| Destructive | Error-colored emphasis, especially in confirmation | Revoke, delete, or other destructive final actions |
| Link | Underlined or clearly link-styled text | Navigation and inline help |

### 10.2 Sizing and behavior

- Standard button height: 40px; compact button: 32–36px; prominent landing CTA: 44–48px.
- Minimum touch target: 24×24 CSS pixels under WCAG 2.2 AA, with a preferred target around 40–44px for common mobile actions.
- Use 8px horizontal icon/text spacing.
- A button should have a clear label describing the result: “Upload files,” “Save policy,” “Revoke access.”
- Show disabled states distinctly, and explain why a critical action is unavailable where useful.
- During submission, prevent accidental duplicate actions and show a progress label or spinner with accessible status text.
- Do not show two equally prominent primary buttons side by side unless the flow truly has two co-equal actions.
- Destructive actions should not be triggered by a single ambiguous icon click when the consequence is significant.

---

## 11. Input and Form Design

### 11.1 Text inputs and text areas

- Standard height: 40–44px; text areas grow for multi-line content.
- Use a visible label above each field. Placeholder text is an example, not a substitute for a label.
- Use helper text for format, constraints, or privacy implications.
- Show errors adjacent to the relevant field and connect them programmatically.
- Preserve entered values when validation fails unless retaining them would be unsafe.
- Never reveal secrets or private keys in a normal text field by default.

### 11.2 Selects, checkboxes, and switches

- Select controls should match input height and border treatment.
- Use checkboxes for independent choices and switches only for immediate on/off settings.
- Do not use a switch for an action that requires explicit save/confirmation unless the behavior is clearly communicated.
- Provide an accessible label and visible checked/selected state.
- Long option descriptions should wrap rather than truncate important meaning.

### 11.3 Validation and security-related forms

- Validate client-side for convenience and server-side for security.
- Do not expose stack traces, internal policy expressions, secrets, or sensitive existence information in errors.
- Access-policy forms should explain attributes and file permissions in plain language, with advanced detail available on demand.
- Show a summary before committing a complex or destructive policy change.
- Public share-link controls must remain disabled or clearly marked unavailable until the secure key-delivery design in `02-TRD.md` is resolved. Never expose a raw document encryption key in a URL or query string.

---

## 12. Cards and Containers

- Use cards only when they group related content or actions.
- Standard card: surface background, 1px border, 8–12px radius, 20–24px padding on desktop.
- Avoid putting every line of content inside its own card.
- Security detail panels should use a clear heading, status, short explanation, and optional technical details.
- Empty states may use a simple icon/illustration, one explanatory sentence, and a relevant action.
- Cards must not imply that a verification passed merely because the panel is styled as a success card.

---

## 13. Tables and Data Display

### 13.1 File list

Desktop file list should prioritize:
- Filename and file-type icon.
- Owner or sharing context where relevant.
- Modified/uploaded date if the data is available.
- File size if the data is available.
- Sharing/access status.
- A consistent row action menu.

Only display metadata actually returned by the application. Do not invent owners, dates, sizes, or access counts.

### 13.2 Table behavior

- Use clear column headers and semantic table markup where the content is tabular.
- Keep headers visually distinct but understated.
- Use consistent row heights and alignment.
- Provide hover and keyboard-focus row states without relying on hover alone.
- Long filenames should wrap or truncate with a way to inspect the full name.
- Use pagination or progressive loading only if the implementation supports it.
- On mobile, convert rows into stacked layouts or a compact list with the most important information first. Do not require horizontal scrolling for routine file actions.
- Empty, loading, error, and populated states must have distinct designs.

### 13.3 Audit log display

Audit rows should prioritize event type, timestamp, outcome, and relevant actor/resource details when authorized. Provide a details view for event IDs, hashes, batch/anchor state, and verification results. Use neutral monospace styling for hashes and a copy control where appropriate.

Do not label a record “blockchain verified” unless the applicable commitment and proof were successfully checked. Distinguish:
- Event recorded
- Included in a Merkle batch
- Batch anchored on-chain
- Commitment/proof verified

These are different states, not synonyms.

---

## 14. Navigation Components

### 14.1 Primary workspace navigation

Follow the routes and screen inventory in `03-APP-FLOW.md`. The core navigation should remain limited to the MVP areas, such as:
- Workspace/files
- Shared files
- Access control or policy management where specified
- Audit logs
- Account/settings area only where defined by the existing flow
- Admin attribute management, shown only to authorized administrators

Do not invent new destinations such as billing, teams, analytics, or a marketplace.

### 14.2 Navigation rules

- Use consistent labels across sidebar, page title, breadcrumbs, and buttons.
- Clearly distinguish active navigation from hover and keyboard focus.
- Do not rely only on icons in the expanded desktop sidebar.
- On mobile, use a compact navigation pattern that preserves access to core destinations without covering content.
- Hide admin-only navigation for users who do not have the relevant role; the server must still enforce authorization.
- Keep navigation stable between protected screens.

### 14.3 Header

The header may contain the page context, relevant page-level action, and account/session menu. Do not overcrowd it with decorative security icons or duplicate the entire sidebar.

---

## 15. Modals and Dialogs

Use dialogs for focused decisions, confirmations, or short tasks—not for entire complex workflows.

**Required behavior**
- Clear title and concise consequence statement.
- One visually primary confirmation action and one secondary cancel action.
- Destructive action clearly identified.
- Focus moves into the dialog when opened and returns to the invoking control when closed.
- Escape closes non-destructive dialogs where appropriate.
- Destructive or security-sensitive operations must not accidentally close and commit on backdrop click.
- On mobile, dialogs may become full-screen sheets if that improves readability.
- Avoid nested dialogs.

**Typical uses from the existing flow**
- Confirm deletion.
- Confirm access revocation.
- Confirm a policy change when it materially changes who can access a file.
- Show file details or a focused audit-detail view when the flow calls for it.

Never use a confirmation dialog to imply that a requested action succeeded before the backend confirms it.

---

## 16. Notifications and Feedback

### 16.1 Toast notifications

- Use for brief outcomes that do not require user input.
- Place consistently, preferably top-right on desktop and near the top/bottom safe area on mobile.
- Use concise, specific messages: “File uploaded” or “Access revoked.”
- Do not use toasts as the only way to report a critical security failure.
- Do not make important messages disappear so quickly that users cannot read them.
- Use `aria-live` appropriately and avoid announcing the same event multiple times.

### 16.2 Inline feedback

Use inline status panels for:
- Upload progress and failure.
- Key setup or recovery limitations.
- Access-denied explanations that are safe to disclose.
- Signature verification results.
- Audit batching and blockchain anchoring status.
- Pending or failed operations requiring a retry.

### 16.3 Security-status language

Prefer precise language:
- “File encrypted in this browser” only after client-side encryption completed.
- “Signature verified” only after cryptographic verification succeeded against an authenticated key.
- “Access revoked for future requests” rather than “All copies revoked.”
- “Anchor pending” while a batch has not yet been anchored.
- “Anchor verified” only after checking the on-chain commitment/proof.

Do not claim that blockchain proves an event was truthful or that every event was captured. The audit interface should describe blockchain anchoring as evidence that a commitment was recorded, not as proof of the underlying event’s truth.

---

## 17. Loading and Skeleton States

- Use skeletons for known page structures such as file rows or audit rows.
- Use a small spinner or progress indicator for a single short operation.
- Uploads and other long-running operations should show real progress when available; do not fabricate percentage values.
- Preserve the surrounding layout to prevent content jumping.
- Keep controls disabled only when necessary, and communicate the current action.
- For background blockchain anchoring, show “Pending” or “Queued” rather than blocking file browsing or download.
- Respect `prefers-reduced-motion`.
- Avoid indefinite skeletons: transition to an error/retry state when a request fails or times out.
- Loading placeholders should not be announced as real content to screen readers.

---

## 18. Empty and Error States

### 18.1 Empty states

Every data-driven screen should have a designed empty state. Use:
1. A concise heading.
2. One sentence explaining why the area is empty.
3. A relevant next action, if the user is allowed to take one.
4. Optional restrained iconography.

Examples:
- No files yet → “Upload your first file” action.
- No shared files → explain that files shared with the user will appear here.
- No audit entries → state that no events are available for the selected scope.
- No policies configured → provide the existing flow’s policy creation action if authorized.
- No search results, if search exists in the approved PRD/flow → suggest checking the query; do not add search solely for this design document.

### 18.2 Error states

- State what failed in plain language and what the user can do next.
- Provide Retry only when retrying is safe and supported.
- Do not expose stack traces, internal IDs, sensitive policy details, or secret material.
- Use a neutral, generic response when revealing whether a protected resource exists would create an information leak.
- Distinguish network failure from authorization denial and cryptographic verification failure where safe.
- A failed signature, integrity check, or audit proof must be visually unmistakable and must not be styled as a success.
- If blockchain anchoring is unavailable, file operations should remain usable where possible and the audit UI should show the pending/failed anchor state honestly.

---

## 19. Responsive Design Rules

Use content-driven breakpoints; the values below are recommended starting points and may be adjusted after testing.

| Breakpoint | Width | Layout behavior |
|---|---:|---|
| Mobile | `< 640px` | Single column, compact navigation, stacked page actions, list rows instead of wide tables |
| Tablet | `640–1023px` | Reduced sidebar or collapsible navigation, flexible two-column layouts only when comfortable |
| Desktop | `1024–1439px` | Full workspace shell and standard file table/list |
| Wide desktop | `≥ 1440px` | Keep content max-width; do not stretch text and tables edge to edge |

### Mobile requirements

- Keep the primary action easy to locate.
- Stack page title and primary action when side-by-side placement becomes cramped.
- Convert tables to stacked rows/cards with filename and main action visible.
- Use full-width forms and dialogs/sheets where needed.
- Ensure menus and dialogs fit within the viewport and do not hide critical actions behind the keyboard.
- Keep touch targets comfortably sized and spaced.
- Prevent horizontal page scrolling, especially for hashes, long filenames, and audit metadata.
- Do not hide essential security warnings on small screens.
- Test portrait and landscape where relevant.

### Tablet requirements

- Allow the sidebar to collapse or become a drawer.
- Keep file actions discoverable without forcing desktop-style hover.
- Avoid squeezing a full desktop table into a narrow content area.

### Desktop requirements

- Use available space for scanability, not unnecessary decorative panels.
- Keep common file actions near the file list.
- Avoid excessive empty width in forms; constrain reading width.
- Support keyboard-only use of navigation, menus, tables, and dialogs.

---

## 20. Dark and Light Mode

**Recommended baseline:** Implement light mode first and make the token system compatible with dark mode. Add a user-facing theme toggle only if it is included in the agreed implementation scope; do not invent a settings page solely for theme selection.

If both themes are implemented:
- Use semantic design tokens; components should not hard-code light-only colors.
- Preserve status meanings in both themes.
- Re-check text, icon, border, disabled, hover, and focus contrast.
- Ensure screenshots and loading/empty/error states look intentional in both modes.
- Avoid pure-white large surfaces against pure-black surfaces if it creates glare; use the palette above.
- Follow the system theme by default if there is no user preference setting.
- Persist a chosen preference only if the application has an appropriate, agreed mechanism.

---

## 21. Accessibility Requirements

Target **WCAG 2.2 Level AA** for core flows.

### Required checklist

- [ ] All functionality is available by keyboard.
- [ ] Keyboard focus is visible and not obscured by sticky headers, drawers, or dialogs.
- [ ] Use semantic headings in a logical order.
- [ ] Every form control has a persistent programmatic label.
- [ ] Error messages are associated with the relevant field and explain how to fix the issue where possible.
- [ ] Color is never the only way to convey status.
- [ ] Text and meaningful UI boundaries meet applicable contrast requirements.
- [ ] Common touch targets are preferably around 40–44px; never fall below applicable WCAG 2.2 target-size requirements without a valid exception.
- [ ] Dialogs manage focus correctly and have accessible names.
- [ ] Icon-only controls have accessible names.
- [ ] Status changes and asynchronous results are announced appropriately to assistive technology.
- [ ] Reduced-motion preferences are respected.
- [ ] Zoom to 200% does not hide essential functionality or force routine horizontal scrolling.
- [ ] File upload supports a clear keyboard-accessible selection path; drag-and-drop must not be the only method.
- [ ] Tables have meaningful headers and relationships.
- [ ] Do not use tiny low-contrast text for important security explanations.

### Motion and animation

- Keep animation short, purposeful, and non-essential.
- Do not animate security success in a way that could be mistaken for verification before it completes.
- Provide a static fallback for the atmospheric cloud/upload visual.
- Respect `prefers-reduced-motion: reduce`.
- Avoid flashing, parallax, and continuous decorative movement.

---

## 22. Component Reuse Guidelines

### 22.1 Build shared components first

Recommended shared component families:
- Application shell, sidebar/navigation, page header, breadcrumbs where used.
- Buttons, icon buttons, text fields, selects, checkboxes, switches.
- Status badges, inline alerts, toasts, progress indicators, skeletons.
- Cards, section containers, dropdown menus, dialogs, confirmation dialogs.
- File row/list, file action menu, file metadata display.
- Security status summary and expandable security details.
- Audit event row, audit detail panel, hash display/copy control.
- Empty state, error state, and permission-denied state.

These are component categories, not a requirement to create a separate component for every minor visual variation.

### 22.2 Reuse rules

- A component should have one clear responsibility and a small set of intentional variants.
- Use design tokens for color, spacing, radius, type, and elevation.
- Do not create page-specific copies of buttons, inputs, badges, or dialogs.
- Avoid “variant explosion.” Add a variant only when a real recurring use case exists.
- Keep labels, status semantics, and interaction behavior consistent.
- Components must not infer security success from styling; they should receive an explicit state from the application.
- Use the same status labels and visual treatments across file details, sharing, and audit views.
- Keep business logic and cryptographic verification separate from purely presentational UI components.

### 22.3 Suggested status badge vocabulary

| Status | Meaning | Suggested treatment |
|---|---|---|
| Encrypted | Client-side encryption completed for this file/version | Neutral or success, depending on the exact assertion |
| Shared | One or more active share permissions exist | Neutral |
| Revoked | Future access through the relevant grant has been revoked | Neutral/warning |
| Pending | Operation or audit step is not complete | Warning |
| Verified | A named cryptographic check passed | Success |
| Failed | Operation or verification failed | Error |
| Unknown | State has not been confirmed | Neutral |
| Not anchored | No confirmed blockchain anchor exists | Neutral/warning |
| Anchor verified | The on-chain commitment/proof was checked successfully | Success |

A badge should include a short visible label. Technical detail can be shown on demand, but must not be hidden when needed to understand a failure.

---

## 23. Page-Specific Design Notes

Follow the screen inventory, route names, and journeys in `03-APP-FLOW.md`. These notes specify visual treatment, not new functionality.

### 23.1 Public landing page

**Purpose:** Explain DropSafe and direct visitors to registration or login.

- Use a strong headline, short supporting copy, and one clear primary CTA.
- Keep the product tagline “Your Files. Your Control.” visible in the brand area or hero.
- Supporting message: “Encrypted files. Controlled access. Verifiable activity.”
- Use a restrained monochrome layout with optional cloud/upload atmospheric artwork.
- Explain the value proposition in plain language; avoid unsupported absolute claims such as “unhackable” or “100% secure.”
- Keep login/register navigation clear.
- On mobile, place the CTA within the first screen when practical and avoid oversized hero artwork.

### 23.2 Login and registration

- Keep forms narrow, calm, and focused.
- Use clear labels, appropriate autocomplete attributes, and field-level validation.
- Explain authentication errors without exposing whether a sensitive account or resource exists when that would be unsafe.
- Show loading and submission states.
- Do not invent social sign-in, multi-factor authentication, email verification, or password-reset flows unless those are added to the requirements.

### 23.3 Key setup / onboarding

- Explain why key setup is needed before encrypted upload/sharing, using plain language.
- Separate user-facing explanation from advanced cryptographic details.
- Make any export, backup, or recovery limitations explicit before the user proceeds.
- Never display or log private-key material in ordinary UI, analytics, URLs, or error messages.
- Do not imply that a forgotten key can be recovered unless a real, reviewed recovery mechanism exists.
- Use a clear completion state only after the relevant setup step actually succeeds.

### 23.4 Workspace / file dashboard

- Page title and “Upload files” primary action should be easy to find.
- File list is the primary content; avoid unnecessary metric cards.
- Keep shared state and relevant actions visible but secondary to filenames.
- Use clear empty, loading, and failure states.
- Show only real file metadata.
- A file’s existence or metadata must not be disclosed to unauthorized users.

### 23.5 Upload experience

- Provide both a keyboard-accessible file picker and drag-and-drop if supported.
- Show selected filenames, size when available, progress, completion, and per-file errors.
- Explain that file content is encrypted in the browser before ciphertext upload only when that behavior is implemented and has completed for the relevant file.
- Separate encryption progress from upload progress if both can be reported accurately.
- Do not fabricate progress percentages.
- Respect reduced motion; the atmospheric upload visual is optional and must not obstruct the task.
- If encryption fails, do not present the file as successfully uploaded and encrypted.

### 23.6 File details

- Organize content into clear groups: file information, sharing/access state, and security/audit details.
- Keep the most common actions easy to locate.
- Show cryptographic and audit details progressively rather than overwhelming the default view.
- Distinguish file version, key version, signature status, and anchor status when the data exists.
- Never present a signature or integrity check as passed without a successful verification result.

### 23.7 Shared files

- Clearly distinguish files shared with the current user from files owned by them, following the App Flow.
- Show available actions based on server-authorized permissions.
- If an action is denied, explain the limitation in plain language without exposing sensitive policy internals.
- Do not assume that viewing a file means the user can download, reshare, or change its permissions.

### 23.8 Sharing and access control

- Use a focused sharing panel or page with a clear recipient/access summary.
- Explain the difference between attribute-based eligibility and file-specific permissions in accessible language.
- Keep technical policy JSON/AST out of the default experience; show advanced policy detail only where the flow supports it.
- Provide a review step before a consequential policy change.
- Make revoked grants visibly distinct from active grants.
- Explain that revocation blocks future authorized retrieval but cannot erase plaintext already downloaded by a recipient.
- Registered-recipient sharing and protected shareable links are in the PRD, but the share-link key-delivery design remains an open TRD decision. Until resolved, do not present link sharing as ready for use and never put a raw document key in the URL.

### 23.9 Audit logs

- Present a readable event list before advanced cryptographic detail.
- Include clear event outcomes and timestamps when available.
- Use explicit states for record creation, Merkle-batch inclusion, blockchain anchoring, and proof verification.
- Provide a detail view for hashes and identifiers, with copy controls and wrapping.
- Show pending, failed, and unavailable states honestly.
- Do not imply that a blockchain anchor proves event truth or guarantees that every event was recorded.
- Keep blockchain availability separate from ordinary file-operation status.

### 23.10 Attribute administration

- Show this navigation and route only to authorized administrators.
- Keep attribute names, values, and assignment actions explicit.
- Provide confirmation/review for changes that alter a user’s access eligibility.
- Explain that attributes are trusted authorization inputs.
- Avoid exposing signing secrets or sensitive backend configuration.
- The UI is not a security boundary; the backend must enforce admin permissions.

### 23.11 Dialogs, menus, and account/session controls

- Keep menu items consistent and use text labels for important actions.
- Separate destructive actions from routine actions.
- Make logout/session-end behavior clear and ensure the client clears sensitive in-memory state according to the implementation.
- Do not add account/settings controls that are not supported by the existing PRD/App Flow.

---

## 24. CSS Variable Suggestions

The following is a token naming reference, not application code. Implement tokens in the project’s chosen styling system and keep component styles tied to semantic variables.

| Category | Suggested variables |
|---|---|
| Colors | `--color-primary`, `--color-background`, `--color-surface`, `--color-text`, `--color-text-muted`, `--color-border`, `--color-success`, `--color-warning`, `--color-error`, `--color-info`, `--color-focus` |
| Typography | `--font-sans`, `--font-mono`, `--text-h1`, `--text-h2`, `--text-body`, `--text-small`, `--line-height-body` |
| Spacing | `--space-1` through `--space-16` |
| Radius | `--radius-sm`, `--radius-md`, `--radius-lg`, `--radius-xl`, `--radius-pill` |
| Layout | `--sidebar-width`, `--content-max-width`, `--page-padding-x` |
| Elevation | `--shadow-popover`, `--shadow-dialog` |
| Motion | `--duration-fast`, `--duration-normal`, `--ease-standard` |

---

## 25. Required vs Optional Design Decisions

| Decision | Status | Rule |
|---|---|---|
| Premium monochrome workspace | **Required** | Keep the authenticated experience restrained and consistent |
| DropSafe name and tagline | **Required** | Use “DropSafe” and “Your Files. Your Control.” consistently |
| Semantic status colors | **Required** | Use colors only for meaningful states and pair them with text |
| Responsive desktop/tablet/mobile behavior | **Required** | Core flows must work at all three sizes |
| WCAG 2.2 AA target | **Required** | Include keyboard, contrast, labels, focus, and screen-reader support |
| Progressive disclosure for security detail | **Required** | Simple status by default, technical details on demand |
| Honest verification/anchor states | **Required** | Never claim success before verification completes |
| Cloud-inspired landing/upload visual | **Optional** | Restrained, performance-conscious, and non-blocking |
| Glassmorphism | **Optional and limited** | If used, only in a small landing/upload area; maintain contrast |
| Dark mode | **Optional** | Token system should support it; implement only within agreed scope |
| Animated transitions | **Optional** | Subtle, short, reduced-motion aware |
| Collapsible sidebar | **Optional** | Add only if it improves navigation at intermediate widths |

---

## 26. Design Acceptance Checklist

Before accepting a screen from Stitch or Antigravity, verify:

### Visual consistency
- [ ] Uses the shared typography, spacing, color, radius, and border tokens.
- [ ] Uses the same button, input, badge, dialog, and navigation styles as other screens.
- [ ] Has a clear content hierarchy and avoids unnecessary cards or decoration.
- [ ] Uses consistent names for the same actions and destinations.

### Usability
- [ ] The main task and primary action are obvious.
- [ ] Empty, loading, error, success, and disabled states are designed where relevant.
- [ ] Forms have labels, helper text where needed, and understandable validation.
- [ ] Mobile layout remains usable without routine horizontal scrolling.

### Security communication
- [ ] Security statuses reflect real application state.
- [ ] Pending and unknown states are not styled or worded as verified.
- [ ] Revocation limitations are explained where relevant.
- [ ] No private key, raw document key, or secret appears in URLs, visible logs, or error copy.
- [ ] Protected-resource errors do not disclose sensitive existence or policy details.
- [ ] Blockchain availability does not appear to control ordinary file access.

### Accessibility
- [ ] Keyboard focus is visible and logical.
- [ ] Text and meaningful controls have sufficient contrast.
- [ ] Icons have accessible names and status is not color-only.
- [ ] Dialogs and asynchronous status messages work with assistive technology.
- [ ] Reduced-motion preference is respected.

---

## 27. Handoff Notes for Google Stitch and Google Antigravity

### For Google Stitch
- Generate the landing page and core workspace screens using this document as the design source of truth.
- Prioritize a coherent shared system over one-off page concepts.
- Generate desktop and mobile layouts for core journeys.
- Keep file lists, sharing panels, audit states, and form components visually related.
- Use realistic placeholder content only for visual exploration; replace it with real application data during implementation.
- Do not add features or routes absent from `01-PRD.md` and `03-APP-FLOW.md`.

### For Google Antigravity
- Implement shared tokens and reusable components before polishing individual pages.
- Preserve the interaction and security-state semantics described here.
- Connect status badges to real state; do not hard-code “Verified,” “Encrypted,” or “Anchored” as decorative copy.
- Keep cryptographic operations and authorization decisions out of presentational components.
- Test responsive layout, keyboard interaction, reduced motion, loading/error states, and dark mode if implemented.
- Treat `01-PRD.md`, `02-TRD.md`, and `03-APP-FLOW.md` as functional/technical constraints; this document governs visual and interaction consistency.

---

## Final Design Principle

**DropSafe should feel simple to use and precise about security.** The interface must make ordinary file tasks easy while clearly distinguishing what is encrypted, what access is allowed, what was verified, and what remains pending or unknown.
