import logging

from django import forms
from django.contrib import admin
from django.utils.html import format_html

from core.admin_base import ModelAdmin, PublicUrlAdminMixin

from .models import PDFFile, PublicationCollection

logger = logging.getLogger('date')


class PublicationCollectionAdminForm(forms.ModelForm):
    password = forms.CharField(
        label='Password',
        required=False,
        widget=forms.PasswordInput(render_value=False),
        help_text='Set or replace the access password. Leave blank to keep the current password.',
    )
    clear_password = forms.BooleanField(
        label='Clear password',
        required=False,
        help_text='Remove the current password.',
    )

    class Meta:
        model = PublicationCollection
        fields = '__all__'  # noqa: DJ007

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('clear_password') and cleaned_data.get('password'):
            raise forms.ValidationError('Choose either a new password or clear the current password, not both.')
        return cleaned_data

    def save(self, commit=True):
        collection = super().save(commit=False)
        if self.cleaned_data.get('clear_password'):
            collection.set_password('')
        elif self.cleaned_data.get('password'):
            collection.set_password(self.cleaned_data['password'])
        if commit:
            collection.save()
            self.save_m2m()
        return collection


@admin.register(PublicationCollection)
class PublicationCollectionAdmin(ModelAdmin):
    form = PublicationCollectionAdminForm
    list_display = ('title', 'visibility', 'ordering', 'is_active', 'publication_count', 'updated_at')
    list_filter = ('visibility', 'is_active')
    search_fields = ('title', 'slug', 'description')
    ordering = ('ordering', 'title')
    prepopulated_fields = {'slug': ('title',)}
    filter_horizontal = ('allowed_membership_types',)
    readonly_fields = ('created_at', 'updated_at', 'has_password')
    fieldsets = (
        (
            None,
            {
                'fields': ('title', 'slug', 'description', 'cover_image', 'ordering', 'is_active'),
            },
        ),
        (
            'Access Control',
            {
                'fields': ('visibility', 'allowed_membership_types', 'password', 'clear_password', 'has_password'),
                'description': 'Controls whether this collection is listed and who can open its publications.',
            },
        ),
        (
            'Timestamps',
            {
                'fields': ('created_at', 'updated_at'),
                'classes': ('collapse',),
            },
        ),
    )

    def get_prepopulated_fields(self, request, obj=None):
        if obj is None:
            return self.prepopulated_fields
        return {}

    @admin.display(boolean=True, description='Has password')
    def has_password(self, obj):
        return bool(obj and obj.has_password())

    @admin.display(description='Publications')
    def publication_count(self, obj):
        return obj.publications.count()


@admin.register(PDFFile)
class PDFFileAdmin(PublicUrlAdminMixin, ModelAdmin):
    list_display = (
        'title',
        'collection',
        'publication_date',
        'is_external_link',
        'is_public',
        'requires_login',
        'uploaded_at',
        'updated_at',
    )
    list_filter = ('collection', 'is_public', 'requires_login', 'uploaded_at', 'updated_at', 'publication_date')
    search_fields = ('title', 'slug', 'description', 'file', 'redirect_url', 'collection__title')
    ordering = ('-uploaded_at',)
    date_hierarchy = 'publication_date'
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ('uploaded_at', 'updated_at')
    fieldsets = (
        (
            None,
            {
                'fields': (
                    'collection',
                    'title',
                    'slug',
                    'publication_date',
                    'description',
                    'file',
                    'redirect_url',
                    'cover_image',
                )  # noqa: E501
            },
        ),
        (
            'Access Control',
            {
                'fields': ('is_public', 'requires_login'),
                'description': 'Publication access is checked after the collection access rules.',
            },
        ),
        ('Timestamps', {'fields': ('uploaded_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    def get_prepopulated_fields(self, request, obj=None):
        # Only prepopulate slug for new objects
        if obj is None:
            return self.prepopulated_fields
        return {}

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(super().get_readonly_fields(request, obj))
        if obj:
            readonly_fields.append('file_link')
        return readonly_fields

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if not obj:
            return fieldsets

        updated_fieldsets = []
        for name, options in fieldsets:
            fields = tuple('file_link' if field == 'file' else field for field in options.get('fields', ()))
            updated_fieldsets.append((name, {**options, 'fields': fields}))
        return updated_fieldsets

    @admin.display(description="File")
    def file_link(self, obj):
        if not obj or not obj.file:
            return '-'
        try:
            return format_html(
                '<a href="{}" target="_blank" rel="noopener noreferrer">{}</a>',
                obj.file.url,
                obj.file.name,
            )
        except Exception as exc:
            logger.warning("Unable to resolve PDF file URL for %s: %s", obj.pk, exc)
            return obj.file.name

    @admin.display(boolean=True, description='External link')
    def is_external_link(self, obj):
        return bool(obj.redirect_url)
