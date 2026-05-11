# Social Development Notes

## Responsibility
`social` is now a compatibility app for legacy public URLs.

## Routes
- `/social/` renders the existing placeholder page.
- `/social/harassment/` delegates to `harassment.views.harassment_form` while preserving the `social:harassment` reverse name used by templates.

## Split Apps
- Instagram embeds live in `instagram`.
- Harassment reporting lives in `harassment`.

## Migration Notes
- The legacy social models were copied into their focused apps.
- The legacy social database tables are dropped by the split migration after data is copied.
