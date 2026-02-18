# Route Migration Matrix

## Implemented in Decoupled Frontend
- `/` -> Next route `frontend/app/page.tsx` using `GET /api/v1/home`
- `/news` -> Next route `frontend/app/news/page.tsx` using `GET /api/v1/news`
- `/news/{slug}` -> Next route `frontend/app/news/[slug]/page.tsx` using `GET /api/v1/news/{slug}`
- `/events` -> Next route `frontend/app/events/page.tsx` using `GET /api/v1/events`
- `/events/{slug}` -> Next route `frontend/app/events/[slug]/page.tsx` using `GET /api/v1/events/{slug}`
- `/pages/{slug}` -> Next route `frontend/app/pages/[slug]/page.tsx` using `GET /api/v1/pages/{slug}`

## Still Django-Rendered (Pending API + Frontend Migration)
- `/members/*`
- `/archive/*`
- `/polls/*`
- `/ctf/*`
- `/publications/*`
- `/social/*`
- `/alumni/*`
- `/lucia/*`
- app-specific custom event templates and some form workflows

## Rollout Recommendation
1. Keep current Django pages available during transition.
2. Cut traffic to Next routes per route group after QA.
3. Remove unused Django template routes only after parity checks.
