# Frontend Maintainability Final Pass Plan

## Summary
The frontend has improved significantly (`home/events/members` feature modules, theme extraction, event variant decomposition), but maintainability risk remains due to broad global CSS and cross-domain utility class coupling.  
This pass standardizes remaining domains onto feature-scoped modules and shrinks globals to foundation-only.

## Scope
- In scope:
  - `ctf`, `polls`, `archive`, `ads`, `publications`, `social`, `alumni` route surfaces
  - shared layout/form/list primitives
  - global CSS reduction (`base.css`, `rich-content.css`, `legacy-forms.css`, `events.css`)
- Out of scope:
  - new feature work
  - visual redesign
  - mobile/responsive redesign pass (only parity-preserving structure cleanup)

## Architecture Decisions
1. Keep `app/*/page.tsx` files thin: fetch + compose only.
2. Keep domain styles in `features/<domain>/*.module.css`.
3. Keep reusable primitives in `components/ui/*` (+ modules).
4. Keep `app/styles/base.css` for:
   - tokens
   - reset
   - app-shell frame
   - minimal global element defaults
5. Keep split global layers in `app/styles/` by concern:
   - `shared-text.css` for minimal cross-cutting text helpers (`.meta`)
   - `rich-content.css` for CKEditor rendering defaults
   - `legacy-forms.css` for temporary cross-domain form utility compatibility
   - `news.css` and `legacy-media.css` until those domains are fully module-scoped
6. Keep `app/styles/events.css` only for:
   - truly route-global behavior that cannot be localized yet (temporary)
7. No new broad selectors like `div a`, `body:has(...)`, or domain-specific globals unless explicitly documented.

## Public Interfaces / Contracts to Add
1. `components/ui/page-shell.tsx` + `page-shell.module.css`
   - Props: `title`, `eyebrow?`, `meta?`, `children`, `compact?`
2. `components/ui/content-panel.tsx` + `content-panel.module.css`
   - Standard content surface wrapper.
3. `components/ui/form-primitives.module.css`
   - Exports class contracts used by forms:
     - `stack`
     - `grid`
     - `field`
     - `fieldset`
     - `choiceLine`
     - `inlineActions`
4. `components/ui/list-primitives.module.css`
   - Exports:
     - `list`
     - `listSpaced`
     - `rowLine`
     - `roleGrid`
5. `features/<domain>/<domain>-page.module.css` for each remaining domain.

## Implementation Steps
1. Create shared UI primitives/modules.
   - Add `page-shell`, `content-panel`, `form-primitives`, `list-primitives`.
   - Keep markup-compatible wrappers to minimize visual drift.
2. Migrate domain routes to feature modules (one domain folder at a time):
   - `ctf`, `polls`, `archive`, `ads`, `publications`, `social`, `alumni`.
   - Replace `page-shell/hero/panel/...` className usage with module/primitives.
3. Migrate domain components using global form/list classes.
   - Replace `form-stack/form-grid/form-field/...` and `list--spaced/row-line/...`.
   - Use UI primitive classes imported as module tokens.
4. Reduce globals.
   - Remove migrated selectors from split global layers and `base.css` immediately after each domain migration.
   - Keep rich-content global layer intact for CKEditor compatibility.
5. Events global tail cleanup.
   - Re-assess `events.css` remaining selectors.
   - Move localizable selectors into event modules; keep only unavoidable route-global behavior.
6. Documentation update.
   - Update `docs/frontend-style-architecture-refactor-plan.md` with each completed domain and removed global blocks.
   - Add “global CSS budget” section with allowed categories.

## Testing & Acceptance Criteria
1. Static checks:
   - ESLint passes on all touched files.
2. Visual regression:
   - Run existing chunked Playwright parity suite by domain:
     - `home`
     - `events`
     - `members-auth`
     - plus new chunks for `ctf/polls/archive/publications/alumni`
3. Structural checks (must pass):
   - No `members.css`.
   - No domain-specific selectors in `base.css`.
   - split global files contain only approved layers (rich-content + minimal cross-cutting primitives if still needed).
4. Usage checks:
   - `rg` confirms no leftover legacy utility-class usage in migrated domains.

## Assumptions and Defaults
1. Strategy: broad coordinated pass, not incremental mini-releases.
2. Existing visual parity is preserved; any visual differences are regressions unless explicitly accepted.
3. Bootstrap remains for navbar/offcanvas until a separate UI framework removal plan.
4. CKEditor-rendered content remains globally styled until a separate rich-content isolation pass.

## Progress Notes (Current)
- Added shared UI primitives:
  - `frontend/components/ui/page-shell.tsx`
  - `frontend/components/ui/page-shell.module.css`
  - `frontend/components/ui/content-panel.tsx`
  - `frontend/components/ui/content-panel.module.css`
  - `frontend/components/ui/form-primitives.module.css`
  - `frontend/components/ui/list-primitives.module.css`
- Migrated route surfaces in scope to `PageShell`/`PageHero`/`PagePanel`:
  - `ctf`, `polls`, `archive`, `ads`, `publications`, `social`, `alumni`
- Migrated in-scope forms/components to form/list primitives:
  - `components/ctf/flag-guess-form.tsx`
  - `components/polls/poll-vote-form.tsx`
  - `components/social/harassment-form.tsx`
  - `components/alumni/signup-form.tsx`
  - `components/alumni/update-form.tsx`
  - `components/alumni/update-request-form.tsx`
- Cleanup completed for now:
  - Removed unused selectors from previous shared global layer:
    - `.list--spaced`
    - `.link-grid`
    - `.form-inline`
    - `.row-line`
    - `.role-grid`
    - `.social-harassment-page .content form`
    - `.pagination-row`
- Additional migration/cleanup completed:
  - Migrated remaining `lucia` route surfaces and `frontend/app/not-found.tsx`
    from global `page-shell/hero/panel` classes to `PageShell` primitives.
  - Migrated `frontend/components/events/event-signup-form.tsx` invoice list
    from global `.list` to `list-primitives` (`listStyles.list`).
  - Split former `frontend/app/styles/shared.css` into concern-based files:
    - `frontend/app/styles/shared-text.css`
    - `frontend/app/styles/rich-content.css`
    - `frontend/app/styles/legacy-forms.css`
    - `frontend/app/styles/news.css`
    - `frontend/app/styles/legacy-media.css`
  - Removed obsolete global shell/surface utility blocks from:
    - `frontend/app/styles/base.css` (`.page-shell` and child selectors)
    - split shared global layers (removed from prior `shared.css` before split):
      - `.hero*`
      - `.panel*`
      - `.eyebrow`
      - `.content-grid`
      - `.cta-link`
      - `.home-entry-link*`
      - `.sr-only`
