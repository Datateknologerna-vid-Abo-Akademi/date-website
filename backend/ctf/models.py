import logging

from django_ckeditor_5.fields import CKEditor5Field
from django.db import models
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _

from members.models import Member

logger = logging.getLogger('date')

POST_SLUG_MAX_LENGTH = 50


class Ctf(models.Model):
    title = models.CharField(_('Titel'), max_length=255, blank=False)
    content = CKEditor5Field(_('Innehåll'), blank=True)
    start_date = models.DateTimeField(_('Startdatum'), default=now)
    end_date = models.DateTimeField(_('Slutdatum'), default=now)
    pub_date = models.DateTimeField(auto_now_add=True)
    slug = models.SlugField(_('Slug'), unique=True, allow_unicode=False, max_length=POST_SLUG_MAX_LENGTH)
    published = models.BooleanField(_('Publicera'), default=True)

    class Meta:
        verbose_name = _('ctf')
        verbose_name_plural = _('ctf')

    def __str__(self):
        return self.title

    def ctf_is_open(self):
        return now() >= self.start_date

    def ctf_ended(self):
        return now() > self.end_date


class Flag(models.Model):
    # uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ctf = models.ForeignKey(Ctf, on_delete=models.CASCADE)
    solver = models.ForeignKey(Member, on_delete=models.CASCADE, blank=True, null=True)
    title = models.CharField(max_length=200)
    flag = models.CharField(max_length=200)
    solved_date = models.DateTimeField(blank=True, null=True)
    clues = CKEditor5Field(_('Clue'), blank=True)
    slug = models.SlugField(_('Slug'), unique=True, allow_unicode=False, max_length=POST_SLUG_MAX_LENGTH)

    class Meta:
        verbose_name = _('Flag')
        verbose_name_plural = _('Flags')

    def __str__(self):
        return self.title


class Guess(models.Model):
    ctf = models.ForeignKey(Ctf, on_delete=models.CASCADE, verbose_name=_('CTF'))
    user = models.ForeignKey(Member, on_delete=models.CASCADE, verbose_name=_('Användare'))
    flag = models.ForeignKey(Flag, on_delete=models.CASCADE, verbose_name=_('Flagga'))
    guess = models.CharField(max_length=200, verbose_name=_('Gissning'))
    correct = models.BooleanField(default=False, verbose_name=_('Korrekt'))
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name=_('Tid'))

    class Meta:
        verbose_name = _('Gissning')
        verbose_name_plural = _('Gissningar')

    def __str__(self):
        return f'{self.ctf.title} - {self.flag.title} - {self.user.username} - {self.guess}'
