import datetime
import os
from django.db import models
from django.conf import settings

from django.core.mail import EmailMessage
from django.http import HttpResponseForbidden, request
from django.views.generic import DetailView, ListView
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
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
        context['past_events'] = Event.objects.filter(published=True, event_date_end__lte=datetime.date.today()).order_by(
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
        if 'tomtejakt' in self.get_context_data().get('event').title.lower():
           template_name = 'events/tomtejakt.html'
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
        if self.object.sign_up and (request.user.is_authenticated
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
        attendee = self.get_object().add_event_attendance(user=form.cleaned_data['user'], email=form.cleaned_data['email'],
                                               anonymous=form.cleaned_data['anonymous'], preferences=form.cleaned_data)
        if 'avec' in form.cleaned_data and form.cleaned_data['avec']:
            avec_data = {'avec_for': attendee}
            for key in form.cleaned_data:
                if key.startswith('avec_'):
                    field_name = key.split('avec_')[1]
                    value = form.cleaned_data[key]
                    avec_data[field_name] = value
            self.get_object().add_event_attendance(user=avec_data['user'], email=avec_data['email'],
                                               anonymous=avec_data['anonymous'], preferences=avec_data, avec_for=avec_data['avec_for'])
        if self.get_context_data().get('event').title.lower() == 'baal':
            return redirect('/events/baal/#/anmalda') 
        return render(self.request, self.get_template_names(), self.get_context_data())

    def form_invalid(self, form):
        return render(self.request, self.get_template_names(), self.get_context_data(form=form))


def ws_send(request, form, public_info):
    ws_schema = 'ws' if settings.DEVELOP else 'wss'
    url = request.META.get('HTTP_HOST')
    if 'localhost' in url:
        url = 'localhost:8000'
    path = ws_schema + '://' + url + '/ws' + request.path
    try:
        ws = create_connection(path)
        ws.send(json.dumps(ws_data(form, public_info)))
        # Send ws again if avec
        logger.debug(dict(form.cleaned_data))
        if dict(form.cleaned_data).get('avec'):
            newform = deepcopy(form)
            newform.cleaned_data['user'] = dict(newform.cleaned_data).get('avec_user')
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

def send_baal_mail(form):
    mail_subject = 'XCVIII Kemistbaal Anmälan'
    for key, value in form.cleaned_data.items():
        if isinstance(value, bool):
            if value == True:
                form.cleaned_data[key] = 'Ja'
            else:
                form.cleaned_data[key] = 'Nej'
    message = render_to_string('events/baal_email.html', {
        'form': form.cleaned_data
    })
    to_email = form.cleaned_data['email']
    email = EmailMessage(
                mail_subject, message, to=[to_email]
    )
    logger.info(f"New Baal Attendance: Sending email to {to_email}")
    email.send()