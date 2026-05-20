import os

from django.conf import settings
from django.contrib.auth.mixins import UserPassesTestMixin
from django.shortcuts import redirect
from django_filters.views import FilterView
from django_tables2 import SingleTableMixin

from .filters import DocumentFilter
from .models import Document
from .tables import DocumentTable


def user_type(user):
    if not user.is_authenticated:
        return False
    return user.membership_type.permission_profile != 3


class FilteredDocumentsListView(UserPassesTestMixin, SingleTableMixin, FilterView):
    model = Document
    paginate_by = 15
    table_class = DocumentTable
    template_name = 'archive/document_index.html'
    filterset_class = DocumentFilter

    def get_table_data(self):
        filter_collection = self.request.GET.get('collection', '')
        filter_title_contains = self.request.GET.get('title__contains', '')

        if filter_collection or filter_title_contains:
            if filter_collection:
                return Document.objects.filter(
                    collection__type='Documents', collection=filter_collection, title__contains=filter_title_contains
                )
            else:
                return Document.objects.filter(collection__type='Documents', title__contains=filter_title_contains)
        else:
            return Document.objects.filter(collection__type='Documents')

    def test_func(self):
        # TODO: get a member object and check user.is_authenticated
        return self.request.user.membership_type.permission_profile != 3


def clean_media(request):
    folders = os.walk(settings.MEDIA_ROOT)
    for f in folders:
        print(f[0])
        print(f[2])
        # If picture not in any collection, remove it.
    return redirect('archive:years')
