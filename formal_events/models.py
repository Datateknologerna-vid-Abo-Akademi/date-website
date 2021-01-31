from django.db import models
from ckeditor.fields import RichTextField
from django.utils.translation import ugettext_lazy as _
from django.utils.timezone import now
# Create your models here.

POST_SLUG_MAX_LENGTH = 50

class Formal_Event(models.Model):
    title = models.CharField(_('Titel'), max_length=255, blank=False)
    content = RichTextField(_('Innehåll'), blank=True)
    event_date_start = models.DateTimeField(_('Startdatum'), default=now)
    event_date_end = models.DateTimeField(_('Slutdatum'), default=now)
    
    sign_up_max_participants = models.IntegerField(_('Maximal antal deltagare'),
                                                   choices=[(0, u"Ingen begränsning")] + list(
                                                       zip(range(1, 500), range(1, 500))), default=0)
    sign_up_deadline = models.DateTimeField(_('Anmälningen stängs'), null=True, blank=True, default=now)
    created_time = models.DateTimeField(_('Skapad'), default=now)
    published_time = models.DateTimeField(_('Publicerad'), editable=False, null=True, blank=True)
    modified_time = models.DateTimeField(_('Modifierad'), editable=False, null=True, blank=True)
    published = models.BooleanField(_('Publicera'), default=True)
    slug = models.SlugField(_('Slug'), unique=True, allow_unicode=False, max_length=POST_SLUG_MAX_LENGTH, blank=True)

    class Meta:
        verbose_name = _('formellt evenemang')
        verbose_name_plural = _('formella evenemang')
        ordering = ('id',)

    def __str__(self):
        return self.title

class Formal_Static_Page(models.Model):
    event = models.ForeignKey(Formal_Event, on_delete=models.CASCADE, blank=True, null=True)
    title = models.CharField(_('Titel'), max_length=255, blank=False)
    content = RichTextField(_('Innehåll'), blank=True)
    created_time = models.DateTimeField(_('Skapad'), default=now)
    modified_time = models.DateTimeField(_('Modifierad'), editable=False, null=True, blank=True)
    slug = models.SlugField(_('Slug'), unique=True, allow_unicode=False, max_length=POST_SLUG_MAX_LENGTH)

    class Meta:
        verbose_name = _('Formellt evenemang static page')
        verbose_name_plural = _('Formella evenemang static page')
        ordering = ('id',)


    def __str__(self):
        return self.title
    
    
    #TODO ALL NEEDED FUNCTIONS GOES HERE

#TODO ADDITIONAL CLASSES HERE