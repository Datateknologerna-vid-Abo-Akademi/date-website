from django.shortcuts import render
import logging

from . import models

logger = logging.getLogger('date')

# Create your views here.
def index(request):
    candidates = models.Candidate.objects.all()
    context = {'candidates': candidates}
    return render(request, 'lucia/index.html', context)

def candidates(request):
    candidates = models.Candidate.objects.all()
    context = {'candidates': candidates}
    return render(request, 'lucia/candidates.html', context)    

def candidate(request, slug):
    candidate = models.Candidate.objects.get(slug=slug, published=True)
    context = {'candidate': candidate}
    return render(request, 'lucia/candidate.html', context)