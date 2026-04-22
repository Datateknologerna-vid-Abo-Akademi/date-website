from django.conf import settings
from django.contrib import admin
from django.contrib.admin.utils import flatten_fieldsets
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from core.admin_ui import resolve_admin_links

if getattr(settings, 'USE_UNFOLD', False):
    from unfold.admin import ModelAdmin, TabularInline, StackedInline
    from unfold.overrides import FORMFIELD_OVERRIDES
    from unfold.widgets import (
        UnfoldAdminSplitDateTimeWidget as AdminSplitDateTimeWidget,
        UnfoldAdminTextInputWidget,
        UnfoldAdminURLInputWidget,
        UnfoldAdminEmailInputWidget,
        UnfoldAdminIntegerFieldWidget,
    )
    # Base dict to spread into any admin that defines its own formfield_overrides,
    # so Unfold's datetime/field widget overrides are not accidentally shadowed.
    UNFOLD_FORMFIELD_OVERRIDES = FORMFIELD_OVERRIDES

    _WIDGET_MAP = {
        'TextInput': UnfoldAdminTextInputWidget,
        'URLInput': UnfoldAdminURLInputWidget,
        'EmailInput': UnfoldAdminEmailInputWidget,
        'NumberInput': UnfoldAdminIntegerFieldWidget,
    }
else:
    from django.contrib.admin.widgets import AdminSplitDateTime as AdminSplitDateTimeWidget
    ModelAdmin = admin.ModelAdmin
    TabularInline = admin.TabularInline
    StackedInline = admin.StackedInline
    UNFOLD_FORMFIELD_OVERRIDES = {}
    _WIDGET_MAP = {}


class UnfoldFormMixin:
    """Replace plain Django input widgets with Unfold equivalents at form init.

    Apply to any ModelForm used in the admin that defines form fields directly
    (bypassing formfield_overrides), so those fields get Unfold styling.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            replacement = _WIDGET_MAP.get(type(field.widget).__name__)
            if replacement is not None:
                field.widget = replacement()


class PublicUrlAdminMixin:
    """Show a compact public-page link for models that implement get_absolute_url."""

    public_url_field = 'public_url'

    def public_url(self, obj):
        if not obj or not getattr(obj, 'pk', None) or not hasattr(obj, 'get_absolute_url'):
            return '-'

        return format_html(
            '<a href="{}" target="_blank" rel="noopener noreferrer">{}</a>',
            obj.get_absolute_url(),
            _('Open public page'),
        )

    public_url.short_description = _('Public page')

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(super().get_readonly_fields(request, obj))
        if obj and hasattr(obj, 'get_absolute_url') and self.public_url_field not in readonly_fields:
            readonly_fields.append(self.public_url_field)
        return readonly_fields

    def get_fieldsets(self, request, obj=None):
        fieldsets = list(super().get_fieldsets(request, obj))
        if not obj or not hasattr(obj, 'get_absolute_url'):
            return fieldsets

        if self.public_url_field not in flatten_fieldsets(fieldsets):
            fieldsets.append((None, {'fields': (self.public_url_field,)}))
        return fieldsets


class ExtraChangeListLinksMixin:
    """Render declarative extra buttons beside the default changelist tools."""

    change_list_template = 'admin/core/change_list_with_extra_tools.html'
    changelist_links = ()

    def get_changelist_links(self, request):
        return resolve_admin_links(self.changelist_links, request)
