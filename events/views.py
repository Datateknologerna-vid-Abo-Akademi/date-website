import datetime
import json
import logging
import os

from django.http import HttpResponseForbidden
from django.shortcuts import render
from django.views.generic import DetailView, ListView
from websocket import create_connection
from websocket._exceptions import WebSocketBadStatusException

from .models import Event, EventAttendees

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

                public_info = self.object.get_registration_form_public_info()
                # Do not send ws data on refresh after initial signup.
                if not EventAttendees.objects.filter(email=request.POST.get('email'), event=self.object.id).first():
                    logger.info(f"User {request.user} signed up with name: {request.POST.get('user')}")
                    ws_send(request, form, public_info)
                return self.form_valid(form)
            return self.form_invalid(form)
        return HttpResponseForbidden()

    def form_valid(self, form):
        self.get_object().add_event_attendance(user=form.cleaned_data['user'], email=form.cleaned_data['email'],
                                               anonymous=form.cleaned_data['anonymous'], preferences=form.cleaned_data)
        return render(self.request, self.template_name, self.get_context_data())

    def form_invalid(self, form):
        return render(self.request, self.template_name, self.get_context_data(form=form))


def ws_send(request, form, public_info):
    ws_schema = 'ws' if request.scheme == 'http' else 'wss'
    url = request.META.get('HTTP_HOST')
    path = ws_schema + '://' + url + '/ws' + request.path
    try:
        ws = create_connection(path)
        ws.send(json.dumps(ws_data(form, public_info)))
        ws.close()
    except WebSocketBadStatusException:
        logger.error("Could not create connection for web socket")
        # Alert Datörer


def ws_data(form, public_info):
    data = {}
    pref = dict(form.cleaned_data)  # Creates copy of form

    data['user'] = "Anonymous" if pref['anonymous'] else pref['user']
    # parse the public info and only send that through websockets.
    for index, info in enumerate(public_info):
        if str(info) in pref:
            data[str(info)] = pref[str(info)]
    print(data)
    return {"data": data}