import sys, os ,django, logging
sys.path.append("/code")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

import schedule
import time
import instaloader

from itertools import islice
from django.shortcuts import render
from social.models import IgUrl
from datetime import datetime

logger = logging.getLogger('date')

SCHEDULED_TIME = '00:00'

logger.info("STARTING IG SCHEDULER")

def updateIg():
    logger.info("IGSCHEDULER WORKING")
    logger.info(datetime.now())
    L = instaloader.Instaloader()
    igProfile = instaloader.Profile.from_username(L.context, "kemistklubben")
    posts = igProfile.get_posts()
    top40 = islice(posts, 40)

    IgUrl.objects.all().delete()

    for post in top40:
        u = IgUrl(url=post.url,shortcode=post.shortcode)
        u.save()

schedule.every().day.at(SCHEDULED_TIME).do(updateIg)

while True:
    schedule.run_pending()
    time.sleep(60)

