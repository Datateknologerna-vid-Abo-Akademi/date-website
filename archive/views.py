import os
import requests

from botocore.client import Config

from django.conf import settings
from django.contrib.auth.decorators import permission_required
from django.shortcuts import redirect, render
from django.views import generic
from django.conf import settings
from django_tables2 import SingleTableMixin
from django_filters.views import FilterView
from .models import Collection, Picture, Document
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from .filters import DocumentFilter
from .forms import PictureUploadForm
from .filters import DocumentFilter
from .tables import DocumentTable
from django.contrib.auth.decorators import permission_required


import os

def year_index(request):
    
    years = Collection.objects.dates('pub_date', 'year').reverse()
    year_list = []
    for year in years:
        year_list.append(year.strftime("%Y"))

    context = {
        'type': "pictures",
        'years': year_list,
    }
    return render(request, 'archive/index.html', context)

def picture_index(request, year):
    collections = Collection.objects.filter(type="Pictures", pub_date__year=year).order_by('-pub_date')
    context = {
        'type': "pictures",
        'year' : year,
        'collections': collections,
    }
    return render(request, 'archive/picture_index.html', context)


class FilteredDocumentsListView(SingleTableMixin, FilterView):
    model = Document
    paginate_by = 15
    table_class = DocumentTable
    template_name = 'archive/document_index.html'
    filterset_class = DocumentFilter


def picture_detail(request, year, album):
    collection = Collection.objects.filter(type="Pictures", pub_date__year=year, title=album).order_by('-pub_date')
    pictures = Picture.objects.filter(collection=collection[0])

    page = request.GET.get('page', 1)

    paginator = Paginator(pictures, 15)
    try:
        pictures = paginator.page(page)
    except PageNotAnInteger:
        pictures = paginator.page(1)
    except EmptyPage:
        pictures = paginator.page(paginator.num_pages)

    context = {
        'type': "pictures",
        'year' : year,
        'album' : album,
        'collection' : collection[0],
        'pictures': pictures,
    }

    return render(request, 'archive/detail.html', context )

@permission_required('archive.add_collection')
def upload(request):
    if request.method == 'POST':
        form = PictureUploadForm(request.POST)
        if form.is_valid():
            if request.FILES.getlist('images') is None:
                return redirect('archive:pictures')
            collection = Collection(title=form['album'].value(), type='Pictures')
            collection.save()
            for file in request.FILES.getlist('images'):
                Picture(image=file, collection=collection).save()
        return redirect('archive:years')

    form = PictureUploadForm
    context = {
        'picture_form': form,
    }
    return render(request, 'archive/upload.html', context)


def clean_media(request):
    folders = os.walk(settings.MEDIA_ROOT)
    for f in folders:
        print(f[0])
        print(f[2])
        # If picture not in any collection, remove it.
    return redirect('archive:pictures')