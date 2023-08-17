import logging
import os
import datetime
from smtplib import SMTPException

from django.contrib.auth.hashers import make_password
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import EmailMessage
from django.http import HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.translation import gettext_lazy as _
from django.views import View

from members.forms import SignUpForm, AlumniSignUpForm

from .models import Member, AlumniEmailRecipient
from .tokens import account_activation_token

logger = logging.getLogger('date')


class EditView(View):

    def get(self, request):
        user = request.user
        return render(request, 'userinfo.html', {"user": user})


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
    '''Handle signup form and email sending for new alumnis'''

    form = AlumniSignUpForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():

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
