from django.contrib import admin
from .models import PDFFile

@admin.register(PDFFile)
class PDFFileAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'publication_date', 'num_pages', 'file_size', 'is_public', 'uploaded_at', 'updated_at')
    list_filter = ('is_public', 'uploaded_at', 'updated_at', 'publication_date')
    search_fields = ('title', 'slug', 'description', 'author')
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ('uploaded_at', 'updated_at', 'file_size', 'num_pages')
    fieldsets = (
        (None, {
            'fields': ('title', 'slug', 'author', 'publication_date', 'description', 'file', 'is_public')
        }),
        ('File Information', {
            'fields': ('file_size', 'num_pages'),
            'classes': ('collapse',)
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
        if obj:
            return self.readonly_fields + ('file',)
        return self.readonly_fields