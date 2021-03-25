from django.shortcuts import render
from django.views.generic import ListView, DetailView
from django.shortcuts import get_object_or_404
from .models import FormalEvent, FormalStaticPage


#TODO: list formalevent under /formal
#TODO: /formal/event should redirect to first staticpage.




# Create your views here.

class IndexView(ListView):
    model = FormalEvent
    template_name = 'formal_events/index.html'

#TODO CREATE DETAIL TEXT VIEW
class DetailView(DetailView): #Homepage of formal event
    model = FormalEvent
    template_name = 'formal_events/detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context

def static_view(request, slug, static_slug):
    #TODO: koll så att staticpagen tillhör formalevent
    static_page = FormalStaticPage.objects.get(slug=static_slug) 
    event = FormalEvent.objects.get(slug=slug)
    static_page_list = FormalStaticPage.objects.filter(event=event)

    return render(request, 'formal_events/static.html', {
            'static_page': static_page,
            'error_message': "Du valde inget alternativ.",
            'static_page_list': static_page_list,
            'slug': slug
        })




#TODO CREATE SINGUPFORM VIEW

#TODO CREATE SIGNED UP PEOPLE VIEW