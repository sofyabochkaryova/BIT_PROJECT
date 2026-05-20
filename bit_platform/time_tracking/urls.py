from django.urls import path
from . import views

app_name = 'time_tracking'

urlpatterns = [
    path('log/<int:task_id>/', views.log_time, name='log_time'),
    path('timesheet/<int:task_id>/', views.task_timesheet, name='task_timesheet'),
    path('report/create/<int:task_id>/', views.create_work_report, name='create_report'),
    path('report/<int:pk>/', views.report_detail, name='report_detail'),
    path('report/<int:pk>/download/', views.download_report_docx, name='download_report_docx'),
    path('report/<int:pk>/download/', views.download_report_docx, name='download_report'),
    path('reports/', views.my_reports, name='my_reports'),
]
