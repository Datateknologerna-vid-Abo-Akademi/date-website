import calendar
import datetime

from event_calendar.utils import Calendar

class CalendarManager():

    def __init__(self, request):
        self.date = self.get_date(request.GET.get('month', None))
        self.cal = Calendar(self.date.year, self.date.month)

    def prev_month(self):
        first = self.date.replace(day=1)
        prev = first - datetime.timedelta(days=1)
        month = 'month=' + str(prev.year) + '-' + str(prev.month)
        return month

    def next_month(self):
        days_in_month = calendar.monthrange(self.date.year, self.date.month)[1]
        last = self.date.replace(day=days_in_month)
        _next = last + datetime.timedelta(days=1)
        month = 'month=' + str(_next.year) + '-' + str(_next.month)
        return month

    def curr_month_as_string(self):
        return self.date.strftime("%B %Y")

    def get_date(self, req_day):
        if req_day:
            year, month = (int(x) for x in req_day.split('-'))
            return datetime.date(year, month, day=1)
        return datetime.date.today()

    def get_calendar(self):
        # self.date = get_date(request.GET.get('month', None))
        # cal = Calendar(date.year, date.month)
        _calendar = self.cal.formatmonth()
        return _calendar
