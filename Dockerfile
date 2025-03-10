FROM python:3.13-alpine
RUN apk add --no-cache gcc musl-dev libffi-dev libldap libsasl libressl bash 
ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1
RUN mkdir /code
WORKDIR /code

ADD requirements.txt /code/
RUN pip install -r requirements.txt

ADD . /code/
