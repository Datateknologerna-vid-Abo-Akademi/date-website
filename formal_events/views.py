from django.shortcuts import render
from django.views.generic import ListView

from .models import Event


# Create your views here.

class IndexView(ListView):
    model = Event
    template_name = 'formal_events/index.html'

#TODO CREATE DETAIL TEXT VIEW

#TODO CREATE SINGUPFORM VIEW

#TODO CREATE SIGNED UP PEOPLE VIEW