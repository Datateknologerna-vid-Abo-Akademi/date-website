import json
import logging

from celery import shared_task
from django.conf import settings
from django.template.loader import render_to_string

from .forms import AlumniSignUpForm
from .gsuite_adapter import DateSheetsAdapter
from core.utils import send_email_task
from billing.util import generate_reference_number, generate_invoice_number
from .models import AlumniEmailRecipient

logger = logging.getLogger("date")


# Load settings
try:
    ALUMNI_SETTINGS = json.loads(settings.ALUMNI_SETTINGS)
    AUTH, SHEET = ALUMNI_SETTINGS.get("auth", {}), ALUMNI_SETTINGS.get("sheet")
except Exception as e:
    logger.error(e)
    ALUMNI_SETTINGS, AUTH, SHEET = {}, {}, ""


def log_action(operation: str, data: dict):
    worksheet = "audit_log"
    client = DateSheetsAdapter(AUTH, SHEET, worksheet)
    client.append_row([operation, json.dumps(data)])


def handle_create(form: AlumniSignUpForm):
    worksheet = "members"  # TODO change this
    client = DateSheetsAdapter(AUTH, SHEET, worksheet)
    member_id = int(client.get_last_row()[0]) + 1
    data = form.cleaned_data

    if data["email"] in client.get_column_values(client.get_column_by_name("email")):
        print("Alumni CREATE: Email already registered")
        return

    client.append_row([
        member_id,
        data["name"].split(" ")[0],
        data["name"].split(" ")[1],
        data["address"],
        data["zip"],
        data["city"],
        data["country"],
        data["employer"],
        data["work_title"],
        data["phone_number"],
        data["email"],
        data["tfif_membership"],
        data["alumni_newsletter_consent"],
        0,  # Paid status
    ])

    alumni_email = form.cleaned_data['email']
    alumni_message_subject = "Välkommen till ARG - Betalningsinstruktioner"
    alumni_message_content = render_to_string('members/alumni_signup_email.html')
    # Send email to alumni
    send_email_task.delay(alumni_message_subject, alumni_message_content, settings.DEFAULT_FROM_EMAIL,
                          [alumni_email])

    # Mail to relevant people
    admin_message_recipients = list(AlumniEmailRecipient.objects.all().values_list('recipient_email', flat=True))
    admin_message_subject = f"ARG - Ny medlem {form.cleaned_data['name']}"
    admin_message_content = render_to_string('members/alumni_signup_email_admin.html',
                                             {'alumni': form.cleaned_data})
    # Schedule admin message
    send_email_task.delay(admin_message_subject, admin_message_content, settings.DEFAULT_FROM_EMAIL,
                          admin_message_recipients)


def handle_update(form):
    raise NotImplementedError()

@shared_task()
def handle_alumni_signup(form: AlumniSignUpForm):
    match form.operation:
        case "CREATE":
            handle_create(form)
        case _:
            raise NotImplementedError()
