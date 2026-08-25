# Direct-to-Storage Uploads (Uppy)

## Purpose

Large uploads (gallery photos, exam files, archive documents) previously
traveled as multipart POST bodies through the web process before reaching
S3-compatible storage. On the production cluster this strains the small web
pods. With direct uploads, the browser PUTs files straight to the
S3-compatible endpoint (Backblaze B2 in production) using short-lived
presigned URLs; the web process only issues the signatures and later moves the
object from a temp key to its final key with a server-side copy.

The feature is built on Uppy (vendored under `static/common/uploads/vendor/`,
see the license notice in `LICENSE-NOTICE.md`).

## How it fits together

1. Forms that upload files use `DirectUploadField` (see `core/upload_widgets.py`).
   When enabled it renders a Uppy Dashboard container plus a hidden input;
   when disabled it degrades to the classic multi-file input, so local and
   self-hosted setups behave exactly as before.
2. `POST /_uploads/sign/` (`core/uploads.py`, mounted by
   `core/urls/common.py` for every association) validates the request and
   returns a presigned PUT URL for a server-generated key under `tmp/`.
   Scopes mirror the existing access gates:

   | Scope | Allowed | Gate |
   |---|---|---|
   | `gallery` | images | `gallery.add_album` or `archive.add_collection` permission |
   | `gallery-admin` | images | staff |
   | `exambank` | images, documents | same gate as the exam bank (`ExamBankAccessSettings`) |
   | `admin` | images, documents | staff |

3. The browser uploads directly to the S3 endpoint (CORS on the bucket allows
   the site origin). On form submit the hidden input carries the temp keys;
   the app's save path calls `core.uploads.finalize_upload`, which copies the
   temp object to the model's final key (`<year>/<album>/...` etc., computed
   by the same `upload_to` callables as before) and deletes the temp object.
   No file bytes ever pass through the web process.

4. Gallery photos are compressed client-side (`@uppy/compressor`, 1600px,
   quality 60) before upload, matching the previous server-side behaviour in
   `Photo.save()`. Direct-uploaded photos set `Photo._skip_compress` so the
   server does not re-resize them.

## Enabling (per deployment)

- `USE_S3=True` (required).
- `DIRECT_UPLOADS_ENABLED=True` (Helm: `media.s3.directUploadsEnabled`, env:
  `DIRECT_UPLOADS_ENABLED`). Defaults to `False`; when off, all upload forms
  keep the classic file inputs.
- Buckets must allow the browser to PUT from the site origin and must expire
  abandoned temp objects. Applied once per bucket with the B2 CLI
  (current state as of 2026-08, all 10 assoc buckets):

  ```json
  // CORS
  [{
    "corsRuleName": "uppy-uploads",
    "allowedOrigins": ["https://<site-domain>", ...],
    "allowedHeaders": ["Authorization", "Content-Type", "x-amz-date", "x-amz-content-sha256", "X-Requested-With"],
    "allowedOperations": ["s3_put", "s3_get", "s3_head"],
    "exposeHeaders": ["ETag", "Location"],
    "maxAgeSeconds": 3600
  }]
  ```

  ```json
  // Lifecycle: expire temp uploads that were never attached to a model row
  [{
    "fileNamePrefix": "tmp/",
    "daysFromUploadingToHiding": 1,
    "daysFromHidingToDeleting": 1,
    "daysFromStartingToCancelUnfinishedLargeFiles": 3
  }]
  ```

  The exact commands used to apply these live in the operator repository's
  B2 documentation; the previous bucket state was dumped to
  `transfers/uppy-b2-backup/<bucket>.json` on the dev-mgmt workstation before
  applying.

## Security model

- The signing endpoint requires the scope's gate (session + permission, or the
  exam-bank gate which also covers open/password-session access); CSRF stays
  on (JS sends the cookie token). Sign requests are rate limited with a
  fixed-window counter in the cache, per user for authenticated callers and
  per `REMOTE_ADDR` for anonymous ones (behind the load balancer that is the
  proxy address, so anonymous visitors share one bucket per deployment).
  Limits are per scope (`SIGN_RATE_LIMITS` in `core/uploads.py`, staff scopes
  higher for bulk admin uploads); the limiter runs after the scope gate, fails
  open when the cache is unavailable, and a 429 is surfaced to the client as a
  failed upload.
- Extension allowlist and per-scope size caps are enforced server-side in
  `sign_upload`; Uppy `restrictions` are UX only.
- Keys are always `tmp/<32 hex>.<ext>` generated server-side. Finalization
  re-validates the canonical pattern, so the hidden-form payload can never be
  used to copy or delete arbitrary objects (existing media keys do not match
  the pattern, and the 128-bit random tokens cannot be forged).
- The hidden payload is validated per scope at form clean time: canonical key
  pattern, extension consistency with the file name, positive integer size
  within the scope cap, bounded entry count.
- Presigned URLs expire after 5 minutes (`SIGNATURE_EXPIRES`) and are bearer
  tokens: never log them.
- Finalization `head_object`s the temp object and rejects a size mismatch with
  the declared value before copying, so the client-supplied size cannot be
  understated to bypass the caps. It then reads only the first 512 bytes (a
  ranged GET) and verifies the magic bytes match the declared extension
  (jpeg/png/webp/gif, pdf, zip-family office files, 7z, rar, gz, tar), so
  mislabeled content never reaches the final media paths. The copy is a
  server-side `copy_object` within the same bucket, resolved through the
  storage's collision-free name (`get_available_name`, same semantics as
  classic uploads); it carries the same ACL and object parameters that
  django-storages applies on classic writes (public-bucket files stay
  `public-read`). The temp object is then deleted.
- A missing temp object (already finalized or expired by the lifecycle rule)
  or a failed magic-byte check raises `ValueError`, which the upload views and
  admin forms surface as a skipped file with a warning instead of a 500.
- Temporary objects that are never finalized (abandoned forms, rejected
  copies) are cleaned by the bucket lifecycle rule.
- Collision handling uses the same `get_available_name` semantics as classic
  uploads (django-storages), including its inherent check-then-copy race for
  concurrent uploads of identically named files; the final copy wins, exactly
  as with classic form uploads.

## Known limits / follow-ups

- Single-PUT uploads only (B2 single PUT supports up to 5 GiB; scope caps are
  far below that). Multipart signing endpoints can be added later if ever
  needed.
- Gallery photos are compressed in the browser (downscale to 1600px, quality
  60). Allowed gallery formats are jpg/jpeg/png/webp; animated GIFs and
  camera-only formats (HEIC, TIFF) are not accepted through the direct path
  (classic uploads still accept them via Pillow). The stored file keeps its
  original extension even when the browser re-encodes the content.
- The form blocks submission while uploads are pending or failed; failed
  files must be removed before saving.
- Single-file admin fields (album thumbnails, publication PDFs, event and
  staticpage backgrounds, CKEditor inline images) still use the classic
  widget; the same machinery can be extended to them later.
- Bucket CORS and lifecycle rules were applied to all association buckets on
  2026-08-23; the media proxy Workers are unchanged (uploads go straight to
  the B2 endpoint, not through the Worker).
