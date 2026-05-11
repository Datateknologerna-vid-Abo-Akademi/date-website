from django.shortcuts import render

from harassment.views import harassment_form


def socialIndex(request):
    index = ""
    return render(request, 'social/socialIndex.html', {'index': index})


__all__ = ['harassment_form', 'socialIndex']
