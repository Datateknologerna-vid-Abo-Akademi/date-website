import logging

from django.contrib import admin
from django.utils.html import format_html
from core.admin_base import ModelAdmin, PublicUrlAdminMixin
from .models import PDFFile

logger = logging.getLogger('date')

@admin.register(PDFFile)
class PDFFileAdmin(PublicUrlAdminMixin, ModelAdmin):
    list_display = ('title', 'publication_date', 'is_public', 'requires_login', 'uploaded_at', 'updated_at')
    list_filter = ('is_public', 'requires_login', 'uploaded_at', 'updated_at', 'publication_date')
    search_fields = ('title', 'slug', 'description', 'file')
    ordering = ('-uploaded_at',)
    date_hierarchy = 'publication_date'
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ('uploaded_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('title', 'slug', 'publication_date', 'description', 'file')
        }),
        ('Access Control', {
            'fields': ('is_public', 'requires_login'),
            'description': 'Control who can access this PDF.'
        }),
        ('Timestamps', {
            'fields': ('uploaded_at', 'updated_at'),
            'classes': ('collapse',)
        }),
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

    file_link.short_description = 'File'
