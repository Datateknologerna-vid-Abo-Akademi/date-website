import logging

from django import forms
from django.contrib.admin import widgets as admin_widgets
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

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


# Flatpickr-based datetime input shared across admin forms (events, news, polls, ctf, lucia).
# The widget appends a "Don't publish" clear button only when bound to the conventional
# `published_time` field name, so the same class is safe to reuse for other datetime fields.

FLATPICKR_DATETIME_FORMAT = "%Y-%m-%d %H:%M"
FLATPICKR_DATETIME_INPUT_FORMATS = ["%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"]

FLATPICKR_ADMIN_CSS = (
    "core/css/flatpickr.min.css",
    "core/css/admin-datetime.css",
)
FLATPICKR_ADMIN_JS = (
    "core/js/flatpickr.min.js",
    "core/js/flatpickr-init.js",
)


class PublishDateTimeWidget(forms.DateTimeInput):
    """Flatpickr-styled datetime input with quick-action buttons for `published_time`.

    Adds a "Publish now" button (stamps in the server's current local time at form
    render) and a "Don't publish" clear button.
    """

    def render(self, name, value, attrs=None, renderer=None):
        rendered = super().render(name, value, attrs=attrs, renderer=renderer)
        if name != "published_time":
            return rendered
        widget_id = (attrs or {}).get("id", f"id_{name}")
        server_now = timezone.localtime(timezone.now()).strftime(FLATPICKR_DATETIME_FORMAT)
        return format_html(
            "{} "
            '<button type="button" class="datetime-action-button" '
            'data-set-datetime="#{}" data-set-datetime-value="{}">{}</button> '
            '<button type="button" class="datetime-action-button" '
            'data-clear-datetime="#{}">{}</button>',
            rendered,
            widget_id,
            server_now,
            _("Publish now"),
            widget_id,
            _("Don't publish"),
        )


def flatpickr_datetime_widget():
    return PublishDateTimeWidget(
        format=FLATPICKR_DATETIME_FORMAT,
        attrs={
            "class": "flatpickr-datetime",
            "placeholder": "YYYY-MM-DD HH:MM",
        },
    )


def flatpickr_datetime_field(*, initial=None, required=True):
    return forms.DateTimeField(
        widget=flatpickr_datetime_widget(),
        input_formats=FLATPICKR_DATETIME_INPUT_FORMATS,
        initial=initial,
        required=required,
    )


class FlatpickrDateTimeAdminMixin:
    """Swap selected DateTimeField admin form fields to use the flatpickr widget.

    Override `flatpickr_datetime_fields` on the admin to list field names that
    should adopt the widget. Subclasses still need to declare a Media class that
    loads `FLATPICKR_ADMIN_CSS` / `FLATPICKR_ADMIN_JS` — admin Media is not
    inherited from mixins automatically.
    """

    flatpickr_datetime_fields = ("published_time",)

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name in self.flatpickr_datetime_fields:
            # Override Unfold's default SplitDateTimeField + split widget — those
            # don't accept the single-input format/widget we want here.
            kwargs.setdefault("form_class", forms.DateTimeField)
            kwargs.setdefault("widget", flatpickr_datetime_widget())
            kwargs.setdefault("input_formats", FLATPICKR_DATETIME_INPUT_FORMATS)
        return super().formfield_for_dbfield(db_field, request, **kwargs)
