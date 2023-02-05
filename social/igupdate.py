import logging
import os
import sys

import django

sys.path.append("/code")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

import time
from datetime import datetime
from itertools import islice

import instaloader
import schedule

from social.models import IgUrl

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
        u = IgUrl(url=post.url, shortcode=post.shortcode)
        u.save()


schedule.every().day.at(SCHEDULED_TIME).do(updateIg)

while True:
    schedule.run_pending()
    time.sleep(60)
