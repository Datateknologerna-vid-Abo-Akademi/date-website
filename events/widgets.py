from django.conf import settings
from django.forms import widgets
from django.template.loader import render_to_string


class PrettyJSONWidget(widgets.Textarea):
    def render(self, name, value, attrs=None, **kwargs):
        html = super().render(name, value, attrs)
        start_as = self.attrs.get("initial", None) or "raw"

        ctx = {"html": html, "start_as": start_as}

        return render_to_string("events/jsonwidget.html", ctx)

    @property
    def media(self):
        extra = "" if settings.DEBUG else ".min"
        return widgets.Media(
            js=(
                f"admin/js/vendor/jquery/jquery{extra}.js",
                "admin/js/jquery.init.js",
                "prettyjson/prettyjson.js",
            ),
        )
