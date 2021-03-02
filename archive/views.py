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

def old_year_index(request):
    
    client = boto3.client('s3')
    result = client.list_objects(Bucket=os.getenv('AWS_STORAGE_BUCKET_NAME'), Prefix='media/old/', Delimiter='/')

    year_list = []
    for o in result.get('CommonPrefixes'):
        print('sub folder : ', o.get('Prefix').replace("media/old","").replace("/",""))
        year = o.get('Prefix').replace("media/old","").replace("/","")
        year_list.append(year)
    
    context = {
        'years': year_list,
    }
    return render(request, 'archive/old_index.html', context)

def old_picture_index(request, year):
    client = boto3.client('s3')
    result = client.list_objects(Bucket=os.getenv('AWS_STORAGE_BUCKET_NAME'), Prefix=f'media/old/{year}/', Delimiter='/')
    print(year)
    album_list = []
    for o in result.get('CommonPrefixes'):
        print('sub folder : ', o.get('Prefix').replace(f"media/old/{year}","").replace("/",""))
        album = o.get('Prefix').replace(f"media/old/{year}","").replace("/","")
        album_list.append(album)
        
    context = {
        'year' : year,
        'collections': album_list,
    }
    return render(request, 'archive/old_picture_index.html', context)

def old_detail(request, year, album):

    selected_page = int(request.GET.get('page', 0))

    client = boto3.client('s3')
    paginator = client.get_paginator('list_objects')
    operation_parameters = {'Bucket': os.getenv('AWS_STORAGE_BUCKET_NAME'),
                            'Prefix': f'media/old/{year}/{album}/'}
    page_iterator = paginator.paginate(**operation_parameters, PaginationConfig={'PageSize': 3})

    page_list = []
    for page in page_iterator:
        page_list.append(page['Contents'])

    paginated_page = page_list[selected_page]
   
    s3Url = settings.MEDIA_URL
    image_urls = []
    for img in paginated_page:
        url = s3Url + img['Key'].replace('media/','')
        image_urls.append(url)

    paginate_count = []
    for i in range(0, len(page_list)):
        paginate_count.append(i)

    next_page = len(paginate_count)-1
    if selected_page + 1 < len(page_list):
        next_page = selected_page + 1

    prev_page = 0
    if selected_page - 1 >= 0:
        prev_page = selected_page - 1

    context = {
    'year': year,
    'album': album,
    'image_urls': image_urls,
    'selected_page': selected_page,
    'next_page': next_page,
    'prev_page': prev_page,
    'pagination': paginate_count,
    }

    return render(request, 'archive/old_detail.html', context)