import django_filters

from .models import Document, get_collections_of_type

class DocumentFilter(django_filters.FilterSet):
    collection = django_filters.ModelChoiceFilter(queryset=get_collections_of_type('Documents'))

    class Meta:
        model = Document
        fields = {
            'collection': ['exact'],
            'title': ['contains'],
        }


class ExamFilter(django_filters.FilterSet):

    class Meta:
        model = Document
        fields = {}