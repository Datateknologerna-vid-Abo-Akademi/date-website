from django.conf import settings
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse

from core.utils import enqueue_task_on_commit, send_email_task, validate_captcha

from .forms import HarassmentForm
from .models import HarassmentEmailRecipient


def harassment_form(request):
    form = HarassmentForm()
    if request.session.get("harass_submitted", False):
        request.session['harass_submitted'] = False
        return render(request, 'social/harassment_success.html')

    if request.method == 'POST':
        form = HarassmentForm(request.POST)
        if form.is_valid() and validate_captcha(request.POST.get('cf-turnstile-response')):
            harassment = form.save()
            harassment_receivers = [
                receiver.recipient_email
                for receiver in HarassmentEmailRecipient.objects.all()
            ]
            email_ctx = {
                'harassment': harassment,
                'harassment_url': (
                    f"{settings.CONTENT_VARIABLES['SITE_URL']}"
                    f"{reverse('admin:harassment_harassment_change', args=[harassment.id])}"
                ),
            }
            enqueue_task_on_commit(
                send_email_task,
                "Ny trakasserianmälan har inkommit",
                render_to_string('social/harassment_admin_email.html', email_ctx),
                settings.DEFAULT_FROM_EMAIL,
                harassment_receivers,
            )
            request.session['harass_submitted'] = True
            return redirect('social:harassment')

    return render(request, 'social/harassment_form.html', {'form': form})
