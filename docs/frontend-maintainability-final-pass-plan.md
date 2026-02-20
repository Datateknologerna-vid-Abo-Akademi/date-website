# Frontend Maintainability Final Pass Plan

## Summary
The frontend has improved significantly (`home/events/members` feature modules, theme extraction, event variant decomposition), but maintainability risk remains due to broad global CSS and cross-domain utility class coupling.  
This pass standardizes remaining domains onto feature-scoped modules and shrinks globals to foundation-only.

## Scope
- In scope:
  - `ctf`, `polls`, `archive`, `ads`, `publications`, `social`, `alumni` route surfaces
  - shared layout/form/list primitives
  - global CSS reduction (`base.css`, `shared.css`, `events.css`)
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
5. Keep `app/styles/shared.css` only for:
   - rich-content CKEditor rendering defaults (temporary global contract)
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
   - Remove migrated selectors from `shared.css` and `base.css` immediately after each domain migration.
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
   - `shared.css` contains only approved global layers (rich-content + minimal cross-cutting primitives if still needed).
4. Usage checks:
   - `rg` confirms no leftover legacy utility-class usage in migrated domains.

## Assumptions and Defaults
1. Strategy: broad coordinated pass, not incremental mini-releases.
2. Existing visual parity is preserved; any visual differences are regressions unless explicitly accepted.
3. Bootstrap remains for navbar/offcanvas until a separate UI framework removal plan.
4. CKEditor-rendered content remains globally styled until a separate rich-content isolation pass.
