from django.urls import path

from .views import (
    register_view,
    profile_view,
    profile_edit_view,
    dashboard_redirect,
    client_dashboard,
    analyst_dashboard,
    executor_dashboard,
    staff_list,
)

app_name = 'accounts'

urlpatterns = [
    path('register/', register_view, name='register'),
    path('profile/', profile_view, name='profile'),
    path('profile/edit/', profile_edit_view, name='profile_edit'),
    path('dashboard/', dashboard_redirect, name='dashboard'),
    path('dashboard/client/', client_dashboard, name='client_dashboard'),
    path('dashboard/analyst/', analyst_dashboard, name='analyst_dashboard'),
    path('dashboard/executor/', executor_dashboard, name='executor_dashboard'),
    path('staff/', staff_list, name='staff_list'),
]
