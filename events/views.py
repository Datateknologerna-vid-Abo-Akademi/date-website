from django.shortcuts import render, redirect
from django.views import generic
from events.forms import EventAttendeeForm
from .models import Event, EventRegistrationForm, EventAttendees


# Create your views here.
class IndexView(generic.ListView):
    model = Event
    template_name = 'events/index.html'
    context_object_name = 'event_list'

    def get_queryset(self):
        return Event.objects.all()


class DetailView(generic.DetailView): #TODO: Validate preferences
    model = Event
    template_name = 'events/detail.html'

    def get_context_data(self, **kwargs):
        context = super(DetailView, self).get_context_data(**kwargs)
        if not self.request.user.is_anonymous:
            context['basic_form'] = EventAttendeeForm(
                {'user': self.request.user.full_name, 'email': self.request.user.email})
        else:
            context['basic_form'] = EventAttendeeForm
        return context

    def post(self, request, slug, *args, **kwargs):
        form = EventAttendeeForm(request.POST, request.FILES)
        if form.is_valid():
            self.object = self.get_object()
            this_event = Event.objects.get(slug=slug)
            this_event.add_event_attendance(user=form.cleaned_data['user'], email=form.cleaned_data['email'],
                                            preferences=request.POST, anonymous=form.cleaned_data['anonymous'])
            context = super(DetailView, self).get_context_data(**kwargs)
            context['basic_form'] = EventAttendeeForm
            return self.render_to_response(context=context)
        else:
            self.object = self.get_object()
            context = super(DetailView, self).get_context_data(**kwargs)
            context['basic_form'] = form
            return self.render_to_response(context=context)



