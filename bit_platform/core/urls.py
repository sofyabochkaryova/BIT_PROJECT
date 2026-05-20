from django.urls import path

from .views import dashboard_view, home_view, privacy_view, terms_view

app_name = 'core'

urlpatterns = [
    path('', home_view, name='home'),
    path('dashboard/', dashboard_view, name='dashboard'),
    path('privacy/', privacy_view, name='privacy'),
    path('terms/', terms_view, name='terms'),
]
