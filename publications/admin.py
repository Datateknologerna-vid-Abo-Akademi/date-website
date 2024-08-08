from django.contrib import admin
from .models import PDFFile


@admin.register(PDFFile)
class PDFFileAdmin(admin.ModelAdmin):
    list_display = ('title', 'uploaded_at')
    search_fields = ('title',)
