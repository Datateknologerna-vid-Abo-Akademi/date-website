from .models import StaticPage, StaticPageNav

def get_pages(context):
    pages = StaticPage.objects.all()
    return {'pages': pages}

def get_categories(context):
    categories = StaticPageNav.objects.all()
    return {'categories': categories}