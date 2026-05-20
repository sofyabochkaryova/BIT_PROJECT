from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('', views.analytics_dashboard, name='dashboard'),
    path('list/', views.reports_list, name='list'),
    path('create/', views.create_report, name='create'),
    path('<int:pk>/', views.report_detail, name='detail'),
    path('<int:pk>/delete/', views.delete_report, name='delete'),
    
    # API endpoints
    path('api/requests/', views.api_requests_stats, name='api_requests'),
    path('api/tasks/', views.api_tasks_stats, name='api_tasks'),
    path('api/projects/', views.api_projects_stats, name='api_projects'),
    path('api/employees/', views.api_employees_stats, name='api_employees'),
    path('api/clients/', views.api_clients_stats, name='api_clients'),
]
