import logging
import os
import sys
import time
from datetime import datetime

import django
import schedule

sys.path.append("/code")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", f"core.settings.{os.environ.get('PROJECT_NAME') or 'date'}")
django.setup()

from django.core.management import CommandError, call_command

logger = logging.getLogger('date')

SCHEDULED_TIME = '00:00'


def updateIg():
    logger.info("IGSCHEDULER WORKING")
    logger.info(datetime.now())
    try:
        call_command("update_instagram")
    except CommandError as exc:
        logger.error("Instagram update failed: %s", exc)


def run_scheduler():
    logger.info("STARTING IG SCHEDULER")
    schedule.every().day.at(SCHEDULED_TIME).do(updateIg)

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    run_scheduler()
