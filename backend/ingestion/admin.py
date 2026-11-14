from django.contrib import admin

from .models import IngestionRun


@admin.register(IngestionRun)
class IngestionRunAdmin(admin.ModelAdmin):
    list_display = ["started", "finished", "route", "counts"]
    readonly_fields = ["started", "finished", "route", "source_checksum", "counts", "errors"]
