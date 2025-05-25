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
from .models import AlumniEmailRecipient, AlumniUpdateToken

logger = logging.getLogger("date")


# Load settings
try:
    ALUMNI_SETTINGS = json.loads(settings.ALUMNI_SETTINGS)
    AUTH, SHEET = ALUMNI_SETTINGS.get("auth", {}), ALUMNI_SETTINGS.get("sheet")
except Exception as e:
    logger.error("Error while loading alumni settings: " + str(e))
    ALUMNI_SETTINGS, AUTH, SHEET = {}, {}, ""

MEMBER_SHEET_NAME = "members"  # This should match the actual sheet name in your Google Sheets
AUDIT_LOG_SHEET_NAME = "audit_log"  # This should match the actual sheet name for audit logs


def log_action(operation: str, data: dict):
    worksheet = AUDIT_LOG_SHEET_NAME
    client = DateSheetsAdapter(AUTH, SHEET, worksheet)
    client.append_row([operation, json.dumps(data)])


def handle_create(form: dict):
    worksheet = MEMBER_SHEET_NAME
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
    worksheet = MEMBER_SHEET_NAME
    client = DateSheetsAdapter(AUTH, SHEET, worksheet)
    
    token = form.get('token')
    if not token:
        logger.error("Alumni UPDATE: No token provided")
        return
    # Validate token from db
    try:
        alumni_token = AlumniUpdateToken.objects.get(token=token)
        if not alumni_token.is_valid() or alumni_token.email != form['email']:
            logger.error("Alumni UPDATE: Invalid or expired token")
            return
    except AlumniUpdateToken.DoesNotExist:
        logger.error("Alumni UPDATE: Token does not exist")
        return

    try:
        emails = client.get_column_values(client.get_column_by_name("email"))
        row = emails.index(form['email']) + 1 if form['email'] in emails else None
        row_data = client.get_row_values(row) if row else None
        if not (row and row_data):
            logger.info("Alumni UPDATE: Email not found")
            return

    except Exception as e:
        logger.error("Error while fetching alumni row: " + str(e))
        return

    # Update the row with new data
    try:
        client.update_row(row, [            
            None,  # Member ID is not updated
            form.get("firstname"),
            form.get("lastname"),
            form.get("address"),
            form.get("zip"),
            form.get("city"),
            form.get("country"),
            form.get("employer"),
            form.get("work_title"),
            form.get("phone_number"),
            None,  # Email is not updated
            form.get("tfif_membership"),
            form.get("alumni_newsletter_consent"),
            form.get("year_of_admission"),
            None, # Creation time is not updated
            datetime.datetime.now().isoformat(),
            None,  # Paid status
            None,  # Reference
        ])
    except Exception as e:
        logger.error("Error while updating alumni row: " + str(e))
        return
    
    logger.info("Updating alumni log entry")
    log_action("UPDATE", form)

    # Delete the token after successful update
    logger.info("Deleting alumni update token")
    alumni_token.delete()


def send_token_email(token: str, email: str):
    """Send an email with the token to the alumni."""
    subject = _("Uppdatera dina uppgifter")
    context = {
        'token': token,
        'base_url': settings.CONTENT_VARIABLES.get("SITE_URL", "https://datateknologerna.org"),
        'alumini_association_name': settings.CONTENT_VARIABLES.get("ALUMNI_ASSOCIATION_NAME", "Albins R Gamyler"),
    }
    message = render_to_string('alumni/alumni_update_token_email.html', context)
    send_email_task.delay(subject, message, settings.DEFAULT_FROM_EMAIL, [email])


@shared_task()
def handle_alumni_signup(form: dict):
    logger.info("Received alumni signup form with operation: " + form['operation'])
    match form["operation"]:
        case "CREATE":
            handle_create(form)
        case "UPDATE":
            handle_update(form)
        case _:
            raise NotImplementedError()
