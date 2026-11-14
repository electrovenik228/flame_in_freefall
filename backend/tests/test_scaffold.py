import pytest


@pytest.mark.django_db
def test_stats_and_health(client):
    assert client.get("/api/v1/meta/stats/").status_code == 200
    assert client.get("/api/v1/health/").json()["status"] == "ok"


@pytest.mark.django_db
def test_error_format(client):
    body = client.get("/api/v1/health/", HTTP_ACCEPT="text/csv").json()
    assert set(body["error"]) == {"code", "message", "details"}
