from django.urls import path

from .views import my_projects, project_detail, complete_project, archive_project

app_name = 'projects'

urlpatterns = [
    path('my/', my_projects, name='my_projects'),
    path('<int:pk>/', project_detail, name='project_detail'),
    path('<int:pk>/complete/', complete_project, name='complete_project'),
    path('<int:pk>/archive/', archive_project, name='archive_project'),
]
