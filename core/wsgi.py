"""
WSGI config for date project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/2.1/howto/deployment/wsgi/
"""
# update

import os

from django.core.wsgi import get_wsgi_application

proj_name = os.environ.get("PROJECT_NAME", "date")

os.environ.setdefault('DJANGO_SETTINGS_MODULE', f'core.settings.{proj_name}')

application = get_wsgi_application()
