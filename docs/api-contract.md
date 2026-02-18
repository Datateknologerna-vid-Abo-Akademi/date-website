# API Contract (v1)

Base path: `/api/v1`

## Envelope
- Success: `{ "data": ... }`
- Error: `{ "error": { "code": string, "message": string, "details"?: object } }`

## Implemented Endpoints

### Meta and Session
- `GET /meta/site`
- `GET /auth/session`
- `POST /auth/login`
- `POST /auth/logout`
- `POST /auth/signup`

### Home
- `GET /home`
  - Includes homepage events/news, ads, instagram post references, and calendar events.

### News
- `GET /news`
  - Query params:
    - `category=<slug>`
    - `category=none` (uncategorized)
    - `author=<username>`
- `GET /news/{slug}`
  - Optional query: `category=<slug>`

### Events
- `GET /events`
  - Query: `include_past=true|false`
- `GET /events/{slug}`
- `POST /events/{slug}/passcode`
- `POST /events/{slug}/signup`

### Static Pages
- `GET /pages/{slug}`

### Members
- `GET /members/me`
- `PATCH /members/me`
- `GET /members/functionary-roles`
- `GET /members/functionaries`
  - Query params:
    - `year=<YYYY|all>`
    - `role=<id|title|all>`
- `GET /members/me/functionaries`
- `POST /members/me/functionaries`
- `DELETE /members/me/functionaries/{functionary_id}`

### Polls
- `GET /polls`
- `GET /polls/{id}`
- `GET /polls/{id}/results`
- `POST /polls/{id}/vote`
  - JSON body: `{ "choice_ids": number[] }`

## Notes
- API uses Django session authentication (`SessionAuthentication`).
- CSRF cookie is set via `GET /auth/session`.
- Event signup endpoint validates the dynamic event form fields and optional captcha.
