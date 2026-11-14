from django.db import connection
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.response import Response


@extend_schema(
    responses=inline_serializer("Health", {"status": serializers.CharField(), "database": serializers.CharField()})
)
@api_view(["GET"])
def health(request):
    """Health endpoint for the API and its database."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return Response({"status": "ok", "database": "ok"})


@extend_schema(
    responses=inline_serializer(
        "Stats",
        {"investigations": serializers.IntegerField(), "last_refresh": serializers.DateTimeField(allow_null=True)},
    )
)
@api_view(["GET"])
def meta_stats(request):
    """Counts and last refresh date for the Overview page."""
    return Response({"investigations": 0, "last_refresh": None})
