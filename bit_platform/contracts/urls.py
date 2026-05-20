from django.urls import path

from . import views

app_name = 'contracts'

urlpatterns = [
    path('', views.contract_list, name='list'),
    path('create/<int:request_id>/', views.create_contract, name='create'),
    path('<int:pk>/', views.contract_detail, name='detail'),
]
