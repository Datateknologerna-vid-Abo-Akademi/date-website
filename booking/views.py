import logging
from django.views.generic import ListView
from .models import Room

# Create your views here.
logger = logging.getLogger('date')


class IndexView(ListView):
    model = Room
    template_name = 'booking/index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        rooms = Room.objects.order_by('name')
        context['room_list'] = rooms
        return context