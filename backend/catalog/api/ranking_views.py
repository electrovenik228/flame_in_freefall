"""Ranking and coverage endpoints. Both are computed in code from stored data, with no AI call."""

import math
from collections import defaultdict

from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.response import Response

from catalog import models
from catalog.services import ranking

from .serializers import EnvironmentSerializer

DISCLAIMER = (
    "This ranking is a research aid built on an open rubric. It is not a safety rating and does not replace "
    "NASA flammability standards or testing."
)
GRAVITY_NOTE = (
    "PSI holds no partial-gravity data. Rankings for the Moon and Mars differ only through the atmosphere "
    "criterion; microgravity and 1 g results bound the partial-gravity case, they do not answer it."
)
AXIS_UNITS = {"oxygen_pct": "%", "pressure_kpa": "kPa", "flow_speed_cm_s": "cm/s"}
DEFAULT_BINS = {"oxygen_pct": 2.0, "pressure_kpa": 20.0, "flow_speed_cm_s": 5.0}


def ranking_payload(target: ranking.Target, weights: dict | None, environment=None) -> dict:
    merged = {**ranking.DEFAULT_WEIGHTS, **(weights or {})}
    return {
        "environment": EnvironmentSerializer(environment).data if environment else None,
        "target": {
            "name": target.name,
            "oxygen_pct": target.oxygen,
            "pressure_kpa": target.pressure,
            "flow_cm_s": target.flow,
        },
        "weights": merged,
        "criteria": ranking.CRITERIA,
        "disclaimer": DISCLAIMER,
        "gravity_note": GRAVITY_NOTE,
        "results": ranking.rank(target, merged),
    }


@extend_schema(responses=OpenApiTypes.OBJECT)
@api_view(["GET"])
def environment_ranking(request, pk: int):
    """Ranked investigations with sub-scores and rationale for a reference environment."""
    environment = get_object_or_404(models.Environment, pk=pk)
    return Response(ranking_payload(ranking.Target.from_environment(environment), None, environment))


class WeightsSerializer(serializers.Serializer):
    atmosphere = serializers.FloatField(min_value=0, max_value=100, required=False)
    fuel = serializers.FloatField(min_value=0, max_value=100, required=False)
    safety = serializers.FloatField(min_value=0, max_value=100, required=False)
    flow = serializers.FloatField(min_value=0, max_value=100, required=False)
    gravity = serializers.FloatField(min_value=0, max_value=100, required=False)


class CustomRankingSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=80, required=False, default="Custom atmosphere")
    oxygen_pct_min = serializers.FloatField(min_value=0, max_value=100, required=False, allow_null=True)
    oxygen_pct_max = serializers.FloatField(min_value=0, max_value=100, required=False, allow_null=True)
    pressure_kpa_min = serializers.FloatField(min_value=0, max_value=2000, required=False, allow_null=True)
    pressure_kpa_max = serializers.FloatField(min_value=0, max_value=2000, required=False, allow_null=True)
    flow_cm_s_min = serializers.FloatField(min_value=0, max_value=1000, required=False, allow_null=True)
    flow_cm_s_max = serializers.FloatField(min_value=0, max_value=1000, required=False, allow_null=True)
    weights = WeightsSerializer(required=False)

    def validate(self, data):
        for low, high in (
            ("oxygen_pct_min", "oxygen_pct_max"),
            ("pressure_kpa_min", "pressure_kpa_max"),
            ("flow_cm_s_min", "flow_cm_s_max"),
        ):
            if data.get(low) is not None and data.get(high) is not None and data[low] > data[high]:
                raise serializers.ValidationError({low: "The lower bound is above the upper bound."})
        if all(
            data.get(key) is None
            for key in ("oxygen_pct_min", "oxygen_pct_max", "pressure_kpa_min", "pressure_kpa_max")
        ):
            raise serializers.ValidationError("Give at least one oxygen or pressure bound.")
        return data


@extend_schema(request=CustomRankingSerializer, responses=OpenApiTypes.OBJECT)
@api_view(["POST"])
def custom_ranking(request):
    """Ranking for a user-defined atmosphere and weights. Computed in code, with no AI call."""
    serializer = CustomRankingSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    target = ranking.Target(
        data["name"],
        (data.get("oxygen_pct_min"), data.get("oxygen_pct_max")),
        (data.get("pressure_kpa_min"), data.get("pressure_kpa_max")),
        (data.get("flow_cm_s_min"), data.get("flow_cm_s_max")),
    )
    return Response(ranking_payload(target, data.get("weights")))


