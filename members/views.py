import datetime
import logging
import os

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.contrib.auth.views import PasswordChangeView, PasswordResetView
from django.contrib.sites.shortcuts import get_current_site
from django.http import HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.translation import gettext_lazy as _
from django.views import View

from core.utils import validate_captcha, send_email_task
from members.forms import SignUpForm, AlumniSignUpForm
from .models import Member, AlumniEmailRecipient
from .forms import CustomPasswordResetForm
from .tokens import account_activation_token

logger = logging.getLogger('date')


class EditView(View):
    @method_decorator(login_required)
    def get(self, request):
        user = request.user
        return render(request, 'userinfo.html', {"user": user})


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
            return render(request, 'signup.html', {'form': form, 'alumni': False})

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
            send_email_task.delay(mail_subject, message, settings.DEFAULT_FROM_EMAIL, [to_email])
            logger.info(f"NEW USER: Sending email to {to_email}")
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
        alumni_message_subject = "Välkommen till ASG - Betalningsinstruktioner"
        alumni_message_content = render_to_string('alumni_signup_email.html')
        # Send email to alumni
        send_email_task.delay(alumni_message_subject, alumni_message_content, settings.DEFAULT_FROM_EMAIL,
                              [alumni_email])

        # Mail to relevant people
        admin_message_recipients = list(AlumniEmailRecipient.objects.all().values_list('recipient_email', flat=True))
        admin_message_subject = f"ASG - Ny medlem {form.cleaned_data['name']}"
        admin_message_content = render_to_string('alumni_signup_email_admin.html', {'alumni': form.cleaned_data, 'alumni_id': alumni.id})

        # Schedule admin message
        send_email_task.delay(admin_message_subject, admin_message_content, settings.DEFAULT_FROM_EMAIL,
                              admin_message_recipients)

        return render(request, 'registration/registration_complete.html', {'alumni': True})

    return render(request, 'signup.html', {'form': form, 'alumni': True})


class CustomPasswordResetView(PasswordResetView):
    form_class = CustomPasswordResetForm


class CustomPasswordChangeView(PasswordChangeView):
    template_name = "registration/password_change_form.html"
