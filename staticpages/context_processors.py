from .models import StaticPage, StaticPageNav, StaticUrl

def get_pages(context):
    pages = StaticPage.objects.all().order_by('dropdown_element')
    return {'pages': pages}

def get_categories(context):
    categories = StaticPageNav.objects.all()
    return {'categories': categories}

def get_urls(context):
    urls = StaticUrl.objects.all().order_by('dropdown_element')
    return {'urls': urls}