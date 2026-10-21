from django import forms
from django.conf import settings
from django.urls import NoReverseMatch, reverse
from django.utils.html import format_html, format_html_join
from django.utils.translation import gettext_lazy as _

from .models import StaticPage, StaticUrl

if getattr(settings, 'USE_UNFOLD', False):
    from unfold.widgets import UnfoldAdminTextInputWidget

    _TextInputBase = UnfoldAdminTextInputWidget
else:
    _TextInputBase = forms.TextInput


# Sections an editor is likely to link from the navigation. Each entry is
# resolved through reverse(), so a route that an association does not install
# simply drops out instead of offering a dead URL.
COMMON_NAV_TARGETS = (
    (_('Startsidan'), 'index'),
    (_('Nyheter'), 'news:index'),
    (_('Evenemang'), 'events:index'),
    (_('Medlemssidor'), 'members:info'),
    (_('Logga in'), 'members:login'),
    (_('Publikationer'), 'publications:pdf_list'),
    (_('Polls'), 'polls:index'),
    (_('Dokument'), 'archive:documents'),
    (_('Bildarkiv'), 'archive:years'),
)


def get_nav_targets():
    """Return (url, label) suggestions for a navigation URL field."""
    targets = []
    seen = set()

    def add(url, label=''):
        if url and url not in seen:
            seen.add(url)
            targets.append((url, str(label)))

    for title, slug in StaticPage.objects.order_by('title').values_list('title', 'slug'):
        try:
            add(reverse('staticpages:page', args=[slug]), title)
        except NoReverseMatch:
            continue

    for label, url_name in COMMON_NAV_TARGETS:
        try:
            add(reverse(url_name), label)
        except NoReverseMatch:
            continue

    existing_urls = (
        StaticUrl.objects.exclude(url='').order_by('dropdown_element').values_list('url', flat=True).distinct()
    )
    for url in existing_urls:
        add(url)

    return targets


class NavTargetWidget(_TextInputBase):  # type: ignore[misc, valid-type]
    """Free-text URL input with suggestions of the site's own pages.

    The input stays a normal text field: an editor can still type any external
    address or a hand-written path, and the browser narrows the suggestions
    while typing.
    """

    def __init__(self, targets=None, attrs=None):
        self.targets = list(targets or ())
        super().__init__(attrs=attrs)

    def render(self, name, value, attrs=None, renderer=None):
        attrs = dict(attrs or {})
        datalist_id = f"{attrs.get('id') or f'id_{name}'}_suggestions"
        attrs['list'] = datalist_id
        rendered = super().render(name, value, attrs, renderer)
        options = format_html_join(
            '',
            '<option value="{}">{}</option>',
            ((url, label) for url, label in self.targets),
        )
        return format_html('{}<datalist id="{}">{}</datalist>', rendered, datalist_id, options)
