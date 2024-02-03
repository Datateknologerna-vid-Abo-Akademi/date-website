import datetime
import json
import logging
from copy import deepcopy

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.http import HttpResponseForbidden, HttpResponse
from django.shortcuts import render, redirect
from django.views.generic import DetailView, ListView
from websocket import create_connection
from websocket._exceptions import WebSocketBadStatusException

from core.utils import validate_captcha
from members.models import Member
from staticpages.models import StaticPage, StaticPageNav
from .forms import PasscodeForm
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
        context['past_events'] = Event.objects.filter(published=True,
                                                      event_date_end__lte=datetime.date.today()).order_by(
            'event_date_start').reverse()
        return context


class EventDetailView(DetailView):
    model = Event
    template_name = 'events/detail.html'

    def get_template_names(self):
        template_name = 'events/detail.html'
        logger.debug(self.get_context_data().get('event').title.lower())
        if (self.get_context_data().get('event').title.lower() == 'årsfest' or
                self.get_context_data().get('event').title.lower() == 'årsfest gäster'):
            template_name = 'events/arsfest.html'
        if self.object.passcode and self.object.passcode != self.request.session.get('passcode_status', False):
            template_name = 'events/event_passcode.html'

        return template_name

    def get_context_data(self, **kwargs):
        context = super(EventDetailView, self).get_context_data(**kwargs)
        form = kwargs.pop('form', None)
        if self.object.passcode and self.object.passcode != self.request.session.get('passcode_status', False):
            form = PasscodeForm
        if form:
            context['form'] = form
        else:
            context['form'] = self.object.make_registration_form()
        baal_staticnav = StaticPageNav.objects.filter(category_name="Årsfest")
        if len(baal_staticnav) > 0:
            baal_staticpages = StaticPage.objects.filter(category=baal_staticnav[0].pk)
            context['staticpages'] = baal_staticpages

        return context

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        show_content = not self.object.members_only or (self.object.members_only and request.user.is_authenticated)
        # Check if there's a redirect link
        redirect_link = self.object.redirect_link
        if redirect_link and show_content:
            return redirect(redirect_link)
        if not show_content:
            return redirect('/members/login')
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        # set passcode status to session if passcode is enabled
        if self.object.passcode and self.object.passcode != self.request.session.get('passcode_status', False):
            if self.object.passcode == request.POST.get('passcode'):
                self.request.session['passcode_status'] = self.object.passcode
                if (self.get_context_data().get('event').title.lower() == 'årsfest' or
                self.get_context_data().get('event').title.lower() == 'årsfest gäster'):
                    return render(self.request, 'events/arsfest.html', self.get_context_data())
                return render(self.request, 'events/detail.html', self.get_context_data())
            else:
                return render(self.request, 'events/event_passcode.html',
                              self.get_context_data(passcode_error='invalid passcode'))

        if self.object.sign_up and (request.user.is_authenticated
                                    and self.object.registration_is_open_members()
                                    and Member.objects.get(username=request.user.username).get_active_subscription() is not None
                                    or self.object.registration_is_open_others()
                                    or request.user.groups.filter(
                    name="commodore").exists()):  # Temp fix to allow commodore peeps to enter pre-signed up attendees
            form = self.object.make_registration_form().__call__(data=request.POST)
            if self.object.captcha:
                if not validate_captcha(request.POST.get('cf-turnstile-response', '')):
                    return self.form_invalid(form)
            if form.is_valid():
                public_info = self.object.get_registration_form_public_info()
                # Do not send ws data on refresh after initial signup.
                if not EventAttendees.objects.filter(email=request.POST.get('email'), event=self.object.id).first():
                    logger.info(f"User {request.user} signed up with name: {request.POST.get('user')}")
                    if not settings.TEST:
                        ws_send(request, form, public_info)
                return self.form_valid(form)
            return self.form_invalid(form)
        return HttpResponseForbidden()

    def form_valid(self, form):
        attendee = self.get_object().add_event_attendance(user=form.cleaned_data['user'],
                                                          email=form.cleaned_data['email'],
                                                          anonymous=form.cleaned_data['anonymous'],
                                                          preferences=form.cleaned_data)
        if 'avec' in form.cleaned_data and form.cleaned_data['avec']:
            avec_data = {'avec_for': attendee}
            for key in form.cleaned_data:
                if key.startswith('avec_'):
                    field_name = key.split('avec_')[1]
                    value = form.cleaned_data[key]
                    avec_data[field_name] = value
            self.get_object().add_event_attendance(user=avec_data['user'], email=avec_data['email'],
                                                   anonymous=avec_data['anonymous'], preferences=avec_data,
                                                   avec_for=avec_data['avec_for'])
        if (self.get_context_data().get('event').title.lower() == 'årsfest' or
                self.get_context_data().get('event').title.lower() == 'årsfest gäster'):
            return redirect(f"/events/{self.get_context_data().get('event').slug}/#/anmalda")
        return redirect(f"/events/{self.get_context_data().get('event').slug}")

    def form_invalid(self, form):
        if (self.get_context_data().get('event').title.lower() == 'årsfest' or
                self.get_context_data().get('event').title.lower() == 'årsfest gäster'):
            return render(self.request, 'events/arsfest.html', self.get_context_data(form=form))
        return render(self.request, self.template_name, self.get_context_data(form=form), status=400)


def ws_send(request, form, public_info):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(f"event_{request.path.split('/')[-2]}",
                                            {"type": "event_message", **ws_data(form, public_info)})
    # Send ws again if avec
    if dict(form.cleaned_data).get('avec'):
        newform = deepcopy(form)
        newform.cleaned_data['user'] = dict(newform.cleaned_data).get('avec_user')
        public_info = ''
        async_to_sync(channel_layer.group_send)(f"event_{request.path.split('/')[-2]}",
                                                {"type": "event_message", **ws_data(newform, public_info)})


def ws_data(form, public_info):
    data = {}
    pref = dict(form.cleaned_data)  # Creates copy of form

    data['user'] = "Anonymous" if pref['anonymous'] else pref['user']
    # parse the public info and only send that through websockets.
    for index, info in enumerate(public_info):
        if str(info) in pref:
            data[str(info)] = pref[str(info)]
    return {"data": data}


def date_25(request):
    context = {}
    return render(request, 'events/date_25.html', context)