from django.shortcuts import render


def socialIndex(request):
    index = ""
    return render(request, "social/socialIndex.html", {"index": index})
