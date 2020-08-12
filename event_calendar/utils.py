from datetime import datetime, timedelta
from calendar import HTMLCalendar
from events.models import Event


class Calendar(HTMLCalendar):
    def __init__(self, year=None, month=None):
        self.year = year
        self.month = month
        super(Calendar, self).__init__()

    # formats a day as a td
    # filter events by day
    def formatday(self, day, events):
        events_per_day = events.filter(event_date_start__day=day)
        d = ''
        a = ''
        for event in events_per_day:
            d += f'<a class="tooltip" href=/events/{event.slug}>'
            d += f'<span class="tooltiptext">{event.title}</span>'
            a += f'</a>'

        if day != 0:
            return f"<td class='day'>{d}{day}{a}</td>"
        return '<td></td>'

    # formats a week as a tr
    def formatweek(self, the_week, events, **kwargs):
        week = ''
        for d, _ in the_week:
            week += self.formatday(d, events)
        return f'<tr class="weekday"> {week} </tr>'

    # formats a month as a table
    # filter events by year and month
    def formatmonth(self, with_year=True, **kwargs):
        events = Event.objects.filter(event_date_start__year=self.year, event_date_start__month=self.month)

        cal = ""
        # cal += f'{self.formatmonthname(self.year, self.month, withyear=with_year)}\n'
        cal += f'{self.formatweekheader()}\n'
        for week in self.monthdays2calendar(self.year, self.month):
            cal += f'{self.formatweek(week, events)}\n'
        return cal
