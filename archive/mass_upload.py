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

logger = logging.getLogger('date')

logger.info("STARTING IMAGE UPLOADER")

def s3_config():
    return boto3.client('s3',
            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name='eu-north-1')

client = s3_config()

path = input("enter folder year path: ")
query_list = []
collection_list = []
for root,dirs,files in os.walk(path):
    #Loops through all directories in a directory

    for name in dirs:
        #Splits the path into a list and reverses it so that album is always split_path[0]
        path = os.path.join(root, name)
        split_path = path.split("/")
        split_path.reverse()

        #Splits the path and uses year and album name (path has to end with /<year>/<album_name>)
        album_name = split_path[0]
        album_year = int(split_path[1])

        #Creates a collection from path (path has to end with /<year>/<album_name>) 
        collection = Collection(title=album_name, type="Pictures", pub_date=datetime.datetime(album_year,1,1,10,10,tzinfo=pytz.timezone('Europe/Helsinki')))
        collection.save()
        collection_list.append(collection)

    for file in files:
        #Loops through every file in a directory
        
        path = os.path.join(root, file)
        #Splits the path and uses album name (path has to end with /<year>/<album_name>)
        split_path = path.split("/")
        split_path.reverse()

        for collection in collection_list:
            if collection.title == split_path[1]:
                picture_data = (path, False, collection.id)
                query_list.append(picture_data)
                with open(os.path.join(root,file), "rb") as f:
                    #Image content type had to be set in order to access img url. Currently set as "image/jpeg"
                    client.upload_fileobj(f, settings.AWS_STORAGE_BUCKET_NAME, "media/" + os.path.join(root,file), ExtraArgs={'ContentType': 'image/jpeg'})
            
# Creates a connection to the database and inserts the query list to the correct table
cursor = connection.cursor()

query = ''' INSERT INTO archive_picture 
        (image, favorite, collection_id) 
        VALUES (%s,%s,%s) '''

cursor.executemany(query, query_list)
transaction.commit()

logger.info("IMAGE UPLOADER COMPLETE")
