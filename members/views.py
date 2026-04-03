import datetime
import logging
import os

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.contrib.auth.hashers import make_password
from django.contrib.auth.views import PasswordChangeView, PasswordResetView
from django.contrib.sites.shortcuts import get_current_site
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _
from django.views import View

from core.utils import validate_captcha, send_email_task
from .constants import (
    TWO_FACTOR_SETUP_SESSION_KEY,
    TWO_FACTOR_VERIFIED_USER_ID_SESSION_KEY,
)
from .forms import (
    SignUpForm,
    FunctionaryForm,
    MemberEditForm,
    CustomPasswordResetForm,
    TwoFactorDisableForm,
    TwoFactorTokenForm,
)
from .functionary import (get_distinct_years, get_functionary_roles, get_selected_year,
                          get_selected_role, get_filtered_functionaries, get_functionaries_by_role)
from .models import Member, Functionary
from .two_factor import (
    build_qr_code_data_uri,
    build_totp_provisioning_uri,
    generate_two_factor_secret,
    verify_two_factor_token,
)
from .tokens import account_activation_token

logger = logging.getLogger('date')


class UserinfoView(View):
    @method_decorator(login_required)
    def get(self, request):
        user = request.user
        form = MemberEditForm(instance=user)  # Initialize form with user instance
        context = {
            "user": user,
            "form": form,
            "two_factor_enabled": user.has_2fa_enabled,
        }
        return render(request, 'members/userinfo.html', context)

    @method_decorator(login_required)
    def post(self, request):
        user = request.user
        form = MemberEditForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            # Redirect to the same page to display updated info
            return redirect(reverse('members:info'))  # Replace 'userinfo' with the name of this view in urls.py
        context = {
            "user": user,
            "form": form,
            "two_factor_enabled": user.has_2fa_enabled,
        }
        return render(request, 'members/userinfo.html', context)


class CertificateView(View):
    @method_decorator(login_required)
    def get(self, request):
        icons = ['atom', 'asterisk', 'poo', 'certificate', 'cog', 'compact-disc', 'snowflake']
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
        return render(request, 'members/certificate.html', context)


def signup(request):
    # If user has submitted the form show success page
    if request.session.get("signup_submitted", False):
        request.session['signup_submitted'] = False
        return render(request, 'members/registration/registration_complete.html')

    if request.method == 'POST':
        form = SignUpForm(request.POST)

        if not validate_captcha(request.POST.get('cf-turnstile-response', '')):
            return render(request, 'members/signup.html', {'form': form, 'alumni': False})

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
            message = render_to_string('members/acc_active_email.html', {
                'user': user,
                'domain': current_site.domain,
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),  # .decode(),
                'token': account_activation_token.make_token(user),
            })
            to_email = os.environ.get('EMAIL_HOST_RECEIVER')
            send_email_task.delay(mail_subject, message, settings.DEFAULT_FROM_EMAIL, [to_email])
            logger.info(f"NEW USER: Sending email to {to_email}")
            request.session['signup_submitted'] = True
            return redirect(request.path)
    else:
        form = SignUpForm()
    return render(request, 'members/signup.html', {'form': form})


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
        return render(request, 'members/userinfo.html', {"user": user, "msg": msg})
    else:
        return HttpResponse('Activation link is invalid!')



class CustomPasswordResetView(PasswordResetView):
    form_class = CustomPasswordResetForm


class CustomLoginView(LoginView):
    template_name = "members/registration/login.html"


