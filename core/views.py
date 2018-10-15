import datetime

from django.shortcuts import render, redirect
from django.utils import translation

from date import settings
from events.models import Event
from news.models import Post

def index(request):
    events = Event.objects.filter(published=True, event_date_end__gte=datetime.date.today()).reverse()[:5]
    news = Post.objects.filter(published=True).reverse()[:5]
    return render(request, 'start/start.html', {'events':events, 'news': news})


def language(request, lang):
    if str(lang).lower() == 'fi':
        lang = settings.LANG_FINNISH
    else:
        lang = settings.LANG_SWEDISH
    translation.activate(lang)
    request.session[translation.LANGUAGE_SESSION_KEY] = lang
    # response = http.HttpResponse()
    # response.set_cookie()
    origin = request.META.get('HTTP_REFERER')
    return redirect(origin)
