from django.shortcuts import render, redirect
from django.views import generic
from .models import Event, EventRegistrationForm, EventAttendees


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

    def get_context_data(self, **kwargs):
        context = super(DetailView, self).get_context_data(**kwargs)
        context['logged_in_as'] = self.request.user
        return context

def add_event_attendance(request, slug):
    if request.method == 'POST':
        if len(request.body) > 0:
            anonymous = True if request.POST.get('anonym') else False
            this_event = Event.objects.get(slug=slug)
            this_event.add_event_attendance(user=request.POST.get('namn'), email=request.POST.get('email'),
                                            preferences=request.POST, anonymous=anonymous)
        return redirect('events:detail', slug=slug)
    else:
        return redirect('events:detail', slug=slug)