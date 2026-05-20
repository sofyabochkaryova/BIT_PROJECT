from django.urls import path
from . import views

app_name = 'clients'

urlpatterns = [
    path('company/', views.my_company, name='my_company'),
]