@extend_schema(
    parameters=[
        OpenApiParameter("x", str, enum=list(AXIS_UNITS), description="Horizontal axis, default oxygen_pct"),
        OpenApiParameter("y", str, enum=list(AXIS_UNITS), description="Vertical axis, default pressure_kpa"),
        OpenApiParameter("x_bin", float, description="Bin width on x"),
        OpenApiParameter("y_bin", float, description="Bin width on y"),
    ],
    responses=OpenApiTypes.OBJECT,
)
@api_view(["GET"])
def coverage(request):
    """Binned counts of test runs on two condition axes, with the reference environments and gaps."""
    x, y = request.GET.get("x", "oxygen_pct"), request.GET.get("y", "pressure_kpa")
    if x not in AXIS_UNITS or y not in AXIS_UNITS or x == y:
        raise serializers.ValidationError({"x": f"Choose two different axes from {', '.join(AXIS_UNITS)}."})
    try:
        x_bin = float(request.GET.get("x_bin", DEFAULT_BINS[x]))
        y_bin = float(request.GET.get("y_bin", DEFAULT_BINS[y]))
    except ValueError as exc:
        raise serializers.ValidationError({"x_bin": "Bin widths must be numbers."}) from exc
    if x_bin <= 0 or y_bin <= 0:
        raise serializers.ValidationError({"x_bin": "Bin widths must be positive."})

    runs = list(models.TestRun.objects.values("investigation__psi_id", "investigation__acronym", x, y))
    cells: dict[tuple[float, float], dict] = defaultdict(lambda: {"count": 0, "investigations": defaultdict(int)})
    plotted = 0
    for run in runs:
        if run[x] is None or run[y] is None:
            continue
        plotted += 1
        key = (math.floor(run[x] / x_bin) * x_bin, math.floor(run[y] / y_bin) * y_bin)
        cells[key]["count"] += 1
        cells[key]["investigations"][run["investigation__psi_id"]] += 1
    names = {
        run["investigation__psi_id"]: run["investigation__acronym"] or run["investigation__psi_id"] for run in runs
    }
    bins = [
        {
            "x0": x0, "x1": x0 + x_bin, "y0": y0, "y1": y0 + y_bin, "count": cell["count"],
            "investigations": [
                {"psi_id": psi_id, "name": names[psi_id], "runs": n}
                for psi_id, n in sorted(cell["investigations"].items(), key=lambda item: -item[1])
            ],
        }
        for (x0, y0), cell in sorted(cells.items())
    ]  # fmt: skip

    environments = []
    bounding: dict[str, dict] = {}
    context = ranking.load_context()
    for environment in models.Environment.objects.all():
        target = ranking.Target.from_environment(environment)
        rows = ranking.rank(target, context=context)
        scored = [row for row in rows if row["sub_scores"]["atmosphere"]["status"] == "scored"]
        scored.sort(key=lambda row: -row["sub_scores"]["atmosphere"]["score"])
        inside = sum(row["sub_scores"]["atmosphere"]["details"].get("runs_inside", 0) for row in scored)
        environments.append(
            {
                **EnvironmentSerializer(environment).data,
                "test_runs_inside": inside,
                "tested": inside > 0,
                "nearest": [
                    {
                        "psi_id": row["psi_id"],
                        "display_name": row["display_name"],
                        "atmosphere_score": row["sub_scores"]["atmosphere"]["score"],
                        "explanation": row["sub_scores"]["atmosphere"]["explanation"],
                        "basis": row["sub_scores"]["atmosphere"]["details"].get("basis"),
                    }
                    for row in scored[:4]
                ],
            }
        )
        for row in rows:
            details = row["sub_scores"]["gravity"]["details"]
            if details["microgravity"] and (details["one_g_reference"] or details["partial_gravity_proxy"]):
                bounding[row["psi_id"]] = {
                    "psi_id": row["psi_id"],
                    "display_name": row["display_name"],
                    "one_g_reference": details["one_g_reference"],
                    "partial_gravity_proxy": details["partial_gravity_proxy"],
                    "quotes": row["sub_scores"]["gravity"]["source"].get("quotes", []),
                }
    return Response(
        {
            "x": {"field": x, "unit": AXIS_UNITS[x], "bin": x_bin},
            "y": {"field": y, "unit": AXIS_UNITS[y], "bin": y_bin},
            "test_runs_total": len(runs),
            "test_runs_plotted": plotted,
            "test_runs_missing_an_axis": len(runs) - plotted,
            "bins": bins,
            "environments": environments,
            "partial_gravity": {
                "statement": "No partial-gravity combustion data exists in PSI. Lunar (1/6 g) and Martian (3/8 g) "
                "behaviour can only be bounded by microgravity and 1 g results.",
                "bounding_records": sorted(bounding.values(), key=lambda item: item["psi_id"]),
            },
        }
    )
