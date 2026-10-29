import logging

from django.shortcuts import get_object_or_404, render

from . import models

logger = logging.getLogger('date')


# Create your views here.
def index(request):
    candidates = models.Candidate.objects.published()
    context = {'candidates': candidates}
    return render(request, 'lucia/index.html', context)


def candidates(request):
    candidates = models.Candidate.objects.published()
    context = {'candidates': candidates}
    return render(request, 'lucia/candidates.html', context)


def candidate(request, slug):
    candidate = get_object_or_404(models.Candidate.objects.published(), slug=slug)
    context = {'candidate': candidate}
    return render(request, 'lucia/candidate.html', context)
