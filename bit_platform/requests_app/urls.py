from django.urls import path

from .views import (
    my_requests,
    create_request,
    request_detail,
    edit_request,
    all_requests,
    new_requests,
    my_analysis,
)

app_name = 'requests_app'

urlpatterns = [
    # Клиентские URLs
    path('my/', my_requests, name='my_requests'),
    path('create/', create_request, name='create_request'),
    path('<int:pk>/', request_detail, name='request_detail'),
    path('<int:pk>/edit/', edit_request, name='edit_request'),
    
    # Аналитик URLs
    path('all/', all_requests, name='all_requests'),
    path('new/', new_requests, name='new_requests'),
    path('analysis/', my_analysis, name='my_analysis'),
]
