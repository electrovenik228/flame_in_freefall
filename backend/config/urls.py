from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/assistant/", include("assistant.urls")),
    path("api/v1/", include("catalog.api.urls")),
]
