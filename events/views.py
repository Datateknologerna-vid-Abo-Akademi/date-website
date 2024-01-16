import datetime
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.http import HttpResponseForbidden, HttpResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.generic import DetailView, ListView

from core.utils import validate_captcha
from members.models import Member
from staticpages.models import StaticPage, StaticPageNav
from .forms import PasscodeForm
from .models import Event, EventAttendees
from .websocket_utils import ws_send

logger = logging.getLogger('date')


class IndexView(ListView):
    model = Event
    template_name = 'events/index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        events = Event.objects.filter(published=True).order_by('event_date_start')
        today = datetime.date.today()
        context['event_list'] = events.filter(event_date_end__gte=today)
        context['past_events'] = events.filter(event_date_end__lte=today).reverse()
        return context


class EventDetailView(DetailView):
    model = Event
    template_name = 'events/detail.html'

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        response = self.handle_redirection(request)
        if response:
            return response
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        passcode_response = self.handle_passcode(request)
        if passcode_response:
            return passcode_response
        return self.handle_event_signup(request)

    def get_context_data(self, **kwargs):
        context = super(EventDetailView, self).get_context_data(**kwargs)
        form = kwargs.pop('form', None)
        if self.object.passcode and self.object.passcode != self.request.session.get('passcode_status', False):
            form = PasscodeForm
        if form:
            context['form'] = form
        else:
            context['form'] = self.object.make_registration_form()
        try:
            baal_staticnav = StaticPageNav.objects.filter(category_name="Årsfest")
            if baal_staticnav.exists():
                context['staticpages'] = StaticPage.objects.filter(category=baal_staticnav.first().pk)
        except Exception as e:
            logger.error(f"Error fetching static pages: {e}")
        return context

    def get_template_names(self):
        event_title = self.get_context_data().get('event').title.lower()
        logger.debug(event_title)
        if event_title in ['årsfest', 'årsfest gäster']:
            return ['events/arsfest.html']
        if self.object.passcode and self.object.passcode != self.request.session.get('passcode_status', False):
            return ['events/event_passcode.html']
        return [self.template_name]

    def form_valid(self, form):
        attendee = self.add_attendance(form.cleaned_data)
        if 'avec' in form.cleaned_data and form.cleaned_data['avec']:
            self.handle_avec_data(form.cleaned_data, attendee)
        return self.redirect_after_signup()

    def form_invalid(self, form):
        if self.get_context_data().get('event').title.lower() in ['årsfest', 'årsfest gäster']:
            return render(self.request, 'events/arsfest.html', self.get_context_data(form=form))
        return render(self.request, self.template_name, self.get_context_data(form=form), status=400)

    def handle_redirection(self, request):
        show_content = not self.object.members_only or request.user.is_authenticated
        if self.object.redirect_link and show_content:
            return redirect(self.object.redirect_link)
        if not show_content:
            return redirect(reverse('members:login'))

    def handle_passcode(self, request):
        if self.object.passcode and self.object.passcode != request.session.get('passcode_status', False):
            if self.object.passcode == request.POST.get('passcode'):
                request.session['passcode_status'] = self.object.passcode
                return self.render_to_response(self.get_context_data())
            else:
                return render(request, 'events/event_passcode.html',
                              self.get_context_data(passcode_error='invalid passcode'))
        return None

    def handle_event_signup(self, request):
        if not self.object.sign_up:
            return HttpResponseForbidden()

        user_authenticated = request.user.is_authenticated
        user_member = Member.objects.get(username=request.user.username).get_active_subscription() is not None
        registration_open_for_members = self.object.registration_is_open_members()
        registration_open_for_others = self.object.registration_is_open_others()
        user_in_commodore_group = request.user.groups.filter(name="commodore").exists()

        # Check if user is allowed to sign up
        if not (user_authenticated and (
                user_member and registration_open_for_members) or registration_open_for_others or user_in_commodore_group):
            return HttpResponseForbidden()

        form = self.object.make_registration_form()(data=request.POST)

        # CAPTCHA validation if applicable
        if self.object.captcha:
            captcha_response = request.POST.get('cf-turnstile-response', '')
            if not validate_captcha(captcha_response):
                return self.form_invalid(form)

        if form.is_valid():
            return self.process_signup_form(form, request)

        return self.form_invalid(form)

    def process_signup_form(self, form, request):
        public_info = self.object.get_registration_form_public_info()
        if not EventAttendees.objects.filter(email=form.cleaned_data['email'], event=self.object.id).first():
            logger.info(f"User {request.user} signed up with name: {form.cleaned_data['user']}")
            if not settings.TEST:
                ws_send(request, form, public_info)
        return self.form_valid(form)

    def redirect_after_signup(self):
        event = self.get_context_data().get('event')
        if event.title.lower() in ['årsfest', 'årsfest gäster']:
            return redirect(f"/events/{event.slug}/#/anmalda")
        return redirect(f"/events/{self.get_context_data().get('event').slug}

    def handle_avec_data(self, cleaned_data, attendee):
        avec_data = {'avec_for': attendee}
        avec_keys = [key for key in cleaned_data if key.startswith('avec_')]
        avec_data.update({key.split('avec_')[1]: cleaned_data[key] for key in avec_keys})
        self.add_attendance(avec_data)

    def add_attendance(self, data):
        return self.get_object().add_event_attendance(**data)


def date_25(request):
    context = {}
    return render(request, 'events/date_25.html', context)
