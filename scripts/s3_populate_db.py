#Imports to get django setup
import os
import sys
import django

sys.path.append("/code")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

#Rest of the imports
import logging
import boto3
import datetime
import requests
import pytz

from django.conf import settings
from archive.models import Collection, Picture
from django.db import connection,transaction

FORBIDDEN_NAMES = ["documents", "cache"]

logger = logging.getLogger('date')

logger.info("STARTING IMAGE UPLOADER")

def s3_config():
    return boto3.client('s3',
            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY)

client = s3_config()

query_list = []
collection_list = []
year_list = []


response = client.list_objects(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Prefix=settings.PRIVATE_MEDIA_LOCATION + "/", Delimiter="/")

# Gets a list of years
for obj in response.get('CommonPrefixes'):
    year = obj.get('Prefix').replace(settings.PRIVATE_MEDIA_LOCATION,"").replace("/","")
    if year not in FORBIDDEN_NAMES:
        year_list.append(year)

for year in year_list:
    response = client.list_objects(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Prefix=settings.PRIVATE_MEDIA_LOCATION + f"/{year}/", Delimiter="/")
    album_year = int(year)
    # For every year, list containing albums
    for obj in response.get('CommonPrefixes'):
        album_name = obj.get('Prefix').replace(settings.PRIVATE_MEDIA_LOCATION + f"/{year}","").replace("/","")
        exists_check = Collection.objects.filter(title=album_name, pub_date__year=album_year).count()
        # check if album name not exists
        if exists_check == 0:
            logger.info("Album does not exist")
            # Create a collection from album name
            collection = Collection(title=album_name, type="Pictures", pub_date=datetime.datetime(album_year,1,1,10,10,tzinfo=pytz.timezone('Europe/Helsinki')))
            # If an album with same name in a specific year does not exist, save the collection
            collection.save()
            response = client.list_objects(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Prefix=settings.PRIVATE_MEDIA_LOCATION + f"/{year}/{album_name}")
            contents = response.get('Contents')
            # For every album, list its contents
            for data in contents:
                path = data["Key"].replace(settings.PRIVATE_MEDIA_LOCATION + "/", "")
                logger.info(path)
                picture_data = (path, False, collection.id)
                query_list.append(picture_data)


# Creates a connection to the database and inserts the query list to the correct table
cursor = connection.cursor()

query = ''' INSERT INTO archive_picture 
        (image, favorite, collection_id) 
        VALUES (%s,%s,%s) '''

cursor.executemany(query, query_list)
transaction.commit()

logger.info("IMAGE UPLOADER COMPLETE")
