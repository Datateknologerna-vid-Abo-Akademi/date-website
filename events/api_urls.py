from django.urls import re_path

from . import api

app_name = 'events'

urlpatterns = [
    re_path(r'^upcoming/$', api.upcoming_events, name='upcoming'),
]
