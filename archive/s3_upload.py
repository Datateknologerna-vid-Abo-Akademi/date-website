
import os
import sys
import boto3
import datetime
import requests
import pytz

AWS_S3_ENDPOINT_URL = os.environ['AWS_S3_ENDPOINT_URL']
AWS_ACCESS_KEY_ID = os.environ['AWS_ACCESS_KEY_ID']
AWS_SECRET_ACCESS_KEY = os.environ['AWS_SECRET_ACCESS_KEY']
AWS_STORAGE_BUCKET_NAME = os.environ['AWS_STORAGE_BUCKET_NAME']
PRIVATE_MEDIA_LOCATION = os.environ['PRIVATE_MEDIA_LOCATION']


def s3_config():
    return boto3.client('s3',
            endpoint_url=AWS_S3_ENDPOINT_URL,
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY)

print("STARTING IMAGE UPLOADER")

client = s3_config()

path = input("enter folder year path: ")
album_list = []
for root,dirs,files in os.walk(path):
    #Loops through all directories in a directory

    for name in dirs:
        #Splits the path into a list and reverses it so that album is always split_path[0]
        path = os.path.join(root, name)
        split_path = path.split("/")
        split_path.reverse()

        #Splits the path and uses year and album name (path has to end with /<year>/<album_name>)
        album_name = split_path[0]
        #album_year = int(split_path[1])


        #Creates a collection from path (path has to end with /<year>/<album_name>) 

        album_list.append(album_name)

    for file in files:
        #Loops through every file in a directory
        
        path = os.path.join(root, file)
        #Splits the path and uses album name (path has to end with /<year>/<album_name>)
        split_path = path.split("/")

        # Do not include files from thumbnails folder
        if 'thumbs' != split_path[2]:
            split_path.reverse()

            for title in album_list:
                if title == split_path[1]:
                    with open(os.path.join(root,file), "rb") as f:
                        #Image content type had to be set in order to access img url. Currently set as "image/jpeg"
                        client.upload_fileobj(f, AWS_STORAGE_BUCKET_NAME, PRIVATE_MEDIA_LOCATION + "/" + os.path.join(root,file), ExtraArgs={'ContentType': 'image/jpeg'})
                        print(path + " uploaded")
            

print("IMAGE UPLOADER COMPLETE")
