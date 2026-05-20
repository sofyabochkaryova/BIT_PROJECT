from django.urls import path

from .views import my_tasks, task_detail, all_tasks

app_name = 'tasks'

urlpatterns = [
    path('my/', my_tasks, name='my_tasks'),
    path('all/', all_tasks, name='all_tasks'),
    path('<int:pk>/', task_detail, name='task_detail'),
]
