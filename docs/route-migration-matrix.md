# Route Migration Matrix

## Implemented in Decoupled Frontend
- `/` -> Next route `frontend/app/page.tsx` using `GET /api/v1/home`
- `/news` -> Next route `frontend/app/news/page.tsx` using `GET /api/v1/news`
- `/news/{slug}` -> Next route `frontend/app/news/[slug]/page.tsx` using `GET /api/v1/news/{slug}`
- `/events` -> Next route `frontend/app/events/page.tsx` using `GET /api/v1/events`
- `/events/{slug}` -> Next route `frontend/app/events/[slug]/page.tsx` using `GET /api/v1/events/{slug}`
- `/pages/{slug}` -> Next route `frontend/app/pages/[slug]/page.tsx` using `GET /api/v1/pages/{slug}`
- `/members` -> Next route `frontend/app/members/page.tsx` using `GET /api/v1/auth/session`
- `/members/login` -> Next route `frontend/app/members/login/page.tsx` using `POST /api/v1/auth/login`
- `/members/profile` -> Next route `frontend/app/members/profile/page.tsx` using `GET/PATCH /api/v1/members/me`
- `/members/functionaries` -> Next route `frontend/app/members/functionaries/page.tsx` using
  `GET /api/v1/members/functionaries`, `GET/POST/DELETE /api/v1/members/me/functionaries*`
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

## Still Django-Rendered (Pending API + Frontend Migration)
- `/ctf/*`
- `/social/*`
- `/alumni/*`
- `/lucia/*`
- app-specific custom event templates and some form workflows

## Rollout Recommendation
1. Keep current Django pages available during transition.
2. Cut traffic to Next routes per route group after QA.
3. Remove unused Django template routes only after parity checks.
