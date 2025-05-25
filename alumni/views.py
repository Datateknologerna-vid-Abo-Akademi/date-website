import logging

from django.shortcuts import render, redirect

from core.utils import validate_captcha

from .gsuite_adapter import DateSheetsAdapter
from .models import AlumniUpdateToken
from .forms import AlumniSignUpForm, AlumniUpdateForm, AlumniEmailVerificationForm
from .tasks import handle_alumni_signup, send_token_email, update_alumni_task, AUTH, SHEET, MEMBER_SHEET_NAME

log = logging.getLogger("date")

# Create your views here.

def alumni_signup(request):
    """Handle signup form and email sending for new alumnis"""

    form = AlumniSignUpForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        if not validate_captcha(request.POST.get('cf-turnstile-response', '')):
            return render(request, 'members/signup.html', {'form': form, 'alumni': True})

        client = DateSheetsAdapter(AUTH, SHEET, MEMBER_SHEET_NAME)
        
        if form.cleaned_data["email"] in client.get_column_values(client.get_column_by_name("email")):
            log.info("Alumni CREATE: Email already registered")
            return render(request, 'members/signup.html', {'form': form, 'alumni': True, 'error': 'Email already registered.'})

        handle_alumni_signup.delay(form.cleaned_data)

        return render(request, 'members/registration/registration_complete.html', {'alumni': True})

    return render(request, 'members/signup.html', {'form': form, 'alumni': True})


def alumni_update_form(request, token):
    """Render the alumni update form with a token for verification."""
    if request.method == 'GET':
        # Check if the token is valid
        try:
            token = AlumniUpdateToken.objects.get(token=token)
            assert token.is_valid()
        except (AlumniUpdateToken.DoesNotExist, AssertionError):
            log.info(f"Invalid token: {token}")
            return redirect('alumni:alumni_update_no_token')
        form = AlumniUpdateForm(token=token)
        return render(request, 'alumni/alumni_update_form.html', {'form': form})
    elif request.method == 'POST':
        form = AlumniUpdateForm(request.POST, token=token)
        if form.is_valid():
            # Process the form data
            if form.cleaned_data['token'] is None or not AlumniUpdateToken.objects.filter(token=form.cleaned_data['token']).is_valid():
                return render(request, 'alumni/alumni_update_form.html', {'form': form, 'error': 'Invalid token.'}, status=403)

            AlumniUpdateToken.objects.filter(token=form.cleaned_data['token']).delete()
            update_alumni_task.delay(form.cleaned_data)

            return redirect('alumni:alumni_update_complete')
    return 405


def alumni_update(request):
    """Handle the alumni update form submission."""
    if request.method == 'POST':
        form = AlumniEmailVerificationForm(request.POST)
        if form.is_valid():
            token = AlumniUpdateToken(email=form.cleaned_data['email'])
            token.save()
            
            send_token_email.delay(token.token, form.cleaned_data['email'])

            return redirect('alumni:alumni_check_email')
    elif request.method == 'GET':
        form = AlumniUpdateForm()
        return render(request, 'alumni/alumni_update_form.html', {'form': form})
    return 405
