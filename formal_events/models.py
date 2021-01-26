from django.db import models
from ckeditor.fields import RichTextField
from django.utils.translation import ugettext_lazy as _

# Create your models here.

class Event(models.Model):
    title = models.CharField(_('Titel'), max_length=255, blank=False)
    content = RichTextField(_('Innehåll'), blank=True)
    #TODO ALL OTHER NEEDED FIELDS GOES HERE

    class Meta:
        verbose_name = _('fromellt evenemang')
        verbose_name_plural = _('formella evenemang')
        ordering = ('id',)
    
    #TODO ALL NEEDED FUNCTIONS GOES HERE

#TODO ADDITIONAL CLASSES HERE