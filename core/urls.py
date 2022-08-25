"""date URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
# update

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from date import views as date

app_name = 'core'

urlpatterns = [
    path('', date.index, name='index'),
    path('news/', include('news.urls')),
    path('members/', include('django.contrib.auth.urls')),
    path('members/', include('members.urls')),
    path('archive/', include('archive.urls')),
    path('events/', include('events.urls')),
    path('pages/', include('staticpages.urls')),
    path('ads/',include('ads.urls')),
    path('social/',include('social.urls')),
    path('polls/', include('polls.urls')),
    path('ctf/', include('ctf.urls')),
    path('admin/', admin.site.urls),
]
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
