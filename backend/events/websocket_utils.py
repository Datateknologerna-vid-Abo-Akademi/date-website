import logging
from copy import deepcopy
from django.utils.translation import gettext

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger('date')


def ws_send(event_slug, form, public_info):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(f"event_{event_slug}",
                                            {"type": "event_message", **ws_data(form, public_info)})
    # Send ws again if avec
    if dict(form.cleaned_data).get('avec'):
        newform = deepcopy(form)
        newform.cleaned_data['user'] = dict(newform.cleaned_data).get('avec_user')
        public_info = ''
        async_to_sync(channel_layer.group_send)(f"event_{event_slug}",
                                                {"type": "event_message", **ws_data(newform, public_info)})


def ws_data(form, public_info):
    pref = dict(form.cleaned_data)  # Creates copy of form

    fields = [] # (fieldName, value) tuples
    anonymous = pref['anonymous']

    fields.append(("user", gettext("Anonymt") if anonymous else pref['user']))
    # parse the public info and only send that through websockets.
    # the extra fields are reversed in the details.html template and must be reversed here too
    for info in reversed(public_info):
        key = str(info)
        if key in pref:
            fields.append(( info.name, str(pref[key]) )) # stringify the field value before sending, for consistency
    
    return {"data": { "fields": fields, "anonymous": anonymous }}
