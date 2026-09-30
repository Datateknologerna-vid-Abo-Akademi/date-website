import logging
import os
import sys
import time
from datetime import datetime
from itertools import islice

import django
import instaloader
import schedule

sys.path.append("/code")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings.date")
django.setup()

from instagram.models import IgUrl

logger = logging.getLogger('date')

SCHEDULED_TIME = '00:00'


def updateIg():
    logger.info("IGSCHEDULER WORKING")
    logger.info(datetime.now())
    loader = instaloader.Instaloader()
    ig_profile = instaloader.Profile.from_username(loader.context, "kemistklubben")
    top40 = islice(ig_profile.get_posts(), 40)

    IgUrl.objects.all().delete()

    for post in top40:
        IgUrl.objects.create(url=post.url, shortcode=post.shortcode)


def run_scheduler():
    logger.info("STARTING IG SCHEDULER")
    schedule.every().day.at(SCHEDULED_TIME).do(updateIg)

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    run_scheduler()
