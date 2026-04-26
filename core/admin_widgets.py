import logging

from django.contrib.admin import widgets as admin_widgets


logger = logging.getLogger("date")


class SafeAdminFileWidget(admin_widgets.AdminFileWidget):
    """Avoid crashing admin forms when a stored file cannot resolve a URL."""

    def is_initial(self, value):
        if not value:
            return False
        try:
            return bool(value.url)
        except Exception as exc:
            logger.warning("Unable to resolve admin file widget URL: %s", exc)
            return False
