#!/usr/bin/env python
import os
import sys

proj_name = os.environ.get("PROJECT_NAME")
if proj_name == "":
    proj_name = "date"
    print("PROJECT_NAME not set, defaulting to 'date'")

if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', f'core.settings.{proj_name}')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)
