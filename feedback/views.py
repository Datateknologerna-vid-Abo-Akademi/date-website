from django.conf import settings
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse

from core.utils import enqueue_task_on_commit, send_email_task, validate_captcha

from .forms import FeedbackSubmissionForm
from .models import FeedbackEmailRecipient, FeedbackFormSettings


def feedback_form(request):
    form = FeedbackSubmissionForm()
    if request.session.get('feedback_submitted', False):
        request.session['feedback_submitted'] = False
        return render(request, 'feedback/feedback_success.html')

    if request.method == 'POST':
        form = FeedbackSubmissionForm(request.POST)
        if form.is_valid() and validate_captcha(request.POST.get('cf-turnstile-response')):
            submission = form.save()
            feedback_receivers = [receiver.recipient_email for receiver in FeedbackEmailRecipient.objects.all()]
            email_ctx = {
                'submission': submission,
                'submission_url': (
                    f"{settings.CONTENT_VARIABLES['SITE_URL']}"
                    f"{reverse('admin:feedback_feedbacksubmission_change', args=[submission.id])}"
                ),
            }
            if feedback_receivers:
                enqueue_task_on_commit(
                    send_email_task,
                    "Ny feedback har inkommit",
                    render_to_string('feedback/feedback_admin_email.txt', email_ctx),
                    settings.DEFAULT_FROM_EMAIL,
                    feedback_receivers,
                )
            request.session['feedback_submitted'] = True
            return redirect('feedback:form')

    return render(
        request,
        'feedback/feedback_form.html',
        {'form': form, 'intro_text': FeedbackFormSettings.get_solo().intro_text},
    )
