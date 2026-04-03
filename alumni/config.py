import json
import logging

from django.conf import settings

logger = logging.getLogger("date")

MEMBER_SHEET_NAME = "members"
AUDIT_LOG_SHEET_NAME = "audit_log"


def get_alumni_sheet_config():
    raw_settings = getattr(settings, "ALUMNI_SETTINGS", "")
    if not raw_settings:
        return {}, ""

    try:
        alumni_settings = json.loads(raw_settings)
    except Exception as exc:
        logger.error("Error while loading alumni settings: %s", exc)
        return {}, ""

    return alumni_settings.get("auth", {}), alumni_settings.get("sheet", "")
