# Stage 1: install dependencies (needs build tools for compiled extensions)
FROM python:3.14-alpine AS builder
RUN apk add --no-cache gcc musl-dev libffi-dev libldap libsasl libressl
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /code
COPY pyproject.toml uv.lock ./
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
RUN uv sync --frozen --no-dev --no-install-project

# Stage 2: lean runtime image (no build tools)
FROM python:3.14-alpine
RUN apk add --no-cache libldap libsasl libressl bash gettext
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PATH="/opt/venv/bin:$PATH"
COPY --from=builder /opt/venv /opt/venv
RUN mkdir /code
WORKDIR /code
ADD . /code/
RUN python manage.py compilemessages -l en -l fi -l sv
# Collect static at build time so web pods start without running
# collectstatic. The default image ships the date variant's assets;
# build with --build-arg PROJECT_NAME=<variant> for association-specific
# images (or enable collectstaticOnStartup in the chart for other variants).
ARG PROJECT_NAME=date
ENV PROJECT_NAME=$PROJECT_NAME
RUN python manage.py collectstatic --noinput
