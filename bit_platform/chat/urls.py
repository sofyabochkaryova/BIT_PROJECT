from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    path('', views.conversation_list, name='list'),
    path('widget-data/', views.widget_data, name='widget_data'),
    path('widget-messages/<int:pk>/', views.widget_messages, name='widget_messages'),
    path('<int:pk>/', views.conversation_detail, name='conversation'),
    path('<int:pk>/send/', views.send_message, name='send_message'),
    path('<int:pk>/messages/', views.get_new_messages, name='get_messages'),
    path('start/<int:user_id>/', views.start_conversation, name='start'),
    path('start/', views.start_conversation_post, name='start_post'),
    path('request/<int:request_id>/', views.start_request_chat, name='start_request'),
    path('create-group/', views.create_group_chat, name='create_group'),
    path('<int:pk>/delete/', views.delete_conversation, name='delete_conversation'),
    path('message/<int:message_id>/react/', views.add_reaction, name='add_reaction'),
    path('message/<int:message_id>/delete/', views.delete_message, name='delete_message'),
    path('search-users/', views.search_users, name='search_users'),
]
