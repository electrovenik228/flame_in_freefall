from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("investigations", views.InvestigationViewSet, basename="investigation")
router.register("test-runs", views.TestRunViewSet, basename="test-run")
router.register("projects", views.ProjectViewSet, basename="project")
router.register("facilities", views.FacilityViewSet, basename="facility")
router.register("instruments", views.InstrumentViewSet, basename="instrument")
router.register("publications", views.PublicationViewSet, basename="publication")
router.register("environments", views.EnvironmentViewSet, basename="environment")

urlpatterns = [
    path("health/", views.health, name="health"),
    path("meta/stats/", views.meta_stats, name="meta-stats"),
    path("search/", views.global_search, name="search"),
    path("test-runs/export/", views.TestRunExportView.as_view(), name="test-run-export"),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
    *router.urls,
]
