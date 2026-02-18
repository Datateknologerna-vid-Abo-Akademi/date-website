FROM python:3.12.8-alpine3.20

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN apk add --no-cache \
    bash \
    gcc \
    libffi-dev \
    musl-dev \
    openssl-dev \
    postgresql-dev

WORKDIR /code

COPY requirements.txt /code/requirements.txt
RUN pip install --upgrade pip && pip install -r /code/requirements.txt

COPY . /code/
