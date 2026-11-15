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

## Step 4. Catalogue API

- **Range filters on investigations mean overlap.** `oxygen_pct_min=30` keeps records whose tested range reaches 30% or more. On test runs the same filter is a plain comparison.
- **Export file type** is chosen with `output=csv` or `output=json`, because `format` is reserved by the REST framework.
- **No response cache in the weekend build.** Section 9 caches list and detail responses in Redis; without Redis the queries go straight to PostgreSQL, which is fast at this size.
- **Default order** of investigations is by PSI number.

## Step 5. Catalogue pages

- **Both themes ship.** The tokens of section 10.1 are CSS variables, so the light theme came at no extra cost. Dark is the default when the system has no preference.
- **Safety-function hues:** prevention violet, detection teal, suppression pink, each with its own icon and text label.
- **API types are written by hand** in `frontend/src/lib/api.ts` for the weekend build. Generating the client from the OpenAPI schema is left to the full build.
- **The list loads all records in one request** (page size 200). With 23 records there is no pager.
- **Browser tests run on the developer machine** against the Compose stack: `cd frontend && npm install && npx playwright test`.

## Step 6. AI generation

Status on 15 November 2026: **check passed for the twelve seed records**; 21 of 23 records generated. PSI-39 (CFI) and PSI-47 (DAFT), which are not in the seed set, failed with "credit balance is too low" and are pending. The run made 70 Claude requests, about 4.70 USD at list price.

- **Run it with** `docker compose exec web python manage.py generate_ai`. It prints the step 6 check at the end; `--report` prints the check alone.
- **Extraction returns values as the source writes them**, with the source's unit. Conversion to kPa, percent and cm/s is done in code. Each number must appear in one of its own evidence quotes.
- **Quote check.** A quote must appear word for word in the named source document. Only runs of whitespace are normalized.
- **Number check for prose.** A number in AI text passes when the same number appears in a source document of the cited record. PSI identifiers and digits inside names (C2H4) are not numeric claims. Prompts forbid unit conversion in prose, so no conversion is attempted in the check.
- **Failed checks.** The model gets one more attempt with the list of problems. If the second attempt also fails, the result is rejected: a row marked "not generated" keeps the reasons, and nothing is shown.
- **Refusals** follow section 7.3: marked "not generated", no retry. Server-side refusal fallbacks are not enabled.
- **Test-run statistics are a citable document.** Counts and ranges computed from the database are rendered as text, so a summary can cite "274 test runs" and the number check can verify it.
- **Summaries use two requests per record**, one per reading level, with the documents cached between them.
- **Effort.** Stored jobs run at `high` effort (`CLAUDE_BACKGROUND_EFFORT`), not the Opus 5.5 default of medium.
- **Anthropic SDK 2.8** is installed, which uses API version 2026-10-21.
- **AI output is exported to `backend/fixtures/ai_output.json`** (`manage.py export_ai_output`) and loaded with `manage.py import_ai_output`. A fresh database or the server gets the stored output without new Claude requests.
- **One-sided statements keep their missing bound.** "Up to 20 atm" is stored as a maximum only and shown as "≤".
- **Instruments** come from the extraction, each with an evidence quote. The PSI export has no structured instrument field.

## Step 7. Ranking and coverage

