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

## Implemented Routes
- `/`
- `/news`
- `/news/[slug]`
- `/events`
- `/events/[slug]`
- `/pages/[slug]`
- `/members`
- `/members/login`
- `/members/profile`
- `/members/functionaries`
- `/polls`
- `/polls/[id]`
