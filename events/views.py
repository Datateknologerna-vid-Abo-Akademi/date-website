import datetime
import logging

from django.conf import settings
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import DetailView, ListView

from core.utils import validate_captcha
from members.models import Member
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
        today = timezone.now()
        context['event_list'] = events.filter(event_date_end__gte=today)
        context['past_events'] = events.filter(event_date_end__lte=today).reverse()
        return context


class EventDetailView(DetailView):
    model = Event
    template_name = 'events/detail.html'

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        external_link = self.object.redirect_link
        if external_link:
            return redirect(external_link)
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
        return context

    def get_template_names(self):
        event_title = self.get_context_data().get('event').title.lower()
        logger.debug(event_title)
        templates = {
            'årsfest': 'events/arsfest.html',
            'årsfest gäster': 'events/arsfest.html',
            '100 baal': 'events/kk100_detail.html',
            'baal': 'events/baal_detail.html',
            'tomtejakt': 'events/tomtejakt.html',
            'wappmiddag': 'events/wappmiddag.html'
        }
        slugmap = {
            'baal': 'events/baal_detail.html',
            'tomtejakt': 'events/tomtejakt.html',
            'wappmiddag': 'events/wappmiddag.html',
            'arsfest': 'events/arsfest.html',
            'arsfest_stipendiater': 'events/arsfest.html'
        }
        # Will return a 500 response to client if the template is not found
        if event_title in templates: # TODO: Selectable template
            return templates[event_title]
        elif (slug := self.get_context_data().get('event').slug) in slugmap:
            return slugmap[slug]

        if self.object.passcode and self.object.passcode != self.request.session.get('passcode_status', False):
            return ['events/event_passcode.html']
        return [self.template_name]

    def form_valid(self, form):
        attendee = self.get_object().add_event_attendance(user=form.cleaned_data['user'],
                                                          email=form.cleaned_data['email'],
                                                          anonymous=form.cleaned_data['anonymous'],
                                                          preferences=form.cleaned_data)
        if "event_billing" in settings.EXPERIMENTAL_FEATURES and 'billing' in settings.INSTALLED_APPS:
            from billing.handlers import handle_event_billing
            handle_event_billing(attendee)
        if 'avec' in form.cleaned_data and form.cleaned_data['avec']:
            self.handle_avec_data(form.cleaned_data, attendee)
        return self.redirect_after_signup()

    def form_invalid(self, form):
        if self.get_context_data().get('event').title.lower() in ['årsfest', 'årsfest gäster']:
            return render(self.request, 'events/arsfest.html', self.get_context_data(form=form))
        return render(self.request, self.template_name, self.get_context_data(form=form), status=400)

    def handle_passcode(self, request):
        if self.object.passcode and self.object.passcode != request.session.get('passcode_status', False):
            if self.object.passcode == request.POST.get('passcode'):
                request.session['passcode_status'] = self.object.passcode
                return self.render_to_response(self.get_context_data())
            else:
                return render(request, 'events/event_passcode.html',
                              self.get_context_data(passcode_error='invalid passcode'), status=401)
        return None

    def handle_event_signup(self, request):
        if not self.object.sign_up:
            return HttpResponseForbidden()

        user_authenticated = request.user.is_authenticated
        member_obj = Member.objects.filter(username=request.user.username).first()  # Check if user exists
        user_member = member_obj.get_active_subscription() is not None if member_obj else False
        open_for_members = self.object.registration_is_open_members()
        open_for_others = self.object.registration_is_open_others()
        commodore_group = request.user.groups.filter(name="commodore").exists()
        # Temp fix to allow commodore peeps to enter pre-signed

        # Check if user is allowed to sign up
        if self.object.sign_up and (user_authenticated and open_for_members and
                                    user_member or open_for_others or commodore_group):

            form = self.object.make_registration_form()(data=request.POST)

            # CAPTCHA validation if applicable
            if self.object.captcha:
                captcha_response = request.POST.get('cf-turnstile-response', '')
                if not validate_captcha(captcha_response):
                    return self.form_invalid(form)

            if form.is_valid():
                return self.process_signup_form(form, request)

            return self.form_invalid(form)
        return HttpResponseForbidden()

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
            return redirect(f"{reverse('events:detail', args=[event.slug])}#/anmalda")
        return redirect(reverse('events:detail', args=[event.slug]))

    def handle_avec_data(self, cleaned_data, attendee):
        avec_data = {'avec_for': attendee}
        for key in cleaned_data:
            if key.startswith('avec_'):
                field_name = key.split('avec_')[1]
                value = cleaned_data[key]
                avec_data[field_name] = value
        self.get_object().add_event_attendance(user=avec_data['user'], email=avec_data['email'],
                                               anonymous=avec_data['anonymous'], preferences=avec_data,
                                               avec_for=avec_data['avec_for'])
