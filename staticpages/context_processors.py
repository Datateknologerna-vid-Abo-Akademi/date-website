from .models import StaticPageNav, StaticUrl


def get_categories(context):
    categories = StaticPageNav.objects.all().order_by('nav_element')
    return {'categories': categories}


def get_urls(context):
    urls = StaticUrl.objects.all().order_by('dropdown_element')
    return {'urls': urls}
