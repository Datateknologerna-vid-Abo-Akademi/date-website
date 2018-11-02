from django.shortcuts import render, redirect
from django.views import generic
from .models import Collection, Picture
from .forms import PictureUploadForm
from django.conf import settings
import os


def picture_index(request):
    collections = Collection.objects.filter(type="Pictures").order_by('-pub_date')
    context = {
        'type': "pictures",
        'collections': collections,
    }
    return render(request, 'archive/index.html', context)


def document_index(request):
    collections = Collection.objects.filter(type="Documents")
    if request.user.is_authenticated:
        context = {
            'type': "Documents",
            'collections': collections,
        }
        return render(request, 'archive/index.html', context)
    return redirect('index')


class DetailView(generic.DetailView):
    model = Collection
    template_name = 'archive/detail.html'


def edit(request, pk):
    collection = Collection.objects.get(id=pk)
    return render(request, 'archive/edit.html', {'collection': collection})


def remove_file(request, collection_id, file_id):
    file = Picture.objects.get(pk=file_id)
    file.delete()
    collection = Collection.objects.get(pk=collection_id)
    print(collection.picture_set.count())
    if collection.picture_set.count() > 0:
        return render(request, 'archive/edit.html', {'collection': collection})
    collection.delete()
    collections = Collection.objects.all()
    return render(request, 'archive/index.html', {'collections': collections})


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
        # f[0] = Folder
        # f[2] = list of pictures.

        print(f[0])
        print(f[2])
    return redirect('archive:pictures')
