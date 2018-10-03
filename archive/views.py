from django.shortcuts import render, redirect
from django.views import generic
from .models import Collection, Picture
from .forms import PictureUploadForm


def index(request):
    collections = Collection.objects.all()

    context = {
        'collections': collections,
    }
    return render(request, 'archive/index.html', context)


class DetailView(generic.DetailView):
    model = Collection
    template_name = 'archive/detail.html'


def upload(request):
    if request.method == 'POST':
        form = PictureUploadForm(request.POST)

        print("form is :", form.is_valid())
        if form.is_valid():
            collection = Collection(title=form['collection_name'].value(), type='Pictures')
            collection.save()
            for file in request.FILES.getlist('images'):
                Picture(image=file, collection=collection).save()
        return redirect('archive:index')

    form = PictureUploadForm
    context = {
        'picture_form': form,
    }
    return render(request, 'archive/upload.html', context)