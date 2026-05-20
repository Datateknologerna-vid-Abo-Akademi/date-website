"""
Usage:
    python scripts/create_album.py title dir/

Docker usage:
    docker-compose run -v host/dir:code/img:ro web python scripts/create_album.py title img/
"""

import datetime
import os
import sys

import django
from django.core.files import File

sys.path.append("/code")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings.date")
django.setup()

from gallery.models import Album, Photo

album = Album(title=sys.argv[1], pub_date=datetime.datetime.now(tz=datetime.UTC))
album.save()

print("created album")

for root, _, files in os.walk(sys.argv[2]):
    for file in files:
        with open(os.path.join(root, file), 'rb') as file_obj:
            print(f"Uploading {file}")
            pic = Photo.objects.create(album=album, image=File(file_obj, file))
            pic.save()
