from django.db import models


class IngestionRun(models.Model):
    """Audit log for every pipeline run (section 5.1)."""

    started = models.DateTimeField(auto_now_add=True)
    finished = models.DateTimeField(null=True, blank=True)
    route = models.CharField(max_length=60, help_text="Access route used: api, bucket, browser or owner_export")
    source_checksum = models.CharField(max_length=64, blank=True)
    counts = models.JSONField(default=dict, blank=True)
    errors = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["-started"]

    def __str__(self) -> str:
        return f"{self.route} {self.started:%Y-%m-%d %H:%M}"
