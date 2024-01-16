import json
import logging
from websocket._exceptions import WebSocketBadStatusException
from websocket import create_connection
from core import settings

logger = logging.getLogger('date')


def ws_send(request, form, public_info):
    ws_schema = 'ws' if settings.DEVELOP else 'wss'
    url = request.META.get('HTTP_HOST')
    path = f'{ws_schema}://{url}/ws{request.path}'
    ws = None
    try:
        ws = create_connection(path)
        ws.send(json.dumps(ws_data(form.cleaned_data, public_info)))
        if 'avec' in form.cleaned_data:
            avec_data = form.cleaned_data.copy()
            avec_user = form.cleaned_data.get('avec_user')
            if avec_user:
                avec_data['user'] = avec_user
                ws.send(json.dumps(ws_data(avec_data, '')))
    except WebSocketBadStatusException as e:
        logger.error(f"WebSocket connection error: {e}")
    finally:
        if ws:
            ws.close()


def ws_data(cleaned_data, public_info):
    data = {'user': "Anonymous" if cleaned_data['anonymous'] else cleaned_data['user']}

    # Parse the public info and only send that through websockets.
    for info in public_info:
        if info in cleaned_data:
            data[info] = cleaned_data[info]

    return {"data": data}
