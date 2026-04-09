import logging

from django.conf import settings
from django.contrib.admin import widgets as admin_widgets
from django.forms import widgets
from django.template.loader import render_to_string


logger = logging.getLogger("date")


class PrettyJSONWidget(widgets.Textarea):

    def render(self, name, value, attrs=None, **kwargs):
        html = super(PrettyJSONWidget, self).render(name, value, attrs)
        start_as = self.attrs.get('initial', None) or 'raw'

        ctx = {
            "html": html,
            "start_as": start_as
        }

        return render_to_string("events/jsonwidget.html", ctx)

    @property
    def media(self):
        extra = '' if settings.DEBUG else '.min'
        return widgets.Media(
            js=(
                'admin/js/vendor/jquery/jquery%s.js' % extra,
                'admin/js/jquery.init.js',
                'prettyjson/prettyjson.js',
            ),
        )


class SafeAdminFileWidget(admin_widgets.AdminFileWidget):
    """Avoid crashing the admin form when a stored file cannot resolve a URL."""

    def is_initial(self, value):
        if not value:
            return False
        try:
            return bool(value.url)
        except Exception as exc:
            logger.warning("Unable to resolve admin file widget URL: %s", exc)
            return False
