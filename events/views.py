from django.shortcuts import render, redirect
from django.views import generic
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.utils import timezone
from .models import Event, EventRegistration

# Create your views here.
class IndexView(generic.ListView):
    model = Event
    template_name = 'events/index.html'
    context_object_name = 'event_list'

    def get_queryset(self):
        return Event.objects.all()

class DetailView(generic.DetailView):
    model = Event
    template_name = 'events/detail.html'

def add_event_attendance(request, slug):
    this_event = Event.objects.get(slug=slug)
    this_event.add_event_attendance(user=request.user)
    return redirect('detail', slug=slug)

#TODO: Remove possibility to remove attendace without rights
def cancel_event_attendance(request, slug):
    this_event = Event.objects.get(slug=slug)
    this_event.cancel_event_attendance(request.user)
    return redirect('detail', slug=slug)
