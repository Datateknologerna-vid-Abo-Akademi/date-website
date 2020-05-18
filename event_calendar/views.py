import calendar
import datetime

from event_calendar.utils import Calendar


def prev_month(d):
    first = d.replace(day=1)
    prev = first - datetime.timedelta(days=1)
    month = 'month=' + str(prev.year) + '-' + str(prev.month)
    return month


def next_month(d):
    days_in_month = calendar.monthrange(d.year, d.month)[1]
    last = d.replace(day=days_in_month)
    _next = last + datetime.timedelta(days=1)
    month = 'month=' + str(_next.year) + '-' + str(_next.month)
    return month


def get_date(req_day):
    if req_day:
        year, month = (int(x) for x in req_day.split('-'))
        return datetime.date(year, month, day=1)
    return datetime.date.today()


def get_calendar(request):
    d = get_date(request.GET.get('month', None))
    cal = Calendar(d.year, d.month)
    _calendar = cal.formatmonth()
    return _calendar
