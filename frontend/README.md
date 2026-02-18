# Frontend

Next.js App Router frontend for the decoupled website architecture.

## Local (without Docker)
1. Install deps:
   - `npm install`
2. Start dev server:
   - `npm run dev`
3. Configure backend proxy target if needed:
   - `BACKEND_API_ORIGIN=http://localhost:8000`

## Docker
Use the root-level stack:
- `source ../env.sh dev`
- `stack-start`

## API Usage
- Frontend reads from `/api/v1/*`.
- Runtime site and theme config comes from:
  - `GET /api/v1/meta/site`
- Module availability per association is exposed via:
  - `meta.site.data.enabled_modules`
- Association landing route is exposed via:
  - `meta.site.data.default_landing_path`
- Event detail route includes decoupled passcode/signup flow against:
  - `POST /api/v1/events/{slug}/passcode`
  - `POST /api/v1/events/{slug}/signup` (with billing status in response when enabled)
  - `GET /api/v1/events/{slug}/attendees` (anonymized attendee list + waitlist markers)

## Implemented Routes
- `/`
- `/news`
- `/news/[slug]`
- `/news/articles/[slug]`
- `/news/author/[author]`
- `/news/[slug]/[article]`
- `/news/feed` (route handler)
- `/events`
- `/events/[slug]`
- `/events/feed` (route handler)
- `/pages/[slug]`
- `/members`
- `/members/login`
- `/members/signup`
- `/members/activate/[uid]/[token]`
- `/members/password_reset`
- `/members/reset/[uid]/[token]`
- `/members/password_change`
- `/members/profile`
- `/members/functionaries`
- `/polls`
- `/polls/[id]`
- `/archive`
- `/archive/pictures`
- `/archive/pictures/[year]`
- `/archive/pictures/[year]/[album]`
- `/archive/documents`
- `/archive/exams`
- `/archive/exams/[id]`
- `/publications`
- `/publications/[slug]`
- `/ads`
- `/social`
- `/social/harassment`
- `/ctf`
- `/ctf/[slug]`
- `/ctf/[slug]/[flag]`
- `/lucia`
- `/lucia/candidates`
- `/lucia/candidates/[slug]`
- `/alumni`
- `/alumni/signup`
- `/alumni/update`
- `/alumni/update/[token]`
