import os
import boto3

from django.conf import settings
from django.contrib.auth.decorators import permission_required
from django.shortcuts import redirect, render
from django.views import generic
from django_filters.views import FilterView
from django_tables2 import SingleTableMixin

from .filters import DocumentFilter
from .forms import PictureUploadForm
from .models import Collection, Document, Picture
from .tables import DocumentTable

def year_index(request):
    
    client = boto3.client('s3')
    result = client.list_objects(Bucket=os.getenv('AWS_STORAGE_BUCKET_NAME'), Prefix='media/', Delimiter='/')

    for o in result.get('CommonPrefixes'):
        print('sub folder : ', o.get('Prefix').replace("media/",""))

    #s3 = boto3.resource('s3')
    #bucket = s3.Bucket(os.getenv('AWS_STORAGE_BUCKET_NAME'))
    # Iterates through all the objects, doing the pagination for you. Each obj
    # is an ObjectSummary, so it doesn't contain the body. You'll need to call
    # get to get the whole body.
    #for obj in bucket.objects.filter(Prefix='media/', Delimiter='/'):
    #    key = obj.key
    #    url = f'https://{bucket.name}.s3.amazonaws.com/{key}'
    #    print(url)
    
    #print(body)

    
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


class DetailView(generic.DetailView):
    model = Collection
    template_name = 'archive/detail.html'

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
        return redirect('archive:pictures')

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
