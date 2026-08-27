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
