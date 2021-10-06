import datetime
import os
from django.db import models

from django.http import HttpResponseForbidden, request
from django.views.generic import DetailView, ListView
from django.shortcuts import redirect, render
from .models import Event, EventAttendees
from staticpages.models import StaticPage, StaticPageNav
from websocket import create_connection
from websocket._exceptions import WebSocketBadStatusException
from copy import deepcopy

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


def baal_home(request):
    context = {}
    context['event'] = Event.objects.filter(title='Baal').first()
    baal_staticnav = StaticPageNav.objects.filter(category_name="Kemistbaal")
    if len(baal_staticnav) > 0:
        baal_staticpages = StaticPage.objects.filter(category=baal_staticnav[0].pk)
        context['staticpages'] = baal_staticpages
    return render(request, 'events/baal_detail.html', context)


class EventDetailView(DetailView):
    model = Event

    def get_template_names(self):
        template_name = 'events/detail.html'
        if self.get_context_data().get('event').title.lower() == 'baal':
           template_name = 'events/baal_anmalan.html'
        return template_name

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
        if self.get_context_data().get('event').title.lower() == 'baal':
            return redirect('/events/baal/#/anmalda')            
        return render(self.request, self.get_template_names(), self.get_context_data())

    def form_invalid(self, form):
        return render(self.request, self.get_template_names(), self.get_context_data(form=form))


def ws_send(request, form, public_info):
    ws_schema = 'ws' if request.scheme == 'http' else 'wss'
    url = request.META.get('HTTP_HOST')
    path = ws_schema + '://' + url + '/ws' + request.path
    try:
        ws = create_connection(path)
        ws.send(json.dumps(ws_data(form, public_info)))
        # Send ws again if avec
        if dict(form.cleaned_data).get('Avec') and dict(form.cleaned_data).get('Avec Namn'):
            newform = deepcopy(form)
            newform.cleaned_data['user'] = dict(newform.cleaned_data).get('Avec Namn')
            public_info = ''
            ws.send(json.dumps(ws_data(newform, public_info)))
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