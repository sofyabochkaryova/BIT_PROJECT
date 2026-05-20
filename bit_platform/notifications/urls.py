from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('', views.notification_list, name='list'),
    path('<int:pk>/read/', views.mark_as_read, name='mark_read'),
    path('<int:pk>/delete/', views.delete_notification, name='delete'),
    path('mark-all-read/', views.mark_all_read, name='mark_all_read'),
    path('clear-all/', views.clear_all, name='clear_all'),
    path('preferences/', views.notification_preferences, name='preferences'),
    
    # API endpoints
    path('api/unread-count/', views.get_unread_count, name='api_unread_count'),
    path('api/recent/', views.get_recent, name='api_recent'),
]
