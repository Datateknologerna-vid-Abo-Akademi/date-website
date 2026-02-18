#!/bin/bash
python manage.py loaddata fixtures/members.json
python manage.py loaddata fixtures/ads.json

# Generate and load all dynamic fixtures (news, events, polls, ctf, publications, social, staticpages, archive)
python scripts/generate_dynamic_fixtures.py
python manage.py loaddata fixtures/dynamic.json