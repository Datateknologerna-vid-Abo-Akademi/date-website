import django_filters

from .models import ExamFile


class ExamFilter(django_filters.FilterSet):

    class Meta:
        model = ExamFile
        fields = {}
