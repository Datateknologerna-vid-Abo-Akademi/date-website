"""Template helpers for the Albins Angels news category."""

from django import template
from django.urls import reverse

from news.models import Category

register = template.Library()


@register.simple_tag(name='aa_news_url')
def aa_news_url():
    """Return the news listing URL for the Albins Angels category.

    The category slug differs between databases (a fresh database seeds
    ``albins-angels`` while production uses ``aa``), so resolve the category by
    name instead of hardcoding a slug, and fall back to the news index when the
    category does not exist yet.
    """
    from date.views import ALBINS_ANGELS_CATEGORY_NAME

    category = Category.objects.filter(name=ALBINS_ANGELS_CATEGORY_NAME).first()
    if category is None:
        return reverse('news:index')
    return category.get_absolute_url()
