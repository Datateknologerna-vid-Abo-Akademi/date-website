# Stage 1: install dependencies (needs build tools for compiled extensions)
FROM python:3.14-alpine AS builder
RUN apk add --no-cache gcc musl-dev libffi-dev
COPY --from=ghcr.io/astral-sh/uv:0.12.1 /uv /usr/local/bin/uv
WORKDIR /code
COPY pyproject.toml uv.lock ./
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Stage 2: lean runtime image (no build tools). Native wheels bundle their
# own libs (psycopg2, cryptography, pillow), so no LDAP/SASL/OpenSSL system
# packages are needed at runtime.
FROM python:3.14-alpine
RUN apk add --no-cache bash gettext
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PATH="/opt/venv/bin:$PATH"
COPY --from=builder /opt/venv /opt/venv
WORKDIR /code
COPY . /code/
RUN python manage.py compilemessages -l en -l fi -l sv
# Collect static at build time for every association, each into its own tree
# under /code/static-collected/<variant>. Each variant's STATICFILES_DIRS
# produce variant-specific collected output (e.g. date/css/homepage.css
# differs per association), so a single merged tree would not work; separate
# roots keep one generic image that serves every variant without startup
# collection. Settings pick the tree matching the runtime PROJECT_NAME.
ARG PROJECT_NAME=date
ENV PROJECT_NAME=$PROJECT_NAME
# Prod runs the unfold admin skin (USE_UNFOLD=True via extraEnv) on the date
# (incl. qa), pulterit, sf and impuls variants; kk, biocum and demo keep the
# stock admin. collectstatic only discovers app static dirs for apps in
# INSTALLED_APPS, so unfold's files must be collected with USE_UNFOLD=True or
# every unfold admin template render 500s on the missing manifest entry
# (2026-08-30).
RUN for variant in date kk pulterit biocum sf impuls demo; do \
      echo "Collecting static for ${variant}"; \
      case "${variant}" in \
        date|pulterit|sf|impuls) UNFOLD=True ;; \
        *) UNFOLD=False ;; \
      esac; \
      USE_UNFOLD="${UNFOLD}" PROJECT_NAME="${variant}" STATIC_ROOT="/code/static-collected/${variant}" \
        python manage.py collectstatic --noinput --clear || exit 1; \
    done
# The trees share ~99% of their files (common assets plus third-party static
# such as CKEditor), so deduplicate identical files with hardlinks: ~350 MiB
# of collected output collapses to ~55 MiB on disk. The source static/ dir is
# then removed; it is only input for collectstatic, and prod serves the
# collected trees (dev compose bind-mounts the repo). Any release-time static
# upload (S3) must push these trees, not re-run collectstatic from sources.
RUN python scripts/dedup_static.py /code/static-collected \
 && rm -rf static/
