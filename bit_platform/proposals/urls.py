from django.urls import path

from . import views

app_name = 'proposals'

urlpatterns = [
    path('', views.proposal_list, name='list'),
    path('create/<int:request_id>/', views.create_proposal, name='create'),
    path('<int:pk>/', views.proposal_detail, name='detail'),
]
