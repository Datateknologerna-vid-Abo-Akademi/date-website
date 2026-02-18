# Route Migration Matrix

## Implemented in Decoupled Frontend
- `/` -> Next route `frontend/app/page.tsx` using `GET /api/v1/home`
- `/news` -> Next route `frontend/app/news/page.tsx` using `GET /api/v1/news`
- `/news/{slug}` -> Next route `frontend/app/news/[slug]/page.tsx` using `GET /api/v1/news/{slug}`
- `/news/articles/{slug}` -> Next route `frontend/app/news/articles/[slug]/page.tsx`
- `/news/author/{author}` -> Next route `frontend/app/news/author/[author]/page.tsx`
- `/news/{category}/{slug}` -> Next route `frontend/app/news/[slug]/[article]/page.tsx`
- `/news/feed` -> Next route handler `frontend/app/news/feed/route.ts` proxying `GET /api/v1/news/feed`
- `/events` -> Next route `frontend/app/events/page.tsx` using `GET /api/v1/events`
- `/events/{slug}` -> Next route `frontend/app/events/[slug]/page.tsx` using `GET /api/v1/events/{slug}`
  - Includes decoupled passcode + signup forms via `POST /api/v1/events/{slug}/passcode` and
    `POST /api/v1/events/{slug}/signup`
  - Includes attendee list via `GET /api/v1/events/{slug}/attendees`
- `/events/feed` -> Next route handler `frontend/app/events/feed/route.ts` proxying `GET /api/v1/events/feed`
- `/pages/{slug}` -> Next route `frontend/app/pages/[slug]/page.tsx` using `GET /api/v1/pages/{slug}`
- `/members` -> Next route `frontend/app/members/page.tsx` using `GET /api/v1/auth/session`
- `/members/login` -> Next route `frontend/app/members/login/page.tsx` using `POST /api/v1/auth/login`
- `/members/signup` -> Next route `frontend/app/members/signup/page.tsx` using `POST /api/v1/auth/signup`
- `/members/activate/{uid}/{token}` -> Next route `frontend/app/members/activate/[uid]/[token]/page.tsx` using
  `GET /api/v1/auth/activate/{uid}/{token}`
- `/members/password_reset*` -> Next routes under `frontend/app/members/password_reset/*` using
  `POST /api/v1/auth/password-reset`
- `/members/reset/{uid}/{token}` -> Next route `frontend/app/members/reset/[uid]/[token]/page.tsx` using
  `POST /api/v1/auth/password-reset/{uid}/{token}`
- `/members/password_change*` -> Next routes under `frontend/app/members/password_change/*` using
  `POST /api/v1/auth/password-change`
- `/members/profile` -> Next route `frontend/app/members/profile/page.tsx` using `GET/PATCH /api/v1/members/me`
- `/members/functionaries` -> Next route `frontend/app/members/functionaries/page.tsx` using
  `GET /api/v1/members/functionaries`, `GET/POST/DELETE /api/v1/members/me/functionaries*`
- `/members/info|funktionar|funktionarer` -> Next redirect compatibility routes to `/members/profile` or `/members/functionaries`
- `/polls` -> Next route `frontend/app/polls/page.tsx` using `GET /api/v1/polls`
- `/polls/{id}` -> Next route `frontend/app/polls/[id]/page.tsx` using
  `GET /api/v1/polls/{id}` and `POST /api/v1/polls/{id}/vote`
- `/archive` -> Next route `frontend/app/archive/page.tsx`
- `/archive/pictures` -> Next route `frontend/app/archive/pictures/page.tsx` using
  `GET /api/v1/archive/pictures/years`
- `/archive/pictures/{year}` -> Next route `frontend/app/archive/pictures/[year]/page.tsx` using
  `GET /api/v1/archive/pictures/{year}`
- `/archive/pictures/{year}/{album}` -> Next route
  `frontend/app/archive/pictures/[year]/[album]/page.tsx` using
  `GET /api/v1/archive/pictures/{year}/{album}`
- `/archive/pictures/id/{id}` -> Next route `frontend/app/archive/pictures/id/[id]/page.tsx` using
  `GET /api/v1/archive/pictures/id/{id}` then redirects to canonical year/album route
- `/archive/documents` -> Next route `frontend/app/archive/documents/page.tsx` using
  `GET /api/v1/archive/documents`
- `/archive/exams` -> Next route `frontend/app/archive/exams/page.tsx` using
  `GET /api/v1/archive/exams`
- `/archive/exams/{id}` -> Next route `frontend/app/archive/exams/[id]/page.tsx` using
  `GET /api/v1/archive/exams/{id}`
- `/publications` -> Next route `frontend/app/publications/page.tsx` using
  `GET /api/v1/publications`
- `/publications/{slug}` -> Next route `frontend/app/publications/[slug]/page.tsx` using
  `GET /api/v1/publications/{slug}`
- `/ads` -> Next route `frontend/app/ads/page.tsx` using `GET /api/v1/ads`
- `/social` -> Next route `frontend/app/social/page.tsx` using `GET /api/v1/social`
- `/social/harassment` -> Next route `frontend/app/social/harassment/page.tsx` using
  `POST /api/v1/social/harassment`
- `/ctf` -> Next route `frontend/app/ctf/page.tsx` using `GET /api/v1/ctf`
- `/ctf/{slug}` -> Next route `frontend/app/ctf/[slug]/page.tsx` using `GET /api/v1/ctf/{slug}`
- `/ctf/{slug}/{flag}` -> Next route `frontend/app/ctf/[slug]/[flag]/page.tsx` using
  `GET /api/v1/ctf/{slug}/{flag}` and `POST /api/v1/ctf/{slug}/{flag}/guess`
- `/lucia` -> Next route `frontend/app/lucia/page.tsx` using `GET /api/v1/lucia`
- `/lucia/candidates` -> Next route `frontend/app/lucia/candidates/page.tsx` using
  `GET /api/v1/lucia/candidates`
- `/lucia/candidates/{slug}` -> Next route `frontend/app/lucia/candidates/[slug]/page.tsx` using
  `GET /api/v1/lucia/candidates/{slug}`
- `/alumni` -> Next route `frontend/app/alumni/page.tsx`
- `/alumni/signup` -> Next route `frontend/app/alumni/signup/page.tsx` using
  `POST /api/v1/alumni/signup`
- `/alumni/update` -> Next route `frontend/app/alumni/update/page.tsx` using
  `POST /api/v1/alumni/update`
- `/alumni/update/{token}` -> Next route `frontend/app/alumni/update/[token]/page.tsx` using
  `GET/POST /api/v1/alumni/update/{token}`

## Special Event Parity
- Variant-aware event detail rendering is now handled in Next.js via `template_variant` with dedicated styles for:
  - `arsfest`
  - `baal`
  - `kk100`
  - `wappmiddag`
  - `tomtejakt`
- Hash compatibility for legacy variant sections is preserved:
  - `#/main`
  - `#/anmalan`
  - `#/attendee-list` (`#/anmalda` alias)

## Rollout Recommendation
1. Keep current Django pages available during transition.
2. Cut traffic to Next routes per route group after QA.
3. Remove unused Django template routes only after parity checks.

## Module Guarding
- Frontend module routes are guarded using `meta/site` capabilities (`module_capabilities`) to ensure association-safe routing.
