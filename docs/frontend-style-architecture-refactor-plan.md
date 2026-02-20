# Frontend Style Architecture Refactor Plan

Last updated: 2026-02-20

## Goal
- Make frontend styling maintainable and scalable for more associations.
- Preserve legacy visual parity while refactoring.
- Reduce global CSS coupling and mixed responsibilities in route files/components.

## Chosen Direction
- Refactor strategy: phased.
- Styling baseline: CSS Modules + typed theme tokens.
- Bootstrap policy: keep for nav/offcanvas/forms initially, reduce usage elsewhere gradually.

## Why Refactor Is Needed
- Global style surface is large (`frontend/app/styles/*` is ~2664 lines across 6 files).
- Association overrides, variant overrides, and generic primitives are mixed in the same files.
- Theme token + brand fallback logic lives directly in `frontend/app/layout.tsx`.
- Large route/component files combine data logic, layout, variant selection, and visual behavior.

## Target Architecture
1. Theme layer
- `frontend/lib/theme/` with typed helpers for:
  - brand normalization
  - legacy token bridge
  - runtime CSS variable generation
  - UI profile resolution per association

2. Styling layer
- Keep globals thin:
  - foundation/reset
  - app-shell/layout primitives
  - temporary legacy compat bridge
- Move feature styles to CSS Modules:
  - `features/home/*.module.css`
  - `features/events/*.module.css`
  - `features/members/*.module.css`
  - `features/layout/*.module.css`

3. Component layer
- Keep route files thin (data + composition only).
- Move heavy presentation logic to feature components.
- Split variant-heavy event detail rendering into variant-specific components with a registry.

## Phased Plan

### Phase 0: Baseline and Guardrails
- Freeze parity baselines with Playwright chunked runs for `home`, `events`, `members-auth`.
- Add style architecture rules and migration checklist.

### Phase 1: Extract Theme Logic (No Visual Change)
- Move brand token fallback map and style-var builder out of `layout.tsx` into `frontend/lib/theme`.
- Keep generated CSS vars identical.
- Add explicit body data attributes for future profile-based styling.

### Phase 2: Header/Footer Modularization
- Migrate header/footer styling from global files to scoped modules.
- Keep current Bootstrap behavior intact.

### Phase 3: Homepage Modularization
- Split homepage into feature components and scoped styles.
- Isolate association-specific hero/news/events/partner variants.

### Phase 4: Events Modularization
- Replace monolithic event variant rendering with registry + per-variant components.
- Migrate event styles to feature-scoped modules.

### Phase 5: Shared UI Primitives + Members
- Introduce reusable shell/surface/form primitives.
- Migrate member pages/forms off global-only styling.

### Phase 6: Cleanup
- Remove obsolete global selectors and compat blocks.
- Keep only intentional global tokens/foundation/app-shell layers.

## Progress
- [x] Phase 1 started
- [x] Plan documented
- [x] Phase 2
- [x] Phase 3
- [x] Phase 4
- [x] Phase 5
- [x] Phase 6

## Implemented In This Change
- Theme/brand style-variable extraction from `frontend/app/layout.tsx` into `frontend/lib/theme/`.
- Body association/profile metadata hooks for future scoped theming.
- Header/footer styling moved to component-scoped CSS modules.
- Redundant global header/footer CSS blocks removed from `frontend/app/styles/base.css`.
- Homepage route split into feature components:
  - `frontend/features/home/home-page-view.tsx`
  - `frontend/features/home/home-hero.tsx`
  - `frontend/features/home/home-news-feed.tsx`
  - `frontend/features/home/legacy-sections.tsx`
- Homepage layout shell/grid/about sections migrated from global stylesheet to scoped module:
  - `frontend/features/home/home-page-view.module.css`
  - Duplicated layout selectors removed from `frontend/app/styles/home.css`.
- Homepage news-feed block migrated to scoped module:
  - `frontend/features/home/home-news-feed.module.css`
  - Duplicated feed/header/AA icon selectors removed from `frontend/app/styles/home.css`.
- Homepage hero block migrated to scoped module:
  - `frontend/features/home/home-hero.module.css`
  - Hero animation, logo sizing, and brand-specific hero overrides moved out of `frontend/app/styles/home.css`.
- Homepage legacy event/partner blocks migrated to scoped module:
  - `frontend/features/home/legacy-sections.module.css`
  - Event card visuals, partner carousel layout, and association-specific carousel animation moved out of globals.
- `frontend/app/styles/home.css` reduced to a small compatibility layer (shared link/heading/calendar selectors only).
- Events detail prep refactor:
  - Extracted event variant hash/navigation/date helpers into
    `frontend/components/events/event-variant-helpers.ts`
  - `frontend/components/events/event-variant-detail.tsx` now consumes shared helpers (no visual behavior change).
- Events detail split step:
  - Extracted default, tomtejakt, and themed event detail renderers into:
    - `frontend/components/events/event-variant-default.tsx`
    - `frontend/components/events/event-variant-tomtejakt.tsx`
    - `frontend/components/events/event-variant-themed.tsx`
  - `frontend/components/events/event-variant-detail.tsx` now focuses on state/hash orchestration and delegates rendering.
