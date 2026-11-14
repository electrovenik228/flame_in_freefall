import csv
import io

import pytest
from django.core.management import call_command

pytestmark = pytest.mark.django_db
BASE = "/api/v1"


def ids(response) -> list[str]:
    return [item["psi_id"] for item in response.json()["results"]]


def test_list_is_paginated_and_ordered(client, seeded):
    body = client.get(f"{BASE}/investigations/").json()
    assert set(body) == {"count", "next", "previous", "results"}
    assert body["count"] == 23 and len(body["results"]) == 23
    assert [item["psi_id"] for item in body["results"]][:3] == ["PSI-10", "PSI-20", "PSI-21"]
    assert client.get(f"{BASE}/investigations/?page_size=5").json()["next"] is not None
    assert len(client.get(f"{BASE}/investigations/?page_size=500").json()["results"]) == 23  # capped at 200


def test_filters(client, seeded):
    assert set(ids(client.get(f"{BASE}/investigations/?data_depth=per_test"))) == {
        "PSI-25", "PSI-69", "PSI-98", "PSI-99", "PSI-100", "PSI-159",
    }  # fmt: skip
    assert set(ids(client.get(f"{BASE}/investigations/?oxygen_pct_min=30"))) == {"PSI-69", "PSI-159"}
    assert set(ids(client.get(f"{BASE}/investigations/?has_flow=true"))) == {"PSI-98", "PSI-99", "PSI-100"}
    assert ids(client.get(f"{BASE}/investigations/?fuel=heptane")) == ["PSI-69"]
    assert set(ids(client.get(f"{BASE}/investigations/?project=saffire"))) == {"PSI-98", "PSI-99", "PSI-100"}
    assert "PSI-25" in ids(client.get(f"{BASE}/investigations/?facility=glovebox"))
    assert client.get(f"{BASE}/investigations/?is_seed=true").json()["count"] == 12
    assert "PSI-26" not in ids(client.get(f"{BASE}/investigations/?year_min=2015"))
    assert client.get(f"{BASE}/investigations/?ordering=-test_run_count").json()["results"][0]["psi_id"] == "PSI-159"


def test_search(client, seeded):
    assert ids(client.get(f"{BASE}/investigations/?q=FLEX"))[0] in {"PSI-68", "PSI-69"}
    assert "PSI-102" in ids(client.get(f"{BASE}/investigations/?q=smoke aerosol"))
    assert ids(client.get(f"{BASE}/investigations/?q=PSI-22")) == ["PSI-22"]
    body = client.get(f"{BASE}/search/?q=heptane").json()
    assert body["fuels"][0]["fuel"] == "Heptane" and body["fuels"][0]["test_runs"] > 50
    assert any(item["psi_id"] == "PSI-69" for item in body["investigations"])
    assert client.get(f"{BASE}/search/?q=").json()["investigations"] == []


def test_detail(client, seeded):
    body = client.get(f"{BASE}/investigations/PSI-69/").json()
    assert body["acronym"] == "FLEX" and body["doi"] and body["psi_url"].endswith("/PSI-69")
    assert body["test_run_count"] == 274 and body["conditions_source"] == "test_runs"
    varied = {item["field"] for item in body["variables"]["varied"]}
    assert {"fuel", "oxygen_pct", "pressure_kpa"} <= varied
    assert {"field": "flow_speed_cm_s", "label": "Flow speed"} in body["variables"]["not_recorded"]
    fuel = next(item for item in body["variables"]["varied"] if item["field"] == "fuel")
    assert fuel["values"] == ["Heptane", "Methanol"] and fuel["distinct_values"] == 2
    constant = {item["field"]: item["values"] for item in body["variables"]["constant"]}
    assert constant["fuel_form"] == ["droplet"] and constant["gravity_level"] == ["microgravity"]
    assert body["summary"] is None  # nothing generated yet, and nothing invented
    assert {item["psi_id"] for item in body["related"]} == {"PSI-68"}
    assert len(body["publications"]) == 51 and body["facilities"]
    empty = client.get(f"{BASE}/investigations/PSI-26/").json()
    assert empty["variables"]["test_run_count"] == 0 and empty["oxygen_pct_min"] is None


def test_not_found_uses_the_error_format(client, seeded):
    response = client.get(f"{BASE}/investigations/PSI-9999/")
    assert response.status_code == 404
    assert set(response.json()["error"]) == {"code", "message", "details"}


def test_nested_lists(client, seeded):
    runs = client.get(f"{BASE}/investigations/PSI-98/test-runs/").json()
    assert runs["count"] == 2 and runs["results"][0]["source_row"] == 2 and runs["results"][0]["raw_row"]
    files = client.get(f"{BASE}/investigations/PSI-98/files/").json()
    assert files["results"][0]["category"] == "Experimental table"


def test_test_runs_and_export(client, seeded):
    body = client.get(f"{BASE}/test-runs/?fuel_form=solid&oxygen_pct_min=21.6&has_flow=true").json()
    assert body["count"] == 8 and {run["psi_id"] for run in body["results"]} == {"PSI-99"}
    response = client.get(f"{BASE}/test-runs/export/?investigation=PSI-98,PSI-100")
    assert response["Content-Type"].startswith("text/csv")
    rows = list(csv.DictReader(io.StringIO(response.content.decode())))
    assert len(rows) == 4
    assert {"psi_id", "source_file", "source_row", "retrieved_at", "missing_fields"} <= set(rows[0])
    saffire3 = [row for row in rows if row["psi_id"] == "PSI-100"][0]
    assert saffire3["oxygen_pct"] == "" and "oxygen_pct" in saffire3["missing_fields"].split(";")
    as_json = client.get(f"{BASE}/test-runs/export/?investigation=PSI-98&output=json").json()
    assert as_json["count"] == 2


def test_stats_and_reference_lists(client, seeded):
    stats = client.get(f"{BASE}/meta/stats/").json()
    assert stats["investigations"] == 23 and stats["test_runs"] == 749 and stats["last_refresh"]
    assert client.get(f"{BASE}/facilities/").json()["count"] == 6
    assert client.get(f"{BASE}/projects/").json()["count"] == 5
    assert client.get(f"{BASE}/publications/?investigation__psi_id=PSI-98").json()["count"] == 6


def test_openapi_schema_builds_without_warnings(tmp_path):
    """Second half of the step 4 check."""
    call_command("spectacular", "--validate", "--fail-on-warn", "--file", str(tmp_path / "schema.yml"))
    assert (tmp_path / "schema.yml").stat().st_size > 5000
