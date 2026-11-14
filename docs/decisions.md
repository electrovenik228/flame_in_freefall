# Decisions log

Choices made where the specification is silent, and results of checks it asks to be logged.

## Step 0. PSI access probe (section 4.6)

Status on 14 November 2026: **not passed**. No seed record has been saved yet.

| Route | Result | Evidence |
| --- | --- | --- |
| 1. Data requests behind the PSI search page | Address found, request not made | The search page is a 954-byte shell that loads `main.5216219a85b99359.js`. That script references `/geode-py/ws/repo/search`, `/geode-py/ws/repo/filter-options`, `/geode-py/ws/studies` and `/files/v2`. The request to `/geode-py/ws/repo/search` was blocked twice by the agent's permission system as unauthorized access, so it is unknown whether the address answers without a login |
| 2. Public AWS bucket `nasa-psi` | No combustion data visible | Anonymous listing of the bucket root returns three prefixes: `DSI/`, `OASIS/`, `pk4/`, plus `index.html`. This matches the registry description quoted in section 4.1 |
| 3. Headless browser | Not tried | It loads the same addresses as route 1, so it waits for the same permission decision |

**Outcome, 14 November 2026: passed through the owner's export.** The project owner supplied `psi-combustion-seed.json`, retrieved from `https://psi.nasa.gov/geode-py/ws/` at 2026-11-14T15:05:22Z. Checked by the agent:

- 25 investigation records with full metadata and a `psi_page` link each; 21 of them carry experiment tables (24 CSV files, stored as text).
- All twelve seed investigations of section 4.6 are present, each with a DOI and an experiment table: PSI-20, 22, 25, 26, 68, 69, 98, 99, 100, 101, 102, 159.
- 23 records are Combustion Science. PSI-108 (Fluid Physics) and PSI-181 (Materials Science) are not and are left out of the catalogue. PSI-23 is listed as missing from the export.
- A second file, `psi-combustion-seed (1).json`, differs only in its `retrieved_at` time (46 seconds later) and is redundant.
- The export has no per-record file inventory, so the SourceFile table can hold only experiment tables and images for now.
- Source quirks kept as they are, not corrected: SAFFIRE-I (PSI-98) carries the same start and end dates as SAME (PSI-102); the three Saffire records share one hypothesis text; six records have no acronym.

Test-run tables chosen for step 3 (they hold per-test oxygen plus pressure or flow): FLEX (PSI-69), ACME CFI-G (PSI-159), BASS-II (PSI-25). The Saffire tables are small per-sample tables and can be added cheaply.

## Environment notes

- `.gitignore` added at the repository root; it excludes `.env`.
- The user account is not in the `docker` group, so `docker compose` cannot reach the Docker service from the agent's shell.

## Step 1. Scaffold

- **Compose files sit at the repository root**, not in `deploy/`, so the commands in section 12 work as written. `deploy/` holds the Nginx config and image.
- **Local site port is 8080** (`HTTP_PORT`), production is 80. The database port is not published; the host already runs PostgreSQL on 5432.
- **Versions.** Django 5.2 (long-term support), Python 3.12, PostgreSQL 17, Node 22 for the build, React 18, Vite 6, Tailwind 3. Exact pins are in `backend/requirements.lock` and `frontend/package-lock.json`.
- **App server.** Gunicorn with the `uvicorn-worker` package; the worker class inside Uvicorn itself is deprecated.
- **Cache.** Database-backed Django cache instead of Redis, because the weekend build has no Redis but throttles and the daily token counter need a shared store.
- **Admin static files.** WhiteNoise serves them from the `web` service, since Nginx does not proxy `/admin/`.
- **Fonts.** Inter and IBM Plex Mono are bundled with the front end, so the browser makes no third-party font request.
- **Raw PSI export stays out of git.** It is 6.9 MB, almost all of it version-diff fields (`added`, `removed`). A slim fixture built from it is committed instead, with the export's checksum.
- **Working branch.** The build is committed on `weekend-build`, not on `main`.

## Step 2. Data model

- **SourceDocument is added** to the entities of section 5.1. It stores the text of each PSI record and experiment table, so evidence quotes and citations can be checked word for word against a stored source.
- **AI-derived columns on Investigation are a projection.** `fuel_state`, `safety_pillars`, text-derived condition ranges and `judgment_scores` are copied from the newest accepted Insight row. The Insight rows themselves are never edited, which keeps the rule of section 5.3.
- **Vocabularies** (fuel, fuel form, diluent, extinction mode) are one lookup table, `VocabularyTerm`, editable in the admin. Test runs store the term text.
- **AICall is added** to log token usage per request. The public daily token limit is computed from it.
- **Environment gains numeric flow bounds** (`flow_cm_s_min`, `flow_cm_s_max`) beside the ventilation notes, because the flow criterion is scored in code.
- **Contacts keep name, affiliation and role only.** E-mail addresses and phone numbers in the PSI record are not stored.

## Step 3. Seed data

- **All 23 Combustion Science records in the export are loaded**, not only the twelve seed records. The twelve carry `is_seed`. Section 2 puts every combustion record in scope and the export made this free.
- **Fixture.** `backend/fixtures/psi_seed.json` is built from the raw export by `manage.py build_psi_fixture`. It drops the version-diff fields and contact details and records the export checksum.
- **Test runs come from seven tables:** FLEX, ACME CFI-G (normal and inverse flames), BASS-II, Saffire-I, -II and -III. Other tables are stored as source documents only.
- **FLEX column names.** The PSI headers read "O", "N", "CO" and "He initial ambient composition; mole fraction". They are read as O2, N2, CO2 and He.
- **CFI-G inverse flames have no `oxygen_pct`.** Their XO2 column is the oxygen fraction of the burner gas, not of an atmosphere. The value is kept in `outcomes`.
- **BASS-II has no flow speed.** The table gives fan and air display settings, not cm/s. They are kept in `outcomes` unconverted.
- **Ranges and approximate cells.** For a cell such as "21.5 - 21.7" or "~ 22.1" the normalized value is the first number; the text as written is kept in `outcomes` and `raw_row`.
- **Validation.** A non-positive pressure, an oxygen value outside 0-100% or a negative flow is left empty and listed in the ingestion run. One case exists: FLEX row 115 gives 0 mmHg.
- **Projects** are assigned by acronym prefix (ACME, FLEX, BASS, SAFFIRE, SAME). **Facilities** are matched on phrases in the PSI hardware text. Records that match nothing have no project or facility.
- **`data_depth`** is set to per-test by code only where test runs were parsed. For other records it is left to the extraction job in step 6.
