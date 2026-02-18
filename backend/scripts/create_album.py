"""
Usage:
    python scripts/create_album.py title dir/

Docker usage:
    docker-compose run -v host/dir:code/img:ro web python scripts/create_album.py title img/
"""
import datetime
import sys
import os
import django
from django.core.files import File


sys.path.append("/code")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings.date")
django.setup()

from archive.models import Picture, Collection

collection = Collection(
    title=sys.argv[1],
    type="Pictures",
    pub_date=datetime.datetime.now(tz=datetime.timezone.utc)
)
collection.save()

print("created collection")

for root, _, files in os.walk(sys.argv[2]):
    for file in files:
        with open(os.path.join(root, file), 'rb') as file_obj:
            print(f"Uploading {file}")
            pic = Picture.objects.create(
                collection=collection,
                image=File(file_obj, file)
            )
            pic.save()
