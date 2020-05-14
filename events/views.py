import datetime
import os

from django.http import HttpResponseForbidden
from django.views.generic import DetailView, ListView
from django.shortcuts import render
from .models import Event, EventAttendees
from websocket import create_connection
from websocket._exceptions import WebSocketBadStatusException
from django.views import generic
from django.utils.safestring import mark_safe

from .models import *
from .utils import Calendar
import json

import logging
logger = logging.getLogger('date')


class IndexView(ListView):
    model = Event
    template_name = 'events/index.html'

    def get_context_data(self, **kwargs):
        context = super(IndexView, self).get_context_data(**kwargs)
        context['event_list'] = Event.objects.filter(published=True,
                                                     event_date_end__gte=datetime.date.today()).order_by(
            'event_date_start')
        context['past_events'] = Event.objects.filter(published=True, event_date_start__year=datetime.date.today().year,
                                                      event_date_end__lte=datetime.date.today()).order_by(
            'event_date_start').reverse()
        return context


class EventDetailView(DetailView):
    model = Event
    template_name = 'events/detail.html'

    def get_context_data(self, **kwargs):
        context = super(EventDetailView, self).get_context_data(**kwargs)
        form = kwargs.pop('form', None)
        if form:
            context['form'] = form
        else:
            context['form'] = self.object.make_registration_form()

        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.sign_up and self.object.published and (request.user.is_authenticated
                                                              and self.object.registration_is_open_members()
                                                              or self.object.registration_is_open_others()):
            form = self.object.make_registration_form().__call__(data=request.POST)
            if form.is_valid():
                ws_send(request, form)
                return self.form_valid(form)
            return self.form_invalid(form)
        return HttpResponseForbidden()

    def form_valid(self, form):
        self.get_object().add_event_attendance(user=form.cleaned_data['user'], email=form.cleaned_data['email'],
                                               anonymous=form.cleaned_data['anonymous'], preferences=form.cleaned_data)
        return render(self.request, self.template_name, self.get_context_data())

    def form_invalid(self, form):
        return render(self.request, self.template_name, self.get_context_data(form=form))


def ws_send(request, form):
    ws_schema = 'ws' if request.scheme == 'http' else 'wss'
    url = request.META.get('HTTP_HOST')
    path = ws_schema + '://' + url + '/ws' + request.path
    try:
        ws = create_connection(path)
        ws.send(json.dumps(ws_data(form.cleaned_data)))
        ws.close()
    except WebSocketBadStatusException:
        logger.error("Could not create connection for web socket")
        # Alert Datörer


def ws_data(form):
    pref = dict(form)  # Creates copy of form
    pref['user'] = "Anonymous" if pref['anonymous'] else pref['user']
    del pref['anonymous']
    del pref['email']
    return {"data": pref}

class CalendarView(generic.ListView):
    model = Event
    template_name = 'events/calendar.html'

    def get_context_data(self, **kwargs):
        context = super(CalendarView, self).get_context_data(**kwargs)

        d = get_date(self.request.GET.get('day', None))
        
        cal = Calendar(d.year, d.month)

        html_cal = cal.formatmonth(withyear=True)
        context['calendar'] = mark_safe(html_cal)

        return context

def get_date(req_day):
    if req_day:
        year, month = (int(x) for x in req_day.split('-'))
        return date(year, month, day=1)
    return datetime.date.today()
