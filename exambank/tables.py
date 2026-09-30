import django_tables2 as tables

from .models import ExamFile


class ExamFileTable(tables.Table):
    class Meta:
        model = ExamFile
        template_name = "django_tables2/bootstrap.html"
        fields = ('archive', 'title', 'document')
