#!/bin/bash
python manage.py loaddata fixtures/members.json
python manage.py loaddata fixtures/staticpages.json
python manage.py loaddata fixtures/news.json
python manage.py loaddata fixtures/events.json
python manage.py loaddata fixtures/polls.json
python manage.py loaddata fixtures/ads.json
python manage.py loaddata fixtures/archive.json
