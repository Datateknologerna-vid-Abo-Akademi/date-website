import datetime
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
    logger.error("Error while loading alumni settings: " + str(e))
    ALUMNI_SETTINGS, AUTH, SHEET = {}, {}, ""


def log_action(operation: str, data: dict):
    worksheet = "audit_log"
    client = DateSheetsAdapter(AUTH, SHEET, worksheet)
    client.append_row([operation, json.dumps(data)])


def handle_create(form: dict):
    worksheet = "members"  # TODO change this
    client = DateSheetsAdapter(AUTH, SHEET, worksheet)
    print(client)
    try:
        member_id = int(client.get_last_row()[0]) + 1
    except ValueError:
        member_id = 1
    data = form

    if data["email"] in client.get_column_values(client.get_column_by_name("email")):
        logger.info("Alumni CREATE: Email already registered")
        return

    reference = generate_reference_number(generate_invoice_number())

    logger.info("Creating alumni member entry")
    try:
        client.append_row([
            member_id,
            data.get("firstname"),
            data.get("lastname"),
            data.get("address"),
            data.get("zip"),
            data.get("city"),
            data.get("country"),
            data.get("employer"),
            data.get("work_title"),
            data.get("phone_number"),
            data.get("email"),
            data.get("tfif_membership"),
            data.get("alumni_newsletter_consent"),
            data.get("year_of_admission"),
            datetime.datetime.now().isoformat(),
            datetime.datetime.now().isoformat(),
            0,  # Paid status
            reference,
        ])
    except Exception as e:
        logger.error("Error while creating alumni member: " + str(e))
        return

    logger.info("Creating alumni log entry")
    log_action("CREATE", data)


    logger.info("Sending Alumni email")
    alumni_email = form['email']
    alumni_message_subject = "Välkommen till ARG - Betalningsinstruktioner"
    alumni_message_content = render_to_string('members/alumni_signup_email.html', {"alumni": form})
    # Send email to alumni
    send_email_task.delay(alumni_message_subject, alumni_message_content, settings.DEFAULT_FROM_EMAIL,
                          [alumni_email])

    logger.info("Sending Alumni admin email")
    # Mail to relevant people
    admin_message_recipients = list(AlumniEmailRecipient.objects.all().values_list('recipient_email', flat=True))
    admin_message_subject = f"ARG - Ny medlem {form['firstname']+' ' + form['lastname']}"
    admin_message_content = render_to_string('members/alumni_signup_email_admin.html',
                                             {'alumni': form})
    # Schedule admin message
    send_email_task.delay(admin_message_subject, admin_message_content, settings.DEFAULT_FROM_EMAIL,
                          admin_message_recipients)


def handle_update(form):
    raise NotImplementedError()

@shared_task()
def handle_alumni_signup(form: dict):
    logger.info("Received alumni signup form with operation: " + form['operation'])
    match form["operation"]:
        case "CREATE":
            handle_create(form)
        case _:
            raise NotImplementedError()