- Events detail header/nav split:
  - Extracted variant header + nav rendering into
    `frontend/components/events/event-variant-header.tsx`
  - Added shared nav item type in
    `frontend/components/events/event-variant-helpers.ts`
- Events detail content/shell split:
  - Added reusable shell wrapper: `frontend/components/events/event-detail-shell.tsx`
  - Extracted themed content sections to:
    `frontend/components/events/event-variant-sections.tsx`
  - Default/tomtejakt/themed variant components now share the same shell wrapper and have less duplicated markup.
- Events detail navigation state split:
  - Added `frontend/components/events/use-event-variant-navigation.ts` for hash/nav/active-section logic.
  - `frontend/components/events/event-variant-detail.tsx` now delegates navigation state to the hook and remains an orchestration layer.
- Events default detail style split:
  - Added `frontend/components/events/event-variant-default.module.css`
  - Migrated default event-detail content/link/color overrides from global `frontend/app/styles/events.css`
    to scoped module and wired in `frontend/components/events/event-variant-default.tsx`.
- Events index split step:
  - Extracted events index view and formatting helpers into:
    - `frontend/features/events/events-index-view.tsx`
    - `frontend/features/events/events-utils.ts`
  - `frontend/app/events/page.tsx` is now a thin data/composition route.
- Events index style split step:
  - Added `frontend/features/events/events-index-view.module.css`
  - Migrated events-index card/past-link styles from `frontend/app/styles/events.css` to scoped module.
- Events signup form style split step:
  - Added/expanded `frontend/components/events/event-signup-form.module.css`
  - Wired module-scoped classes in `frontend/components/events/event-signup-form.tsx`
    for form layout, input/select/button styling, fieldset reset, and summary section spacing.
  - Removed remaining global signup-form selectors from `frontend/app/styles/events.css`
    (`.event-signup-form*` and `.form-fieldset` under `.event-detail-page`).
- Events attendee list style split step:
  - Added `frontend/components/events/event-attendee-list.module.css`
  - Wired attendee table/header/wrap classes in `frontend/components/events/event-attendee-list.tsx`.
  - Removed global attendee table selectors from `frontend/app/styles/events.css`
    (`#attendees-header`, `.attendee-table*` under `.event-detail-page`).
- Events variant shell style split completion:
  - Added `frontend/components/events/event-variant-themed.module.css`
  - Added `frontend/components/events/event-variant-tomtejakt.module.css`
  - Migrated themed variant and tomtejakt-specific style logic out of global
    `frontend/app/styles/events.css` into scoped modules.
  - Updated event variant components to consume module classes:
    - `frontend/components/events/event-variant-themed.tsx`
    - `frontend/components/events/event-variant-header.tsx`
    - `frontend/components/events/event-variant-sections.tsx`
    - `frontend/components/events/event-variant-tomtejakt.tsx`
  - Removed now-obsolete nav helper class builders from
    `frontend/components/events/event-variant-helpers.ts`.
- Shared auth UI primitive (Phase 5 start):
  - Added reusable auth shell:
    - `frontend/components/ui/auth-shell.tsx`
    - `frontend/components/ui/auth-shell.module.css`
  - Migrated members auth routes to use shared shell:
    - `frontend/app/members/login/page.tsx`
    - `frontend/app/members/signup/page.tsx`
    - `frontend/app/members/password_reset/page.tsx`
    - `frontend/app/members/reset/[uid]/[token]/page.tsx`
  - Added scoped login form module:
    - `frontend/components/members/login-form.module.css`
    - `frontend/components/members/login-form.tsx`
- Global cleanup (Phase 6 start):
  - Removed obsolete members style import from `frontend/app/globals.css`.
  - Removed obsolete `frontend/app/styles/members.css` after migration.
  - Removed obsolete members layout selectors from `frontend/app/styles/base.css`
    and switched to auth-shell-based layout targeting.
  - Updated E2E locator for login snapshot:
    `frontend/tests/e2e/legacy-visual.spec.ts` now uses `data-testid="auth-shell-card"`.
- Members page surface modularization (Phase 5 completion):
  - Added members page surface module:
    `frontend/features/members/members-page.module.css`.
  - Migrated members page shells/hero/panel/layout styling from global utility classes
    to members-scoped module in:
    - `frontend/app/members/page.tsx`
    - `frontend/app/members/profile/page.tsx`
    - `frontend/app/members/functionaries/page.tsx`
    - `frontend/app/members/password_change/page.tsx`
    - `frontend/app/members/password_change/done/page.tsx`
    - `frontend/app/members/password_reset/done/page.tsx`
    - `frontend/app/members/reset/done/page.tsx`
    - `frontend/app/members/cert/page.tsx`
    - `frontend/app/members/activate/[uid]/[token]/page.tsx`
- Members component modularization (Phase 5 completion):
  - Added `frontend/components/members/functionary-manager.module.css`
  - Updated `frontend/components/members/functionary-manager.tsx` to use scoped list/row/inline-action styles.
- Additional global cleanup (Phase 6 completion):
  - Removed obsolete shared selectors from `frontend/app/styles/shared.css`:
    - `.legacy-panel`
    - `.table-wrap`
    - `.attendee-table*`
    - `.is-hidden`
    - `.event-variant-shell`
