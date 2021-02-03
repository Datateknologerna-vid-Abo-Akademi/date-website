from django.shortcuts import render
from django.views.generic import ListView

from .models import FormalEvent, FormalEventAttendees


# Create your views here.

class IndexView(ListView):
    model = FormalEvent
    template_name = 'formal_events/index.html'

class AttendeeView(ListView):
    model = FormalEventAttendees

#TODO CREATE DETAIL TEXT VIEW

#TODO CREATE SINGUPFORM VIEW

#TODO CREATE SIGNED UP PEOPLE VIEW