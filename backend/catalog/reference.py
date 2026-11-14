"""Reference crew environments (section 5.2). Values come from the challenge brief and NASA's
standard atmospheres. Open-ended bounds are None."""

from catalog.models import Environment

NO_FLOW_NOTE = (
    "The challenge brief gives no ventilation speed for this environment, so the flow criterion is "
    "not scored. A flow window can be set in the admin, or under Custom on the ranking page."
)

ENVIRONMENTS = [
    {
        "slug": "earth-sea-level", "name": "Earth, sea level (baseline)", "order": 1,
        "oxygen_pct_min": 21.0, "oxygen_pct_max": 21.0, "pressure_kpa_min": 101.3, "pressure_kpa_max": 101.3,
        "gravity": "1 g", "gravity_g": 1.0, "source": "Challenge brief",
    },
    {
        "slug": "space-station", "name": "Space station", "order": 2,
        "oxygen_pct_min": 21.0, "oxygen_pct_max": 21.0, "pressure_kpa_min": 101.3, "pressure_kpa_max": 101.3,
        "gravity": "Microgravity", "gravity_g": 0.0, "source": "NASA, sea-level air",
    },
    {
        "slug": "spacesuit", "name": "Spacesuit", "order": 3,
        "oxygen_pct_min": 100.0, "oxygen_pct_max": 100.0, "pressure_kpa_min": 29.6, "pressure_kpa_max": 29.6,
        "gravity": "Varies", "gravity_g": None, "source": "Challenge brief",
    },
    {
        "slug": "lunar-habitat", "name": "Lunar surface habitat and pressurized rover", "order": 4,
        "oxygen_pct_min": 30.0, "oxygen_pct_max": None, "pressure_kpa_min": None, "pressure_kpa_max": 70.3,
        "gravity": "1/6 g", "gravity_g": round(1 / 6, 4), "source": "Challenge brief",
    },
    {
        "slug": "mars-habitat", "name": "Mars surface habitat", "order": 5,
        "oxygen_pct_min": 34.0, "oxygen_pct_max": 34.0, "pressure_kpa_min": 56.5, "pressure_kpa_max": 56.5,
        "gravity": "3/8 g", "gravity_g": 0.375, "source": "NASA exploration atmosphere (8.2 psia, 34% oxygen)",
        "source_url": "https://ntrs.nasa.gov/citations/20150021491",
    },
]  # fmt: skip


def load_environments() -> int:
    """Create or update the reference environments. Flow bounds set in the admin are kept."""
    for row in ENVIRONMENTS:
        Environment.objects.update_or_create(
            slug=row["slug"],
            defaults={**{k: v for k, v in row.items() if k != "slug"}, "ventilation_notes": NO_FLOW_NOTE},
        )
    return len(ENVIRONMENTS)
