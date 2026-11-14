from django.contrib import admin

from . import models


class TestRunInline(admin.TabularInline):
    model = models.TestRun
    extra = 0
    fields = ["test_label", "fuel", "oxygen_pct", "pressure_kpa", "flow_speed_cm_s", "source_row"]
    readonly_fields = fields
    can_delete = False
    max_num = 0
    show_change_link = True


@admin.register(models.Investigation)
class InvestigationAdmin(admin.ModelAdmin):
    list_display = ["psi_id", "acronym", "fuel_state", "data_depth", "conditions_source", "is_seed"]
    list_filter = ["is_seed", "fuel_state", "data_depth", "conditions_source", "project"]
    search_fields = ["psi_id", "acronym", "title"]
    filter_horizontal = ["facilities", "instruments"]


@admin.register(models.TestRun)
class TestRunAdmin(admin.ModelAdmin):
    list_display = ["investigation", "test_label", "fuel", "oxygen_pct", "pressure_kpa", "flow_speed_cm_s"]
    list_filter = ["investigation", "fuel_form", "diluent"]
    search_fields = ["test_label", "fuel"]


@admin.register(models.SourceFile)
class SourceFileAdmin(admin.ModelAdmin):
    list_display = ["name", "investigation", "category", "size", "status"]
    list_filter = ["status", "category"]


@admin.register(models.SourceDocument)
class SourceDocumentAdmin(admin.ModelAdmin):
    list_display = ["title", "investigation", "kind", "retrieved_at"]
    list_filter = ["kind"]


@admin.register(models.Publication)
class PublicationAdmin(admin.ModelAdmin):
    list_display = ["title", "investigation", "year"]
    search_fields = ["title", "authors"]


@admin.register(models.Environment)
class EnvironmentAdmin(admin.ModelAdmin):
    list_display = ["name", "oxygen_pct_min", "oxygen_pct_max", "pressure_kpa_min", "pressure_kpa_max", "gravity"]


@admin.register(models.VocabularyTerm)
class VocabularyTermAdmin(admin.ModelAdmin):
    list_display = ["label", "kind", "code"]
    list_filter = ["kind"]


admin.site.register([models.Project, models.Facility, models.Instrument])
admin.site.site_header = "Flame in Freefall admin"
