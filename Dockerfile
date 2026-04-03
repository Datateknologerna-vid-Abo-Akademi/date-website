FROM python:3.14-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    build-essential \
    libffi-dev \
    libldap2-dev \
    libsasl2-dev \
    gettext \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*
ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1
RUN mkdir /code
WORKDIR /code

ADD requirements.txt /code/
RUN pip install -r requirements.txt

ADD . /code/
RUN python manage.py compilemessages
