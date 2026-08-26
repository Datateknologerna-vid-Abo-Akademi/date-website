"""Form field/widget for browser-to-storage uploads (Uppy).

When direct uploads are enabled (``USE_S3`` + ``DIRECT_UPLOADS_ENABLED``) the
widget renders a Uppy Dashboard container plus a hidden input holding the JSON
payload of uploaded temp keys, and a removable list of the files already
uploaded to the temp prefix. On form save the app calls
``core.uploads.finalize_upload`` to move each temp object to its final key.
The uploaded list is rehydrated from the hidden payload on every render, so
files survive reloads and validation errors and can be removed individually.

When direct uploads are disabled the widget degrades to a classic file input
wrapped in a container that lists the selected files and lets the user remove
them before submitting. For upload scopes used by the Django admin (``admin``,
``gallery-admin``) the classic input is rendered through the admin file widget,
keeping the Unfold upload styling and the broken-file safety from
``core.admin_widgets``.

The widget only manages temp uploads; files already attached to model rows are
managed through the normal admin inlines.

The mode is decided at render/clean time (not field construction) because form
field instances are class attributes and Django settings may differ between
deployments.
"""

import json

from django import forms
from django.core.exceptions import ValidationError
from django.utils.html import format_html, format_html_join
from django.utils.translation import gettext_lazy as _

from .uploads import SCOPES, parse_uploaded_files, uploads_enabled

# Always loaded wherever a DirectUploadField renders, so both modes get the
# file-list behavior (Uppy assets are CDN-only and loaded on top when enabled).
UPLOAD_WIDGET_CSS = ('uploads/css/upload-widget.css',)
UPLOAD_WIDGET_JS = ('uploads/js/upload-init.js',)

UPPY_MEDIA_CSS = ('https://releases.transloadit.com/uppy/v5.2.4/uppy.min.css',)
UPPY_MEDIA_JS = ('https://releases.transloadit.com/uppy/v5.2.4/uppy.min.js',)

# Scopes used from Django admin change forms. Their classic-mode input keeps the
# admin upload widget so the Unfold markup and safe-widget behavior are
# preserved when direct uploads are disabled.
ADMIN_UPLOAD_SCOPES = frozenset({'admin', 'gallery-admin'})


class DirectUploadWidget(forms.Widget):
    """File input (classic) or hidden input + Uppy container (direct mode)."""

    def __init__(
        self,
        *,
        scope,
        bucket='private',
        multi=True,
        compress=False,
        allowed_extensions=None,
        max_bytes=None,
        attrs=None,
    ):
        self.scope = scope
        self.bucket = bucket
        self.multi = multi
        self.compress = compress
        self.admin = scope in ADMIN_UPLOAD_SCOPES
        self.allowed_extensions = allowed_extensions or sorted(SCOPES[scope]['extensions'])
        self.max_bytes = max_bytes or SCOPES[scope]['max_bytes']
        super().__init__(attrs)

    @staticmethod
    def _attrs_html(attrs):
        """Render attributes safely (each name/value escaped)."""
        return format_html_join('', ' {}="{}"', sorted(attrs.items()))

    def _classic_input(self, name, attrs=None, renderer=None):
        if self.admin:
            from core.admin_widgets import SafeAdminMultipleFileWidget

            return SafeAdminMultipleFileWidget(attrs=attrs).render(name, None, renderer=renderer)
        input_attrs = self.build_attrs(attrs or {}, {'type': 'file', 'name': name})
        if self.multi:
            input_attrs['multiple'] = 'multiple'
        return format_html('<input{}>', self._attrs_html(input_attrs))

    def _direct_inputs(self, name, value, attrs=None):
        attrs = attrs or {}
        if value is None:
            value = ''
        if not isinstance(value, str):
            value = json.dumps(value)
        hidden_attrs = self.build_attrs(attrs, {'type': 'hidden', 'name': name})
        hidden = format_html('<input{} value="{}">', self._attrs_html(hidden_attrs), value)
        container_attrs = self.build_attrs(
            {
                'class': 'django-uppy-widget',
                'data-uppy-widget': '1',
                'data-uppy-mode': 'direct',
                'data-uppy-scope': self.scope,
                'data-uppy-bucket': self.bucket,
                'data-uppy-multi': 'true' if self.multi else 'false',
                'data-uppy-compress': 'true' if self.compress else 'false',
                'data-uppy-name': name,
                'data-uppy-max-bytes': str(self.max_bytes),
                'data-uppy-allowed-extensions': ','.join(self.allowed_extensions),
            }
        )
        container = format_html(
            '<div{}><div data-uppy-mount="1"></div><ul class="django-uppy-files" data-uppy-uploaded="1"></ul></div>',
            self._attrs_html(container_attrs),
        )
        fallback = format_html('<noscript>{}</noscript>', self._classic_input(name, attrs))
        return format_html('{}{}{}', hidden, container, fallback)

    def _classic_inputs(self, name, attrs=None, renderer=None):
        container = format_html(
            '<div class="django-uppy-widget" data-uppy-widget="1" data-uppy-mode="classic">'
            '{}<ul class="django-uppy-files" data-uppy-selected="1"></ul>'
            '</div>',
            self._classic_input(name, attrs, renderer=renderer),
        )
        return container

    def render(self, name, value, attrs=None, renderer=None):
        if uploads_enabled():
            return self._direct_inputs(name, value, attrs)
        return self._classic_inputs(name, attrs, renderer=renderer)

    def value_from_datadict(self, data, files, name):
        if uploads_enabled():
            classic_files = files.getlist(name) if self.multi else files.get(name)
            if classic_files:
                return classic_files
            return data.get(name)
        if self.multi:
            return files.getlist(name)
        return files.get(name)


class DirectUploadField(forms.Field):
    """Accepts either a JSON payload of temp keys (direct mode) or files."""

    default_error_messages = {
        'invalid_payload': _('Ogiltig uppladdning, försök igen.'),
    }

    def __init__(
        self,
        *,
        scope,
        bucket='private',
        multi=True,
        compress=None,
        allowed_extensions=None,
        max_bytes=None,
        **kwargs,
    ):
        if compress is None:
            compress = SCOPES[scope].get('compress', False)
        kwargs.setdefault('required', False)
        super().__init__(
            widget=DirectUploadWidget(
                scope=scope,
                bucket=bucket,
                multi=multi,
                compress=compress,
                allowed_extensions=allowed_extensions,
                max_bytes=max_bytes,
            ),
            **kwargs,
        )

    def clean(self, value):
        value = super().clean(value)
        if not uploads_enabled() or isinstance(value, (list, tuple)):
            if isinstance(value, (list, tuple)):
                return list(value)
            return [value] if value else []
        try:
            return parse_uploaded_files(value, scope=self.widget.scope)
        except ValueError as exc:
            raise ValidationError(self.error_messages['invalid_payload'], code='invalid_payload') from exc

    def has_changed(self, initial, data):
        return bool(data)


class DirectUploadAdminMediaMixin:
    """Add the upload-widget assets to an admin changeform.

    Admin Media classes are merged into ``ModelAdmin.media``; this mixin
    appends the file-list behavior always (both upload modes need it) and the
    Uppy CDN assets only when direct uploads are enabled, on top of whatever
    the admin declares (e.g. flatpickr)."""

    @property
    def media(self):
        media = super().media
        media += forms.Media(css={'all': UPLOAD_WIDGET_CSS}, js=UPLOAD_WIDGET_JS)
        if uploads_enabled():
            media += forms.Media(css={'all': UPPY_MEDIA_CSS}, js=UPPY_MEDIA_JS)
        return media
