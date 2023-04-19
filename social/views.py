from django.shortcuts import render


# Create your views here.

def socialIndex(request):
    index = ""
    return render(request, 'social/socialIndex.html', {'index': index})
