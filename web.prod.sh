#!/bin/bash

python /code/manage.py migrate --noinput
python manage.py collectstatic --noinput
gunicorn -w 3 --max-requests 1000 --max-requests-jitter 100 --bind=0.0.0.0 core.wsgi