class TwoFactorVerifyView(View):
    template_name = "members/registration/two_factor_verify.html"

    @method_decorator(login_required)
    def get(self, request):
        if not request.user.has_2fa_enabled:
            return redirect(self._get_safe_redirect_url(request) or reverse("members:info"))
        if request.session.get(TWO_FACTOR_VERIFIED_USER_ID_SESSION_KEY) == request.user.pk:
            return redirect(self._get_safe_redirect_url(request) or reverse("members:info"))

        context = {
            "form": TwoFactorTokenForm(),
            "next_url": self._get_safe_redirect_url(request),
        }
        return render(request, self.template_name, context)

    @method_decorator(login_required)
    def post(self, request):
        if not request.user.has_2fa_enabled:
            return redirect(reverse("members:info"))

        form = TwoFactorTokenForm(request.POST)
        next_url = self._get_safe_redirect_url(request)
        if form.is_valid():
            token = form.cleaned_data["token"]
            if verify_two_factor_token(request.user.two_factor_secret, token):
                request.session[TWO_FACTOR_VERIFIED_USER_ID_SESSION_KEY] = request.user.pk
                messages.success(request, _("Tvåfaktorsautentisering bekräftad."))
                return redirect(next_url or reverse("members:info"))
            form.add_error("token", _("Felaktig verifieringskod."))

        context = {
            "form": form,
            "next_url": next_url,
        }
        return render(request, self.template_name, context)

    def _get_safe_redirect_url(self, request):
        next_url = request.POST.get("next") or request.GET.get("next")
        if next_url and url_has_allowed_host_and_scheme(
            next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            return next_url
        return None


class TwoFactorSettingsView(View):
    template_name = "members/two_factor_settings.html"

    @method_decorator(login_required)
    def get(self, request):
        return render(request, self.template_name, self._get_context(request))

    @method_decorator(login_required)
    def post(self, request):
        action = request.POST.get("action")
        if action == "start_setup":
            if request.user.has_2fa_enabled:
                messages.info(request, _("Tvåfaktorsautentisering är redan aktiverad."))
            else:
                request.session[TWO_FACTOR_SETUP_SESSION_KEY] = generate_two_factor_secret()
            return redirect(reverse("members:two_factor_settings"))

        if action == "cancel_setup":
            request.session.pop(TWO_FACTOR_SETUP_SESSION_KEY, None)
            return redirect(reverse("members:two_factor_settings"))

        if action == "confirm_setup":
            return self._confirm_setup(request)

        if action == "disable":
            return self._disable_two_factor(request)

        return redirect(reverse("members:two_factor_settings"))

    def _confirm_setup(self, request):
        form = TwoFactorTokenForm(request.POST)
        setup_secret = request.session.get(TWO_FACTOR_SETUP_SESSION_KEY)
        if not setup_secret:
            messages.error(request, _("Ingen tvåfaktorskonfiguration väntar på bekräftelse."))
            return redirect(reverse("members:two_factor_settings"))

        if form.is_valid():
            token = form.cleaned_data["token"]
            if verify_two_factor_token(setup_secret, token):
                request.user.two_factor_secret = setup_secret
                request.user.two_factor_enabled_at = timezone.now()
                request.user.save(update_fields=["two_factor_secret", "two_factor_enabled_at"])
                request.session[TWO_FACTOR_VERIFIED_USER_ID_SESSION_KEY] = request.user.pk
                request.session.pop(TWO_FACTOR_SETUP_SESSION_KEY, None)
                messages.success(request, _("Tvåfaktorsautentisering aktiverades."))
                return redirect(reverse("members:two_factor_settings"))
            form.add_error("token", _("Felaktig verifieringskod."))

        return render(
            request,
            self.template_name,
            self._get_context(request, setup_form=form),
        )

    def _disable_two_factor(self, request):
        form = TwoFactorDisableForm(request.POST)
        if form.is_valid():
            if not request.user.check_password(form.cleaned_data["password"]):
                form.add_error("password", _("Fel lösenord."))
            elif not verify_two_factor_token(request.user.two_factor_secret, form.cleaned_data["token"]):
                form.add_error("token", _("Felaktig verifieringskod."))
            else:
                request.user.two_factor_secret = ""
                request.user.two_factor_enabled_at = None
                request.user.save(update_fields=["two_factor_secret", "two_factor_enabled_at"])
                request.session.pop(TWO_FACTOR_VERIFIED_USER_ID_SESSION_KEY, None)
                messages.success(request, _("Tvåfaktorsautentisering stängdes av."))
                return redirect(reverse("members:two_factor_settings"))

        return render(
            request,
            self.template_name,
            self._get_context(request, disable_form=form),
        )

    def _get_context(self, request, setup_form=None, disable_form=None):
        setup_secret = request.session.get(TWO_FACTOR_SETUP_SESSION_KEY, "")
        provisioning_uri = build_totp_provisioning_uri(request.user, setup_secret) if setup_secret else ""
        context = {
            "disable_form": disable_form or TwoFactorDisableForm(),
            "is_pending_setup": bool(setup_secret),
            "qr_code_data_uri": build_qr_code_data_uri(provisioning_uri) if provisioning_uri else "",
            "setup_form": setup_form or TwoFactorTokenForm(),
            "setup_secret": setup_secret,
            "two_factor_enabled": request.user.has_2fa_enabled,
        }
        return context


class FunctionaryView(View):
    template_name = 'members/functionary.html'

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

        return render(request, 'members/functionaries.html', context)


class CustomPasswordChangeView(PasswordChangeView):
    template_name = "members/registration/password_change_form.html"
