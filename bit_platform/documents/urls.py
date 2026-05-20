from django.urls import path

from . import views

app_name = 'documents'

urlpatterns = [
    path('', views.document_list, name='list'),
    path('company-stamp/', views.company_stamp_settings, name='company_stamp'),
    path('<int:pk>/', views.document_detail, name='detail'),
    path('<int:pk>/download/', views.download_document, name='download'),
    path('<int:pk>/send-for-signing/', views.send_for_signing, name='send_for_signing'),
    path('<int:pk>/sign/', views.sign_document, name='sign'),
    path('sign/<str:token>/', views.sign_by_token, name='sign_by_token'),
    path('bundle/<int:request_id>/', views.generate_bundle, name='generate_bundle'),
]
