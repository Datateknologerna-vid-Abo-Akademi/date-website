from django.core.exceptions import ImproperlyConfigured


REQUIRED_CONTENT_VARIABLE_KEYS = (
    "SITE_URL",
    "ASSOCIATION_NAME",
    "ASSOCIATION_NAME_SHORT",
    "ASSOCIATION_EMAIL",
    "SOCIAL_BUTTONS",
)

REQUIRED_THEME_KEYS = (
    "brand",
    "font_heading",
    "font_body",
    "palette",
)

REQUIRED_THEME_PALETTE_KEYS = (
    "background",
    "surface",
    "text",
    "text_muted",
    "primary",
    "secondary",
    "accent",
    "border",
)

REQUIRED_BILLING_CONTEXT_KEYS = (
    "INVOICE_RECIPIENT",
    "IBAN",
    "BIC",
)


def _raise(message):
    raise ImproperlyConfigured(message)


def _validate_string(value, setting_name):
    if not isinstance(value, str) or not value.strip():
        _raise(f"{setting_name} must be a non-empty string.")


def _validate_content_variables(settings_name, content_variables):
    if not isinstance(content_variables, dict):
        _raise(f"{settings_name}.CONTENT_VARIABLES must be a dict.")

    for key in REQUIRED_CONTENT_VARIABLE_KEYS:
        if key not in content_variables:
            _raise(f"{settings_name}.CONTENT_VARIABLES is missing required key '{key}'.")

    for key in ("SITE_URL", "ASSOCIATION_NAME", "ASSOCIATION_NAME_SHORT", "ASSOCIATION_EMAIL"):
        _validate_string(content_variables.get(key), f"{settings_name}.CONTENT_VARIABLES['{key}']")

    social_buttons = content_variables.get("SOCIAL_BUTTONS")
    if not isinstance(social_buttons, list):
        _raise(f"{settings_name}.CONTENT_VARIABLES['SOCIAL_BUTTONS'] must be a list.")

    for index, button in enumerate(social_buttons):
        if not isinstance(button, (list, tuple)) or len(button) != 2:
            _raise(
                f"{settings_name}.CONTENT_VARIABLES['SOCIAL_BUTTONS'][{index}] must be a 2-item list [icon, url]."
            )
        icon, url = button
        _validate_string(icon, f"{settings_name}.CONTENT_VARIABLES['SOCIAL_BUTTONS'][{index}][0]")
        _validate_string(url, f"{settings_name}.CONTENT_VARIABLES['SOCIAL_BUTTONS'][{index}][1]")


def _validate_association_theme(settings_name, association_theme):
    if not isinstance(association_theme, dict):
        _raise(f"{settings_name}.ASSOCIATION_THEME must be a dict.")

    for key in REQUIRED_THEME_KEYS:
        if key not in association_theme:
            _raise(f"{settings_name}.ASSOCIATION_THEME is missing required key '{key}'.")

    for key in ("brand", "font_heading", "font_body"):
        _validate_string(association_theme.get(key), f"{settings_name}.ASSOCIATION_THEME['{key}']")

    palette = association_theme.get("palette")
    if not isinstance(palette, dict):
        _raise(f"{settings_name}.ASSOCIATION_THEME['palette'] must be a dict.")

    for key in REQUIRED_THEME_PALETTE_KEYS:
        if key not in palette:
            _raise(f"{settings_name}.ASSOCIATION_THEME['palette'] is missing required key '{key}'.")
        _validate_string(palette.get(key), f"{settings_name}.ASSOCIATION_THEME['palette']['{key}']")


def _validate_billing_context(settings_name, installed_apps, feature_flags, billing_context):
    if "event_billing" not in feature_flags:
        return
    if "billing" not in installed_apps:
        _raise(f"{settings_name}.EXPERIMENTAL_FEATURES includes 'event_billing' but billing app is not installed.")
    if not isinstance(billing_context, dict):
        _raise(f"{settings_name}.BILLING_CONTEXT must be defined when 'event_billing' is enabled.")
    for key in REQUIRED_BILLING_CONTEXT_KEYS:
        if key not in billing_context:
            _raise(f"{settings_name}.BILLING_CONTEXT is missing required key '{key}'.")
        _validate_string(billing_context.get(key), f"{settings_name}.BILLING_CONTEXT['{key}']")


def validate_association_settings(settings_name, namespace):
    content_variables = namespace.get("CONTENT_VARIABLES")
    association_theme = namespace.get("ASSOCIATION_THEME")
    landing_route = namespace.get("FRONTEND_DEFAULT_ROUTE", "/")
    feature_flags = namespace.get("EXPERIMENTAL_FEATURES", [])
    installed_apps = namespace.get("INSTALLED_APPS", [])
    billing_context = namespace.get("BILLING_CONTEXT")

    _validate_content_variables(settings_name, content_variables)
    _validate_association_theme(settings_name, association_theme)

    if not isinstance(landing_route, str) or not landing_route.startswith("/"):
        _raise(f"{settings_name}.FRONTEND_DEFAULT_ROUTE must be an absolute path starting with '/'.")

    if not isinstance(feature_flags, list) or not all(isinstance(flag, str) for flag in feature_flags):
        _raise(f"{settings_name}.EXPERIMENTAL_FEATURES must be a list of strings.")

    if not isinstance(installed_apps, list):
        _raise(f"{settings_name}.INSTALLED_APPS must be a list.")

    _validate_billing_context(settings_name, installed_apps, feature_flags, billing_context)
