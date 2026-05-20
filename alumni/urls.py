from django.urls import path

from . import views

app_name = "alumni"

urlpatterns = [
    path('signup/', views.alumni_signup, name='alumni_signup'),
    path('update/', views.alumni_update_verify, name='alumni_update'),
    path('update/<uuid:token>/', views.alumni_update_form, name='alumni_update_with_token'),
]
