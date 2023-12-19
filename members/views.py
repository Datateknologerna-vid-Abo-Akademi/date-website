import logging
import os
import datetime
from smtplib import SMTPException

from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import EmailMessage
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404, redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.translation import gettext_lazy as _
from django.views import View

from core.utils import validate_captcha
from members.forms import SignUpForm, AlumniSignUpForm, FunctionaryForm
from .functionary import (get_distinct_years, get_functionary_roles, get_selected_year,
                          get_selected_role, get_filtered_functionaries, get_functionaries_by_role)

from .models import Member, AlumniEmailRecipient, Functionary
from .tokens import account_activation_token

logger = logging.getLogger('date')


class UserinfoView(View):
    @method_decorator(login_required)
    def get(self, request):
        user = request.user
        context = {
            "user": user,
        }
        return render(request, 'userinfo.html', context)


class CertificateView(View):
    def get(self, request):
        icons = ['atom', 'asterisk', 'bahai', 'certificate', 'cog', 'compact-disc', 'snowflake']
        user = request.user
        current_time = datetime.datetime.now()

        icon_options = {
            'Monday': icons[0],
            'Tuesday': icons[1],
            'Wednesday': icons[2],
            'Thursday': icons[3],
            'Friday': icons[4],
            'Saturday': icons[5],
            'Sunday': icons[6],
        }
        icon = icon_options[current_time.strftime("%A")]

        context = {
            'user': user,
            'current_time': current_time,
            'icon': icon,
        }
        return render(request, 'certificate.html', context)


def signup(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)

        if not validate_captcha(request.POST.get('cf-turnstile-response', '')):
            return render(request, 'signup.html', {'form': form, 'alumni': True})
        
        if form.is_valid():
            # Create user
            user = form.save(commit=False)
            user.is_active = False
            user.password = make_password(form.cleaned_data['password'])
            user.save()
            # Send email of new user
            current_site = get_current_site(request)
            mail_subject = 'A new account has been created and required your attention.'
            print("Generated token: ", account_activation_token.make_token(user))
            message = render_to_string('acc_active_email.html', {
                'user': user,
                'domain': current_site.domain,
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),  # .decode(),
                'token': account_activation_token.make_token(user),
            })
            to_email = os.environ.get('EMAIL_HOST_RECEIVER')
            email = EmailMessage(
                mail_subject, message, to=[to_email]
            )
            logger.info(f"NEW USER: Sending email to {to_email}")
            email.send()
            return render(request, 'registration/registration_complete.html')
    else:
        form = SignUpForm()
    return render(request, 'signup.html', {'form': form})


def activate(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64)
        user = Member.objects.get(pk=uid)
    except(TypeError, ValueError, OverflowError, Member.DoesNotExist):
        user = None
    if user is not None and account_activation_token.check_token(user, token):
        user.is_active = True
        user.save()
        msg = _("Användare aktiverad")
        return render(request, 'userinfo.html', {"user": user, "msg": msg})
    else:
        return HttpResponse('Activation link is invalid!')


def alumni_signup(request):
    """Handle signup form and email sending for new alumnis"""

    form = AlumniSignUpForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        if not validate_captcha(request.POST.get('cf-turnstile-response', '')):
            return render(request, 'signup.html', {'form': form, 'alumni': True})

        alumni = form.save(commit=False)
        alumni.save()

        # Mail to the person signing up
        alumni_email = form.cleaned_data['email']
        alumni_message_subject = "Välkommen till ARG - Betalningsinstruktioner"
        alumni_message_content = render_to_string('alumni_signup_email.html')
        final_alumni_email = EmailMessage(alumni_message_subject, alumni_message_content, to=[alumni_email])

        # Mail to relevant people
        admin_message_recipients = list(AlumniEmailRecipient.objects.all().values_list('recipient_email', flat=True))
        admin_message_subject = f"ARG - Ny medlem {form.cleaned_data['name']}"
        admin_message_content = render_to_string('alumni_signup_email_admin.html', {'alumni': form.cleaned_data, 'alumni_id': alumni.id})
        final_admin_email = EmailMessage(admin_message_subject, admin_message_content, to=admin_message_recipients)

        # Send mails
        try:
            final_alumni_email.send()
            final_admin_email.send()
        except SMTPException:
            logger.error("Failed to send alumni signup email: %s", form.cleaned_data['name'])

        return render(request, 'registration/registration_complete.html', {'alumni': True})

    return render(request, 'signup.html', {'form': form, 'alumni': True})

class FunctionaryView(View):
    template_name = 'functionary.html'

    @method_decorator(login_required)
    def get(self, request):
        user = request.user
        functionaries = Functionary.objects.filter(member=user).order_by('-year')
        form = FunctionaryForm(initial={'member': user})
        context = {
            "user": user,
            "functionaries": functionaries,
            "form": form,
        }
        return render(request, self.template_name, context)

    @method_decorator(login_required)
    def post(self, request):
        if 'add_functionary' in request.POST:
            return self.add_functionary(request)
        elif 'delete_functionary' in request.POST:
            return self.delete_functionary(request)
        return redirect(reverse('members:functionary'))

    def add_functionary(self, request):
        form = FunctionaryForm(request.POST)
        form.instance.member = request.user
        if form.is_valid():
            form.save()
        else:
            user = request.user
            functionaries = Functionary.objects.filter(member=user).order_by('-year')
            context = {
                "user": user,
                "functionaries": functionaries,
                "form": form,
            }
            return render(request, self.template_name, context)
        return redirect(reverse('members:functionary'))

    def delete_functionary(self, request):
        functionary_id = request.POST.get('functionary_id')
        functionary = get_object_or_404(Functionary, id=functionary_id, member=request.user)
        functionary.delete()
        return redirect(reverse('members:functionary'))


class FunctionariesView(View):
    def get(self, request):
        distinct_years = get_distinct_years()
        functionary_roles = get_functionary_roles()

        selected_year, all_years = get_selected_year(request, distinct_years)
        selected_role, all_roles = get_selected_role(request, functionary_roles)
        board_functionaries = get_filtered_functionaries(
            selected_year, selected_role, True
        )
        board_functionaries_by_role = get_functionaries_by_role(board_functionaries)

        other_functionaries = get_filtered_functionaries(
            selected_year, selected_role, False
        )
        functionaries_by_role = get_functionaries_by_role(other_functionaries)

        context = {
            "board_functionaries_by_role": board_functionaries_by_role,
            "functionaries_by_role": functionaries_by_role,
            "distinct_years": distinct_years,
            "functionary_roles": functionary_roles,
            "selected_role": selected_role,
            "all_roles": all_roles,
            "selected_year": selected_year if isinstance(selected_year, int) else "Alla År",
            "all_years": all_years,
        }

        return render(request, 'functionaries.html', context)