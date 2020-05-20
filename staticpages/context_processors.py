from .models import StaticPage, StaticPageNav, StaticUrl

def get_pages(context):
    pages = StaticPage.objects.all()
    return {'pages': pages}

def get_categories(context):
    categories = StaticPageNav.objects.all()
    return {'categories': categories}

def get_urls(context):
    urls = StaticUrl.objects.all()
    return {'urls': urls}