from django.shortcuts import render
from .models import AbstractFile, Collection


def showroom(request):
    files = AbstractFile.objects.all()
    return render(request, 'archive/showroom.html', {'files': files})


def upload(request):
    if request.method == 'POST':
        # Process files here.
        request.FILES

        files = AbstractFile.objects.all()
        return render(request, 'archive/showroom.html', {'files': files, 'msg': msg})

    else:
        collections = Collection.objects.all()
        return render(request, 'archive/upload.html', {'collections': collections})

