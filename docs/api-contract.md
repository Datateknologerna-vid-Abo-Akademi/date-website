# API Contract (v1)

Base path: `/api/v1`

## Envelope
- Success: `{ "data": ... }`
- Error: `{ "error": { "code": string, "message": string, "details"?: object } }`

## Implemented Endpoints

### Meta and Session
- `GET /meta/site`
  - Includes:
    - `enabled_modules` for association-specific module availability.
    - `default_landing_path` for associations that do not use `/` as homepage.
- `GET /auth/session`
- `POST /auth/login`
- `POST /auth/logout`
- `POST /auth/signup`
- `GET /auth/activate/{uidb64}/{token}`
- `POST /auth/password-reset`
- `POST /auth/password-reset/{uidb64}/{token}`
- `POST /auth/password-change`

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
- `GET /news/feed`

### Events
- `GET /events`
  - Query: `include_past=true|false`
- `GET /events/feed`
- `GET /events/{slug}`
  - Includes:
    - `captcha` (boolean) for signup flow requirements.
    - `template_variant` for frontend event-layout selection.
    - `show_attendee_list` for attendee visibility behavior.
- `GET /events/{slug}/attendees`
  - Includes:
    - `template_variant`
    - `show_attendee_list`
    - `sign_up_max_participants`
    - `registration_public_fields`
    - `attendees` with anonymized display names and waitlist markers.
- `POST /events/{slug}/passcode`
- `POST /events/{slug}/signup`
  - Success payload includes:
    - `registered`
    - `attendee_email`
    - `event_slug`
    - `billing`:
      - `enabled`
      - `status` (`disabled`, `not_configured`, `invoice_created`, `no_invoice_generated`, `processing_error`)
      - `invoice` (nullable object with `invoice_number`, `reference_number`, `invoice_date`, `due_date`, `amount`, `currency`)

### Static Pages
- `GET /pages/{slug}`

### Ads
- `GET /ads`

### Social
- `GET /social`
- `POST /social/harassment`
  - JSON body:
    - `message` (required)
    - `email` (optional)
    - `consent` (required boolean)
    - `cf-turnstile-response` (required when captcha is enabled)

### CTF
- `GET /ctf` (authenticated)
- `GET /ctf/{slug}` (authenticated)
- `GET /ctf/{ctf_slug}/{flag_slug}` (authenticated)
- `POST /ctf/{ctf_slug}/{flag_slug}/guess` (authenticated)
  - JSON body: `{ "guess": string }`

### Lucia
- `GET /lucia`
- `GET /lucia/candidates` (authenticated)
- `GET /lucia/candidates/{slug}` (authenticated)

### Alumni
- `POST /alumni/signup`
- `POST /alumni/update`
- `GET /alumni/update/{token}`
- `POST /alumni/update/{token}`

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

### Archive
- `GET /archive/pictures/years`
- `GET /archive/pictures/{year}`
- `GET /archive/pictures/id/{collection_id}`
- `GET /archive/pictures/{year}/{album}`
  - Query: `page=<n>`
- `GET /archive/documents`
  - Query:
    - `collection=<id>`
    - `title_contains=<text>`
    - `page=<n>`
- `GET /archive/exams`
- `GET /archive/exams/{collection_id}`
  - Query: `page=<n>`

### Publications
- `GET /publications`
  - Query: `page=<n>`
- `GET /publications/{slug}`

## Notes
- API uses Django session authentication (`SessionAuthentication`).
- CSRF cookie is set via `GET /auth/session`.
- Event signup endpoint validates the dynamic event form fields and optional captcha.
- Enabled modules are exposed per association via `enabled_modules` (for example `events`, `news`,
  `archive`, `ads`, `social`, `polls`, `publications`, `ctf`, `lucia`, `alumni`, `billing`).