- **Atmosphere match.** A tested condition within tolerance of the environment window scores 1 (oxygen within 1 percentage point, pressure within 5 kPa). Beyond that the score falls in a straight line to 0 at a further 10 points of oxygen or 50 kPa. With test runs, the best single run decides, so oxygen and pressure are matched jointly, and the explanation counts the runs inside the window. Without test runs, the record-level ranges are used.
- **An axis the record does not state** is left out of the atmosphere score and the row is tagged "partial data".
- **Flow match is not scored for the five reference environments.** The brief gives no ventilation speed and no NASA figure could be confirmed, so none was invented. The criterion is scored when a flow window exists: under Custom atmosphere, or after the owner sets `flow_cm_s_min` and `flow_cm_s_max` in the admin. The same tolerance rule applies (2 cm/s, then 20 cm/s).
- **"Not applicable" differs from "not available".** A criterion the environment does not define is rescaled away without a tag. A criterion the record lacks data for is rescaled away with the "partial data" tag.
- **Gravity relevance does not depend on the environment.** 6 points when PSI lists the record as a microgravity investigation, 2 when the record refers to 1 g or ground reference tests (matched on phrases, the matching sentence is shown as evidence), 2 for an electric field. This follows the scoring rule of section 7.4, not the "changes with the environment" column of its table.
- **AI judgment.** Fuel relevance and safety function are scored 0 to 10 by Claude against written anchors, with evidence quotes, once per investigation. The rubric version is part of the input hash, so a rubric change regenerates them.
- **Rankings are computed on request** from stored data (about 0.1 s), and also stored per pair in `RelevanceScore` by `load_seed`, `import_ai_output` and `generate_ai`.
- **Coverage.** Oxygen in 2-point bins against pressure in 20 kPa bins or flow in 5 cm/s bins. An empty cell means no test run. Counts use five ordered steps of one hue. The spacesuit atmosphere is off the chart and reported as a gap card.
- **Chart colours** for the five criteria were checked with a colour-vision validator on both theme surfaces.

## Step 8. Assistant and Overview

Status: built; the live part of the check waits for API credit.

- **Tools return `search_result` blocks** with citations on, so answers cite the tool results directly. Each block's `source` is the PSI link, or a page of the site for the ranking method.
- **Model and settings.** `CLAUDE_MODEL_FAST` (Sonnet 5.5), `thinking: between_tools`, effort low, output capped by `ASSISTANT_MAX_OUTPUT_TOKENS` (2000), at most 6 tool rounds.
- **Text written before a tool call is discarded** from the answer; only the final turn's text is shown and stored.
- **Number check after the stream.** A number passes when it appears in a tool result of that turn or in the visitor's own messages. An answer with no tool call (an off-topic redirect) gets no mark.
- **Limits.** Daily token limit over all public AI calls, a per-session message cap and a per-IP daily cap. The IP cap counts in the cache under a salted hash; no address is stored.
- **CSRF.** The two POST endpoints accept only `application/json`, which a cross-site form cannot send.
- **Endpoints are plain async Django views**, not REST framework views, so the reply can stream.
- **Overview incidents** quote the three NASA pages of section 4.1 word for word, each with its link. The flame hero is a drawn illustration, labelled so, because no licensed NASA image pair was in hand.
- **The video** loads from youtube-nocookie.com only when the visitor presses play.

## Step 9. Deploy

- **`deploy/deploy.sh user@server`** copies the tracked files and `.env` over SSH, builds, starts, loads the seed and the stored AI output, and waits for the health endpoint. It never removes volumes or backups.
- **Data on the server comes from fixtures**, so the server needs no Claude request to show summaries.
- **Backups.** A `backup` service writes one `pg_dump` a day to `./backups` and keeps the newest 14. A dump and restore were not yet tested on the server; the restore command is in `deploy/server-setup.md`.
- **Security headers** are set by Nginx in every location through `deploy/nginx/security-headers.conf`. The API docs page gets a policy that allows Swagger UI from cdn.jsdelivr.net.
- **The health endpoint returns 503** when the database is unreachable, and the `web` container uses it as its health check.
- **The daily token limit** is `AI_DAILY_TOKEN_LIMIT` in `.env` (5,000,000).
- **Shared server.** The server also runs other projects, and port 80 belongs to one of them, so the site is published on port 2026 (`HTTP_PORT=2026 deploy/deploy.sh root@147.45.185.185`). The firewall was left as found (inactive): enabling the rule of section 12 (ports 22 and 80 only) would cut off the other projects. The admin port 8001 is bound to 127.0.0.1 and is closed from outside.
- **Moved to a second server, 186.246.113.49 (Netherlands), on port 80.** The Claude API answers requests from the first server (147.45.185.185, Russia) with 403 "Request not allowed", so the assistant could not work there. The new server has 1 CPU and 1.9 GB of memory, so a 2 GB swap file was added for the image build. It runs only this project. The first server still runs the site on port 2026 and can be stopped with `docker compose -f docker-compose.prod.yml down` in `~/flame_in_freefall` (the database volume stays).
