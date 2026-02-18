import re

from django.urls import reverse
from django.utils import timezone
from django.utils.html import strip_tags
from django_ical.views import ICalFeed

from events.models import Event


class EventFeed(ICalFeed):
    product_id = '-//date.abo.fi//feed//EN'
    timezone = timezone.get_current_timezone_name()
    file_name = "DaTe-events.ics"

    def __call__(self, request, *args, **kwargs):
        self.host = request.get_host()
        return super(EventFeed, self).__call__(request, *args, **kwargs)

    def items(self):
        return Event.objects.filter(published=True).order_by('-event_date_start')

    def item_guid(self, item):
        return "{}{}".format(item.id, 'date.abo.fi')

    def item_title(self, item):
        return "{}".format(item.title)

    def item_description(self, item):
        text_only = re.sub('[ \t]+', ' ', strip_tags(item.content))
        return text_only.replace('\n ', '\n').strip()

    def item_start_datetime(self, item):
        return item.event_date_start

    def item_end_datetime(self, item):
        return item.event_date_end

    def item_created(self, item):
        return item.created_time

    def item_updateddate(self, item):
        return item.modified_time

    def item_link(self, item):
        return '{a}{b}'.format(a=self.host, b=reverse('events:detail', args=[item.slug]))
