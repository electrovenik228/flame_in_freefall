import json

import pytest
from django.conf import settings

FIXTURE = settings.BASE_DIR / "fixtures" / "psi_seed.json"


@pytest.fixture(scope="session")
def psi_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture
def seeded(db):
    """Database loaded with the PSI seed fixture."""
    from ingestion.loader import load_fixture

    return load_fixture(FIXTURE)
