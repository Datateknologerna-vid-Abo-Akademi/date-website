from django.shortcuts import render
from django.template.loader import render_to_string
from django.conf import settings

from core.utils import validate_captcha, send_email_task

from .forms import AlumniSignUpForm
from .models import AlumniEmailRecipient
from .tasks import handle_alumni_signup


# Create your views here.

def alumni_signup(request):
    """Handle signup form and email sending for new alumnis"""

    form = AlumniSignUpForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        if not validate_captcha(request.POST.get('cf-turnstile-response', '')):
            return render(request, 'members/signup.html', {'form': form, 'alumni': True})

        handle_alumni_signup.delay(form)

        return render(request, 'members/registration/registration_complete.html', {'alumni': True})

    return render(request, 'members/signup.html', {'form': form, 'alumni': True})

