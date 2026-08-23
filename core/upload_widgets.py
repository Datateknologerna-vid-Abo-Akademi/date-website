"""Form field/widget for direct browser-to-storage uploads (Uppy).

When direct uploads are enabled (``USE_S3`` + ``DIRECT_UPLOADS_ENABLED``) the
widget renders a Uppy Dashboard container plus a hidden input holding the JSON
payload of uploaded temp keys. On form save the app calls
``core.uploads.finalize_upload`` to move each temp object to its final key.

When direct uploads are disabled the widget degrades to a classic file input so
behavior (and tests) stay unchanged for local/self-hosted setups.

The mode is decided at render/clean time (not field construction) because form
field instances are class attributes and Django settings may differ between
deployments.
"""

import json

from django import forms
from django.core.exceptions import ValidationError
from django.forms.utils import flatatt
from django.utils.html import escape, mark_safe
from django.utils.translation import gettext_lazy as _

from .uploads import SCOPES, parse_uploaded_files, uploads_enabled

UPPY_MEDIA_CSS = ('uploads/vendor/uppy.min.css',)
UPPY_MEDIA_JS = ('uploads/vendor/uppy.min.js', 'uploads/js/uppy-init.js')


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
        self.allowed_extensions = allowed_extensions or sorted(SCOPES[scope]['extensions'])
        self.max_bytes = max_bytes or SCOPES[scope]['max_bytes']
        super().__init__(attrs)

    def _classic_input(self, name, attrs=None):
        input_attrs = self.build_attrs(attrs, {'type': 'file', 'name': name})
        if self.multi:
            input_attrs['multiple'] = 'multiple'
        return f'<input{flatatt(input_attrs)}>'

    def _direct_inputs(self, name, value, attrs=None):
        if value is None:
            value = ''
        if not isinstance(value, str):
            value = json.dumps(value)
        hidden_attrs = self.build_attrs(attrs, {'type': 'hidden', 'name': name})
        hidden = f'<input{flatatt(hidden_attrs)} value="{escape(value)}">'
        container_attrs = self.build_attrs(
            {
                'class': 'django-uppy-widget',
                'data-uppy-widget': '1',
                'data-uppy-scope': self.scope,
                'data-uppy-bucket': self.bucket,
                'data-uppy-multi': 'true' if self.multi else 'false',
                'data-uppy-compress': 'true' if self.compress else 'false',
                'data-uppy-name': name,
                'data-uppy-max-bytes': str(self.max_bytes),
                'data-uppy-allowed-extensions': ','.join(self.allowed_extensions),
            }
        )
        return hidden + f'<div{flatatt(container_attrs)}></div>'

    def render(self, name, value, attrs=None, renderer=None):
        if uploads_enabled():
            return mark_safe(self._direct_inputs(name, value, attrs))
        return mark_safe(self._classic_input(name, attrs))

    def value_from_datadict(self, data, files, name):
        if uploads_enabled():
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
        if not uploads_enabled():
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
    """Add the Uppy assets to an admin changeform only when direct uploads are
    enabled. Admin Media classes are merged into ``ModelAdmin.media``; this
    mixin appends the Uppy assets conditionally on top of whatever the admin
    declares (e.g. flatpickr)."""

    @property
    def media(self):
        media = super().media
        if uploads_enabled():
            media += forms.Media(css={'all': UPPY_MEDIA_CSS}, js=UPPY_MEDIA_JS)
        return media
