import os

from celery import Celery


os.environ.setdefault('DJANGO_SETTINGS_MODULE', f'core.settings.{os.environ.get("PROJECT_NAME", "date")}')

app = Celery('date')

app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks()
