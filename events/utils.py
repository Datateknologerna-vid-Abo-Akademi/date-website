def get_attendee_price(cleaned_form, event, avec=False):
    form_prices = event.get_registration_form_prices()
    attendee_price = 0
    prefix = "avec_" if avec else ""
    for item in form_prices:
        if cleaned_form.get(prefix + item.name):
            price_field = prefix + item.name
            if isinstance(cleaned_form.get(price_field), str) and cleaned_form.get(price_field).strip().isdigit() and cleaned_form.get(price_field).strip() != "0":
                attendee_price += item.price * int(cleaned_form.get(price_field))
            else:
                attendee_price += item.price
    return attendee_price


def get_attendee_fields(cleaned_form):
    attendee_fields = {}
    attendee_avec_fields = {}
    for key, value in cleaned_form.items():
        if isinstance(value, bool) and value:
            value = "Ja"
        elif isinstance(value, bool) and not value:
            value = "Nej"

        if not key.startswith('avec_'):
            if key == "user":
                attendee_fields["Namn"] = value
            elif key == "anonymous":
                attendee_fields["Anonym"] = value
            else:
                attendee_fields[key] = value
        else:
            avec_key = key.replace("avec_", "")
            if avec_key == "user":
                attendee_avec_fields["Namn"] = value
            elif avec_key == "anonymous":
                attendee_avec_fields["Anonym"] = value
            else:
                attendee_avec_fields[avec_key] = value

    return attendee_fields, attendee_avec_fields
