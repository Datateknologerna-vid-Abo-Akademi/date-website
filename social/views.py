from django.shortcuts import render, redirect
from django.conf import settings
from django.template.loader import render_to_string
from .forms import HarassmentForm
from .models import HarassmentEmailRecipient
from core.utils import send_email_task

# Create your views here.

def socialIndex(request):
    index = ""
    return render(request, 'social/socialIndex.html', {'index': index})


def harassment_form(request):
    form = HarassmentForm()
    # If user has submitted the form show success page
    if request.session.get("harass_submitted", False):
        request.session['harass_submitted'] = False
        return render(request, 'social/harassment_success.html')

    if request.method == 'POST':
        form = HarassmentForm(request.POST)
        if form.is_valid():
            harassment = form.save()  # Save the form data to the Harassment model
            # Send email to all harassment email receivers
            harassment_receivers = [receiver.recipient_email for receiver in HarassmentEmailRecipient.objects.all()]
            email_ctx = {
                'harassment': harassment,
                'harassment_url': f"{settings.CONTENT_VARIABLES['SITE_URL']}/admin/social/harassment/{harassment.id}"
            }
            send_email_task.delay(
                "Ny trakasserianmälan har inkommit",
                render_to_string('social/harassment_admin_email.html', email_ctx),
                settings.DEFAULT_FROM_EMAIL,
                harassment_receivers
            )
            request.session['harass_submitted'] = True
            # Redirect to a success page or perform other actions
            return redirect(request.path)  # Redirect to a success page

    # If the form is not valid or it's a GET request, re-render the form with errors
    return render(request, 'social/harassment_form.html', {'form': form})
