import logging
from copy import copy

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger('date')


def ws_send(request, form, public_info):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(f"event_{request.path.split('/')[-2]}",
                                            {"type": "event_message", **ws_data(form, public_info)})
    # Send ws again if avec
    if dict(form.cleaned_data).get('avec'):
        newform = copy(form)
        newform.cleaned_data['user'] = dict(newform.cleaned_data).get('avec_user')
        public_info = ''
        async_to_sync(channel_layer.group_send)(f"event_{request.path.split('/')[-2]}",
                                                {"type": "event_message", **ws_data(newform, public_info)})


def ws_data(form, public_info):
    data = {}
    pref = dict(form.cleaned_data)  # Creates copy of form

    data['user'] = "Anonymous" if pref['anonymous'] else pref['user']
    # parse the public info and only send that through websockets.
    for index, info in enumerate(public_info):
        if str(info) in pref:
            data[str(info)] = pref[str(info)]
    return {"data": data}
