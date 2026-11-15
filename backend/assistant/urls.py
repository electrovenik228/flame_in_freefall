from django.urls import path

from . import views

urlpatterns = [
    path("conversations/", views.conversations, name="assistant-conversations"),
    path("conversations/<uuid:conversation_id>/", views.conversation_detail, name="assistant-conversation"),
    path("conversations/<uuid:conversation_id>/messages/", views.messages, name="assistant-messages"),
]
