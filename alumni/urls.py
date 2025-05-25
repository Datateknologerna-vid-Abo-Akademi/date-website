from django.urls import path

from . import views

app_name = "alumni"

urlpatterns = [
    path('signup/', views.alumni_signup, name='alumni_signup'),
]
