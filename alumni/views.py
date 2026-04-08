import logging

from django.shortcuts import render, redirect
from django.utils import timezone

from core.utils import enqueue_task_on_commit, validate_captcha

from .gsuite_adapter import DateSheetsAdapter
from .models import AlumniUpdateToken
from .forms import AlumniSignUpForm, AlumniUpdateForm, AlumniEmailVerificationForm
from .tasks import handle_alumni_signup, send_token_email
from .config import MEMBER_SHEET_NAME, get_alumni_sheet_config

log = logging.getLogger("date")

# Create your views here.


def _serialize_alumni_payload(cleaned_data):
    payload = dict(cleaned_data)
    token = payload.get("token")
    if token:
        payload["token"] = str(token)
    return payload


def alumni_signup(request):
    """Handle signup form and email sending for new alumnis"""

    form = AlumniSignUpForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        if not validate_captcha(request.POST.get('cf-turnstile-response', '')):
            return render(request, 'members/signup.html', {'form': form, 'alumni': True})

        auth, sheet = get_alumni_sheet_config()
        client = DateSheetsAdapter(auth, sheet, MEMBER_SHEET_NAME)
        
        if form.cleaned_data["email"] in client.get_column_values(client.get_column_by_name("email")):
            log.info("Alumni CREATE: Email already registered")
            return render(request, 'members/signup.html', {'form': form, 'alumni': True, 'error': 'Email already registered.'})

        handle_alumni_signup.delay(_serialize_alumni_payload(form.cleaned_data))

        return render(request, 'members/registration/registration_complete.html', {'alumni': True})

    return render(request, 'members/signup.html', {'form': form, 'alumni': True})


def alumni_update_form(request, token):
    """Render the alumni update form with a token for verification."""
    # Check if the token is valid
    try:
        token = AlumniUpdateToken.objects.get(token=token)
        assert token.is_valid()
    except (AlumniUpdateToken.DoesNotExist, AssertionError):
        log.info(f"Invalid token: {token}")
        return redirect('alumni:alumni_update')
    
    initial_data = {
        'email': token.email,
        'token': token.token,
    }

    if request.method == 'GET':
        form = AlumniUpdateForm(
            initial=initial_data)
        return render(request, 'members/signup.html', {'form': form, 'alumni': True})
    elif request.method == 'POST':
        form = AlumniUpdateForm(request.POST, initial=initial_data)
        if form.is_valid():
            handle_alumni_signup.delay(
                _serialize_alumni_payload(form.cleaned_data),
                timezone.now().isoformat(),
            )
            return render(request, "alumni/update_complete.html")
        return render(request, 'members/signup.html', {'form': form, 'alumni': True, }, status=400)
    return 405



def alumni_update_verify(request):
    """Handle the alumni update form submission."""
    if request.method == 'POST':
        form = AlumniEmailVerificationForm(request.POST)
        if not validate_captcha(request.POST.get('cf-turnstile-response', '')):
            return render(request, 'alumni/update_verify.html', {'form': form})

        if form.is_valid():
            token = AlumniUpdateToken(email=form.cleaned_data['email'])
            token.save()
            
            enqueue_task_on_commit(send_token_email, str(token.token), form.cleaned_data['email'])

            return render(request, 'alumni/check_email.html')
    elif request.method == 'GET':
        form = AlumniEmailVerificationForm()
        return render(request, 'alumni/update_verify.html', {'form': form})
    return 405
