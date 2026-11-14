# Flame in Freefall — Technical Specification

Nov 14, 2026 · @Бакдөөлөт

## 1. Summary

Flame in Freefall is a web dashboard that turns NASA's microgravity combustion records into ranked, comparable and cited fire-safety insights. Data comes from NASA's Physical Sciences Informatics (PSI) repository. The Claude API reads, structures and interprets it.

The product answers three questions for researchers and engineers:

1. Which investigations matter most for a given crewed environment: spacecraft, station, lunar or Martian base, pressurized rover?
2. What test data exists to feed flammability and fire-scenario models (fuel, oxygen, pressure, flow, gravity)?
3. What does the research imply for prevention, detection and suppression equipment, in space and on Earth?

| Area | Decision |
| --- | --- |
| Back end | Python, Django, Django REST Framework (DRF) |
| Database | PostgreSQL, with full-text search |
| Front end | React + TypeScript single-page app built with Vite |
| AI | Claude API (Anthropic), called only from the back end |
| Background jobs | Celery workers with Redis as broker and cache |
| Delivery | Docker Compose on one server, deployed over SSH and reached by IP address; Nginx as reverse proxy and static host |

One rule shapes the whole design: **structured first, AI second**. Every number on a chart comes from the database. Every AI statement links to the PSI record it is based on.

This specification is written to be executed by an AI coding agent. Section 13 gives the agent its working rules, the build order and the check that closes each step.

## 2. Goals, scope and success criteria

The goal is the challenge brief itself: summarize, rank and interpret combustion investigations so they deliver fire-safety insight for human space exploration.

**In scope for version 1**

- A catalogue of every Combustion Science investigation in PSI, with normalized attributes and links back to the source record.
- Test-level data taken from the PSI experiment tables: fuel, sample or burner geometry, oxygen, pressure, flow, outcome.
- AI summaries, relevance ranking per crew environment, side-by-side comparison and a cited question-and-answer assistant.
- A data explorer with CSV and JSON export for predictive modeling.
- A coverage map showing which atmospheres have been tested and which have not.
- A section on applications to fire safety on Earth.
- Light and dark themes, English interface.

**Out of scope for version 1**

- Mirroring PSI raw files, images and video. The site links to them instead.
- Computer-vision analysis of flame video.
- Running combustion simulations. The site supplies inputs for models, it does not run them.
- Partial-gravity results. PSI has none yet; the data model reserves a gravity field for them.
- User-submitted data and native mobile apps.

**Success criteria**

| Criterion | Target |
| --- | --- |
| PSI combustion investigations ingested with a working source link | 100% |
| AI statements that carry at least one citation | 100% |
| Numeric claims in AI text that match the cited record, on the evaluation set | 100% |
| Evaluation questions passed by the automated grader | 90% or more of 30 |
| Time for a new user to find the top investigations for a 30% oxygen lunar habitat | under 1 minute |
| Catalogue and chart pages, largest contentful paint | under 2.5 s |
| Assistant, time to status line and to first answer word | under 1 s and under 8 s |

## 3. Users and key scenarios

The site serves five kinds of reader, from engineers who need a ranked answer to students who need the basics explained.

| User | What they come for | Main screens |
| --- | --- | --- |
| Aerospace engineer (fire safety, life support) | Which results apply to my cabin atmosphere and materials | Environment ranking, Coverage map |
| Aerospace researcher, professor | Compare investigations, see what is untested | Compare, Coverage map, Assistant |
| Graduate student, modeler | Test conditions and outcomes to validate a flammability model | Data explorer, Export |
| Undergraduate student | Why flames behave differently in microgravity | Overview, Learn, Assistant |
| Fire-safety specialist on Earth | Space research that transfers to terrestrial equipment | Earth applications |

Three scenarios drive acceptance testing:

1. **Lunar habitat check.** An engineer selects "Lunar surface habitat", sees investigations ranked by relevance with a score breakdown, and opens the top one to read its cited summary.
2. **Model inputs.** A graduate student filters test runs to solid fuels above 21% oxygen with forced flow, checks the coverage chart and exports the rows with provenance columns.
3. **Cross-study question.** A researcher asks the assistant how BASS-II and Saffire differ in sample size and flow, and gets a comparison with links to both PSI records.

## 4. Data sources and ingestion

PSI is the single source of experimental facts; the other NASA pages supply context. The site ingests metadata and summary tables, not the raw archive.

### 4.1 Sources

| Source | What we take | Used for |
| --- | --- | --- |
| [PSI data repository, Combustion Science](https://psi.nasa.gov/physci/repo/search?q=combustion&data_source=psi&data_type=investigation) | Investigation records, experiment tables, file lists, publications | All catalogue, test and ranking data |
| [PSI on the AWS Registry of Open Data](https://registry.opendata.aws/nasa-psi/) | Public bucket `nasa-psi` in region us-west-2, readable without an AWS account | Possible fallback route for files. The registry describes the bucket as DSI and OASIS data, so combustion coverage must be checked |
| [NASA Glenn Combustion Science](https://www.nasa.gov/glenn/glenn-expertise-space-exploration/physical-sciences-program/combustion-science/) | Descriptions and fact sheets for ACME, BASS, DAFT, FLEX, Saffire, SAME, SLICE, SPICE; facilities CIR and MDCA | Investigation context, hardware pages |
| [A Researcher's Guide to Combustion Science](https://www.nasa.gov/missions/station/a-researchers-guide-to-combustion-science/) (2015, PDF) | Review text | Background for summaries and the Learn page |
| [Apollo 1](https://sma.nasa.gov/sma-disciplines/accllp/apollo-1), [Apollo 13](https://sma.nasa.gov/sma-disciplines/accllp/apollo-13), [Mir fire](https://www.nasa.gov/history/25-years-ago-fire-aboard-space-station-mir/) | Incident facts and lessons learned | "Why it matters" timeline |
| NASA Spinoff: [air tanks](https://spinoff.nasa.gov/node/9582), [fire detector](https://spinoff.nasa.gov/node/9407), [fire attire](https://spinoff.nasa.gov/node/9918) | Technology transfer stories | Earth applications |
| [NASA ScienceCast video](https://www.youtube.com/watch?v=W1oXykoz9zg) | Embedded video | Overview page |

### 4.2 What a PSI record contains

Per the [PSI database guide](https://science.nasa.gov/wp-content/uploads/2024/11/psi-database-guide.pdf), each investigation page has:

- An identifier such as PSI-8, title, acronym, DOI and research area.
- A description: project type, start and end dates, objectives, approach, hypothesis, benefits, contacts.
- An experiment table with details of samples and runs, also downloadable as a file.
- Hardware and facility links, representative images, publications and version history.
- Data files in folders by type. Raw and analyzed data are split into reduced gravity and Earth gravity.

### 4.3 Known constraints

- **No documented public API.** The PSI search page is a JavaScript application; a plain page fetch returns no content. The first project task is to confirm a stable access route.
- **The archive is very large.** A [public audit by another Space Apps team](https://github.com/YoussefHegazy74/flame-in-freefall), dated 8 November 2026, reports 24 Combustion Science records out of 133, about 16,400 files and roughly 13.5 TB. It also reports that some listed files return "not found". These figures are unverified; we repeat the count in discovery.
- **Depth varies by investigation.** The same audit reports that some records hold per-test tables, some hold 1 Hz telemetry, and some (BASS, BASS-II) hold test matrices and video only.
- **No partial-gravity data** exists in PSI yet, per the challenge brief.
- **Licence.** The AWS registry entry states there are no restrictions on use of the data. Each record's DOI is cited on the site.

### 4.4 Ingestion tiers

| Tier | Content | Volume | Stored where |
| --- | --- | --- | --- |
| 1 | Investigation metadata, file lists, publications | All combustion records | PostgreSQL |
| 2 | Experiment tables (CSV, XLSX) parsed into test runs | Every record that has one | PostgreSQL, raw copy on disk |
| 3 | Selected documents: science requirements, fact sheets, guide chapters | A few per record | Text in PostgreSQL |
| 4 | Raw data, telemetry, images, video | Not downloaded | Link to PSI only |

### 4.5 Pipeline

1. **Fetch.** A Celery task pulls records through the confirmed route, at a polite request rate.
2. **Snapshot.** The raw response or file is saved with its checksum and retrieval time.
3. **Parse.** One parser per table layout turns rows into test runs. Original values and units are kept beside normalized ones.
4. **Normalize.** Claude maps free text to controlled fields (section 7). Each mapped value keeps the source quote.
5. **Validate.** Schema checks run. Failures and low-confidence values go to a review queue in the admin.
6. **Publish.** Records that pass validation become visible. AI summaries and scores are regenerated only for records that changed.

Rules for the pipeline:

- A missing value stays missing. It is never replaced with zero or a guess.
- Every stored value can be traced to a PSI record, file and row.
- Runs are repeatable and safe to restart. A scheduled refresh runs weekly and compares PSI version history.
- If the live route fails, the site keeps serving the last good snapshot and shows its date.

### 4.6 Access probe and seed set

Before any data is loaded, the agent runs an access probe and logs the result in `docs/decisions.md`. It tries three routes in order and uses the first that returns investigation records:

1. The data requests that the PSI web application makes behind its search page.
2. The public AWS bucket `nasa-psi`.
3. A headless browser that renders the PSI pages and saves their content.

If all three fail, the agent stops. The project owner then exports each seed record by hand: the investigation page saved as a file, plus its experiment table.

The hackathon build seeds these twelve investigations, all named in the challenge brief. If one is not found in PSI, the agent logs it and continues; ten is the minimum.

| Role in the demo | Investigations |
| --- | --- |
| Material flammability, prevention | BASS, BASS-II, Saffire-I, Saffire-II, Saffire-III, ACME BRE |
| Smoke detection | SAME, SAME-R |
| Suppression | FLEX, FLEX-2 |
| Highest oxygen levels | ACME CFI-G |
| Partial-gravity proxy | ACME E-FIELD Flames |

## 5. Data model

The database keeps three layers apart: source facts from PSI, reference scenarios we define, and AI output that can be regenerated at any time.

### 5.1 Entities

| Entity | Key fields | Notes |
| --- | --- | --- |
| Project | name, description | Groups related records: ACME, FLEX family, BASS family, Saffire, SAME |
| Investigation | psi\_id, acronym, title, doi, project, dates, objectives, approach, hypothesis, benefits, fuel\_state, safety\_pillars, data\_depth, oxygen, pressure and flow ranges (each min and max), conditions\_source, judgment\_scores, search\_text, psi\_url, psi\_version | One per PSI record. `fuel_state` is gas, liquid or solid. `data_depth` is per-test, telemetry, summary or qualitative. Condition ranges come from test runs when they exist, otherwise from the record text; conditions\_source says which |
| Facility | name, type, description, url | CIR, MSG, MDCA, ACME insert, SPICE flow duct, Saffire vehicle. Many-to-many with Investigation |
| TestRun | investigation, test\_label, date, fuel, fuel\_form, geometry, oxygen\_pct, diluent, pressure\_kpa, flow\_speed\_cm\_s, flow\_direction, gravity\_level, ignited, extinction\_mode, outcomes (JSONB), raw\_row (JSONB), source\_file, source\_row | One row of an experiment table. Normalized columns sit beside the untouched original row |
| Instrument | name, measurement\_type | Cameras, radiometers, thermocouples, smoke detectors, aerosol counters. Many-to-many with Investigation |
| SourceFile | investigation, path, category, gravity\_class, size, checksum, retrieved\_at, status | Inventory of PSI files. `status` records files that are listed but missing |
| Publication | investigation, title, authors, year, url | From the PSI publications list |
| Environment | name, oxygen\_pct range, pressure range, gravity, ventilation notes, source | Reference crew environments used for ranking |
| RelevanceScore | investigation, environment, total, sub\_scores (JSONB), rationale, citations | One per investigation and environment pair |
| Insight | type, target, content (JSONB), citations, model, prompt\_version, input\_hash, review\_status | Summaries, comparisons, gaps, Earth applications |
| Conversation, Message | session, role, content, citations, tool\_calls, token\_usage | Assistant history |
| IngestionRun | started, finished, route, counts, errors | Audit log for every pipeline run |

### 5.2 Reference environments

Values come from the challenge brief and from NASA's standard atmospheres. The space station uses sea-level air. No habitat-specific standard exists for Mars, so that row uses NASA's recommended exploration atmosphere of 8.2 psia and 34% oxygen, described in a [NASA evidence report](https://ntrs.nasa.gov/citations/20150021491) and a [2024 NASA overview](https://ntrs.nasa.gov/citations/20240003211). That atmosphere also sits inside the lunar range given in the brief.

| Environment | Oxygen | Pressure | Gravity | Source |
| --- | --- | --- | --- | --- |
| Earth, sea level (baseline) | 21% | 101.3 kPa (14.7 psi) | 1 g | Challenge brief |
| Space station | 21% | 101.3 kPa (14.7 psi) | Microgravity | NASA, sea-level air |
| Spacesuit | 100% | 29.6 kPa (4.3 psi) | Varies | Challenge brief |
| Lunar surface habitat and pressurized rover | 30% or more | 70.3 kPa (10.2 psi) or less | 1/6 g | Challenge brief |
| Mars surface habitat | 34% | 56.5 kPa (8.2 psi) | 3/8 g | NASA exploration atmosphere |
| Custom | User-defined | User-defined | User-defined | User |

### 5.3 Rules

- Each quantity has one fixed unit, named in the field: pressure in kPa, oxygen in percent by volume, flow speed in cm/s. The interface shows psi beside kPa. The original value and unit stay in `raw_row`.
- Controlled vocabularies (fuel, fuel form, diluent, extinction mode) live in lookup tables, editable in the admin.
- AI rows are never edited in place. A new prompt version writes a new row; the old one is kept for comparison.
- Full-text search uses a PostgreSQL `tsvector` column on investigations, publications and insights. The investigation column also holds its fuel, facility and instrument names, so global search finds them. No vector database is needed at this corpus size.

## 6. System architecture and technology stack

The system is a static React app and a Django API behind one Nginx entry point, with slow work (ingestion, AI generation) moved to background workers.

&#91;embedded content: system architecture · what calls what\]

Arrows show who calls whom. The same connections in words, for exports that drop the picture:

- The browser talks only to Nginx, over HTTP.
- Nginx serves the static React build and proxies `/api/` to the Django API.
- The Django API reads and writes PostgreSQL, uses Redis as cache and job queue, and calls the Claude API for live answers.
- Celery workers take jobs from Redis, fetch records from NASA PSI, call the Claude API for background generation, and write to PostgreSQL.
- The Claude API and NASA PSI are the only external services.

### 6.1 Stack

| Layer | Technology | Why |
| --- | --- | --- |
| Front end | React, TypeScript, Vite | Interactive, filter-heavy dashboard. Builds to static files that Nginx serves, so production needs no Node process |
| UI kit | Tailwind CSS, shadcn/ui (Radix primitives) | Accessible components, full control of theming, light and dark from one token set |
| Data and state | TanStack Query, TanStack Table, React Router | Server-state caching, large sortable tables, filters stored in the URL |
| Charts | Apache ECharts | Scatter, heatmap and parallel-coordinate charts with good performance on thousands of points |
| API | Django, Django REST Framework, django-filter, drf-spectacular | Recommended stack. Admin panel for free, OpenAPI schema generated from code |
| App server | Gunicorn with Uvicorn workers (ASGI) | Needed for streaming assistant replies over server-sent events |
| Background jobs | Celery, Celery Beat, Redis | Ingestion, batch AI jobs, weekly refresh. Redis is also the API cache |
| Database | PostgreSQL | Relational core, JSONB for raw rows and AI payloads, built-in full-text search |
| AI | Claude API through the official Anthropic Python SDK | Extraction, summaries, ranking rationale, comparison, assistant |
| Delivery | Docker, Docker Compose, Nginx | Same containers locally and in production |
| Quality | pytest, Vitest, Playwright, Ruff, ESLint, GitHub Actions | Tests and linting on every push |
| Monitoring | Sentry, structured JSON logs | Errors, slow requests, token usage |

Versions are pinned at project start to the current stable or long-term-support release of each tool.

### 6.2 Front-end choice

A Vite single-page app is chosen over Next.js because the product is an application, not a content site. It needs no server rendering, and a static build keeps the deployment to Nginx plus one Python service. If public sharing and search-engine visibility become a goal, Next.js is the alternative; the API contract stays the same.

### 6.3 Request paths

- **Read paths** (catalogue, charts, rankings) hit DRF, which reads PostgreSQL and caches in Redis. No AI call happens during a page load.
- **Generated content** (summaries, scores, insights) is produced by workers ahead of time and stored. Pages read the stored result.
- **Interactive AI** (assistant, ad-hoc comparison) calls Claude from the API server and streams the reply to the browser.
- **The browser never talks to Claude or NASA directly.** The API key exists only in server environment variables.

## 7. AI layer on the Claude API

Claude does six jobs. Four run in the background and are stored; two run live. In every job Claude works only from records in our database and must cite them.

### 7.1 Jobs

| Job | Runs | Input | Output | Output mode | Model tier |
| --- | --- | --- | --- | --- | --- |
| Attribute extraction | At ingestion | Record text, table headers, documents | Fields of the data model, including condition ranges | JSON schema with evidence quotes | Deep |
| Investigation summary | At ingestion | Record, test-run statistics, documents | Two reading levels: plain and expert | Prose with citations | Deep |
| Relevance judgment | At ingestion and when the rubric changes | Record, rubric | Fuel relevance and safety function scores, each with a short rationale | JSON schema with evidence quotes | Frontier |
| Insights and gaps | After each refresh | Coverage statistics, all summaries | Insight cards: finding, evidence, implication | JSON schema with evidence quotes | Frontier |
| Comparison | On demand, then stored | Two to four records and their test runs | Similarities, differences, what varied, what stayed fixed | Prose with citations, streamed | Deep |
| Research assistant | Live | User question, tool results | Answer, optional chart or filter link | Prose with citations, streamed | Fast |

### 7.2 Models

Model names are configuration, not code. Starting assignment, from the [Claude models overview](https://platform.claude.com/docs/en/models/overview) as of 14 November 2026:

| Tier | Variable | Default model | API ID | Why this tier | List price per million tokens, input / output |
| --- | --- | --- | --- | --- | --- |
| Fast | `CLAUDE_MODEL_FAST` | Claude Sonnet 5.5 | `claude-sonnet-5-5` | Quick first word in live chat | $2 / $10 |
| Deep | `CLAUDE_MODEL_DEEP` | Claude Opus 5.5 | `claude-opus-5-5` | Accurate reading of records and tables | $4 / $20 |
| Frontier | `CLAUDE_MODEL_FRONTIER` | Claude Opus 5.5 | `claude-opus-5-5` | Reasoning across the whole corpus. Can be switched to Fable 5.2 | $4 / $20 |

The build budget is not capped, so background jobs use strong models; the assistant stays on Sonnet for response speed. The Frontier tier may be switched to Claude Fable 5.2 (`claude-fable-5-2`, $8 / $40) only after the project owner confirms that the API organization has 30-day data retention enabled, because the API rejects Fable requests without it. Fable requests can run for minutes, so they use streaming and a 10-minute timeout. Batch requests are listed at 50% off and are optional.

### 7.3 Claude API features used

- **Structured outputs** for the JSON jobs in 7.1. Each schema requires an `evidence` list of source ID and exact quote. Code confirms that every quote appears word for word in the stored source and rejects the result if one does not.
- **Citations** for the prose jobs, with records passed as document blocks. Citations and structured outputs are never sent in the same request, because the API rejects that combination.
- **Tool use** for the assistant. Tools are read-only and take typed parameters; there is no free-form SQL.
- **Prompt caching** for the shared system prompt and corpus context, to cut cost and latency on repeated calls.
- **Streaming** for the assistant, for comparison and for any long background request.
- **Thinking and effort.** The assistant runs with up-front thinking turned off, using the `between_tools` thinking setting because Sonnet 5.5 does not accept thinking fully disabled, and with low effort. Background jobs keep the defaults.
- **Refusals.** A response that stops with reason `refusal` is never stored or shown. In live chat the visitor sees a neutral message. In a background job the item is marked "not generated", logged, and the job moves on without a retry loop.
- **Message Batches API**, optional, for ingestion-time jobs that do not need an instant reply.

Assistant tools: `search_investigations`, `get_investigation`, `query_test_runs`, `get_coverage`, `get_ranking`, `compare_investigations`, `get_environment`.

The hackathon build ships three of them: `search_investigations`, `get_investigation` and `get_ranking`.

### 7.4 Ranking method

The relevance score is a weighted rubric, not a black box. Measurable parts are computed in code; Claude scores only the parts that need judgment and explains them. Users see the breakdown and can change the weights.

| Criterion | Default weight | Scored by | Changes with the environment |
| --- | --- | --- | --- |
| Atmosphere match: overlap of tested oxygen and pressure with the environment | 30 | Code | Yes |
| Fuel and material relevance to crew-cabin materials | 25 | Claude, once per investigation | No |
| Safety function: prevention, detection or suppression | 20 | Claude, once per investigation | No |
| Flow match: still air, ventilation speed or forced flow | 15 | Code | Yes |
| Gravity relevance | 10 | Code | Yes |

Scoring rules:

- Atmosphere and flow match use test runs when a record has them, otherwise the investigation-level ranges from extraction.
- A criterion with no data is marked "not available". The total is rescaled over the remaining criteria and the row carries a "partial data" tag. A missing value never counts as zero.
- Data depth is not part of the score. It appears as a badge on each row and as a filter.
- Gravity relevance gives 6 points for microgravity data, 2 more when the record also holds 1 g reference data, and 2 more for a partial-gravity proxy such as an electric field.
- The two Claude-scored criteria do not depend on the environment. A custom atmosphere is therefore ranked entirely in code, with no AI call.
- Lunar and Mars rankings differ only through the atmosphere criterion. The ranking page says so and explains that PSI holds no partial-gravity data.

### 7.5 Guardrails

- **Grounding.** The system prompt limits Claude to supplied records. If the records do not answer a question, the reply says so.
- **No AI numbers on charts.** Charts read the database. Stored AI text is checked against the cited record before it is saved. Streamed text is checked when the stream ends; the answer then shows a verified mark, or a flag on any number that does not match.
- **Partial gravity.** Claude must state that PSI holds no partial-gravity data and present microgravity and 1 g results as bounds.
- **Labeling.** AI content carries an "AI-generated" mark, its model and date, and a link to sources.
- **Review.** Output is published after automated checks and enters as "unreviewed". Hackathon judges and experts are the scientific reviewers. An admin can hide or regenerate any item they flag.
- **Injection resistance.** Text from ingested files is passed as data, never as instructions. Tools cannot write or reach the network.
- **Not a safety authority.** Every page states that the site is a research aid and does not replace NASA flammability standards or testing.

### 7.6 Evaluation and cost

- The golden set holds 30 questions. Each stores the PSI records that must be cited and the key numbers with a tolerance. An automated grader runs in CI on every prompt or model change; release needs 90% passed and zero uncited numbers.
- Hackathon judges and experts review wording and science separately, outside CI.
- Each stored result records model, prompt version and input hash. Unchanged input is never regenerated.
- Token usage is logged per job, so cost can be reported.
- The public AI endpoints (assistant and comparison) share a global daily token limit, set by `AI_DAILY_TOKEN_LIMIT`. When it is reached they return a notice and stored content keeps working. Background generation is not limited.
- Each visitor is also limited: a message cap per session and per IP address per day, and a maximum output length.
- Assistant latency targets: a status line within 1 second and the first answer word within 8 seconds, measured at build step 8.

## 8. Functional requirements

The site has eleven public pages and one admin area. Pages marked "Core" form the first release; "Next" follows without changes to the architecture.

| # | Page | What the user sees and does | Release |
| --- | --- | --- | --- |
| 1 | Overview | Key counts, three safety tiles (prevention, detection, suppression), latest insight cards, incident timeline, intro video | Core |
| 2 | Investigations | Catalogue as cards or table. Filters: fuel state, fuel, facility, safety function, oxygen range, flow, years, data depth | Core |
| 3 | Investigation detail | AI summary at two reading levels, objectives, fuels and sample geometry, condition ranges, what varied and what stayed fixed, sensors, hardware, files, publications, related records | Core |
| 4 | Environment ranking | Pick a crew environment or enter a custom atmosphere. Ranked list with score breakdown, rationale and weight sliders | Core |
| 5 | Compare | Two to four investigations side by side: attribute matrix, shared hardware, AI similarities and differences | Core |
| 6 | Data explorer | Test-run table with filters and column chooser, parameter charts, CSV and JSON export with provenance columns | Core |
| 7 | Coverage and gaps | Heatmap of tested oxygen against pressure or flow, exploration atmospheres overlaid, gap cards, partial-gravity placeholder | Core |
| 8 | Research assistant | Chat with streamed, cited answers, suggested questions, links that open a filtered view | Core |
| 9 | Earth applications | Spinoff stories linked to the investigations behind them | Next |
| 10 | Learn | Short illustrated primer on flames in microgravity, glossary | Next |
| 11 | About and method | Data sources, scoring rubric, AI disclosure, limitations, citation guidance | Core |
| 12 | Admin | Ingestion runs, review queue, environments, weights, vocabularies, prompt versions | Core |

### 8.1 Page requirements

**Investigation detail**

- Shows the PSI identifier, DOI and a "View on PSI" link at the top.
- Presents test conditions as ranges with counts, for example the oxygen span and the number of runs.
- Lists variables in two groups: varied between tests, and held constant.
- Shows a clear notice when a record has no per-test data, instead of empty charts.

**Environment ranking**

- Recalculates the order in the browser when weights change; no AI call is needed.
- Explains every sub-score in one sentence with a citation.
- Offers "Why is this ranked low?" for any record.

**Compare**

- Highlights cells that differ. Flags pairs whose measurements are not directly comparable, with the reason.
- Groups records that share hardware: ACME insert in CIR, MDCA in CIR, SPICE flow duct in MSG.

**Data explorer**

- Charts: oxygen against pressure, oxygen against flow speed, outcome by fuel, parallel coordinates across all conditions.
- Every exported row carries PSI identifier, file, row number and retrieval date.
- Missing values export as empty, with a separate flag column.

**Coverage and gaps**

- Draws the expected lunar habitat region (30% oxygen or more, 10.2 psi or less) on the chart.
- Lists investigations nearest to each untested region.
- States plainly that no partial-gravity data exists in PSI, and names the records that can bound it.

**Research assistant**

- Each answer shows numbered citations that open the source passage.
- Declines questions outside combustion and fire safety with a short redirect.
- Shows history for the browser session only. The session is an anonymous cookie ID that expires when the browser closes.

### 8.2 Across all pages

- Global search over investigations, fuels, hardware and publications.
- Filters and selections are stored in the URL, so any view can be shared as a link.
- Print-friendly report for an investigation, a ranking or a comparison.
- Version 1 is public and read-only. Only the admin area requires login.

## 9. REST API

The API is versioned under `/api/v1/`, public and read-only except for the assistant and admin. The OpenAPI schema is generated from code and is the contract for the front end.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/investigations/` | List with filters, search, ordering and pagination |
| GET | `/investigations/{psi_id}/` | Full record with summary, condition ranges, facilities, instruments, publications |
| GET | `/investigations/{psi_id}/test-runs/` | Test runs of one investigation |
| GET | `/investigations/{psi_id}/files/` | PSI file inventory with links |
| GET | `/test-runs/` | Cross-investigation test runs. Filters: fuel, fuel\_form, oxygen, pressure, flow, gravity, outcome |
| GET | `/test-runs/export/` | Same filters, returns CSV or JSON with provenance columns |
| GET | `/projects/`, `/facilities/`, `/instruments/`, `/publications/` | Reference lists |
| GET | `/environments/` | Reference crew environments |
| GET | `/environments/{id}/ranking/` | Ranked investigations with sub-scores and rationale |
| POST | `/rankings/custom/` | Ranking for a user-defined atmosphere and weights. Computed in code, with no AI call |
| GET | `/coverage/` | Binned counts of test runs on two chosen condition axes |
| POST | `/comparisons/` | Compare two to four investigations. Returns the stored result as JSON, or streams a new one as server-sent events and stores it |
| GET | `/insights/` | Insight cards by type and target |
| GET | `/search/` | Global search across entities |
| POST | `/assistant/conversations/` | Start a conversation |
| POST | `/assistant/conversations/{id}/messages/` | Send a message. Reply is a server-sent event stream |
| GET | `/jobs/{id}/` | Status of a background job |
| GET | `/meta/stats/` | Counts and last refresh date for the Overview page |
| GET | `/schema/`, `/docs/` | OpenAPI schema and interactive documentation |

**Conventions**

- JSON everywhere, snake\_case fields, ISO 8601 dates, one fixed unit per quantity, named in the field.
- Page-number pagination with `count`, `next`, `previous`, `results`. Default page size 25, maximum 200.
- Range filters use `_min` and `_max` suffixes, for example `oxygen_pct_min=30`.
- One error format: `{"error": {"code", "message", "details"}}` with the matching HTTP status.
- Every AI-bearing response includes `citations`, `model`, `generated_at` and `review_status`.
- Throttling by IP: generous for read endpoints, strict for assistant and comparison endpoints, which also share a global daily token limit.
- List and detail responses are cached in Redis and invalidated when an ingestion run publishes.

## 10. Design and user experience

The visual idea comes from the subject: on Earth a flame is a warm teardrop, in free fall it is a blue sphere. Cool blue marks microgravity, warm amber marks Earth gravity and hazard.

### 10.1 Themes

Two themes share one set of design tokens. The site follows the system setting on first visit; a toggle in the top bar overrides it and is remembered.

| Token | Dark theme "Orbit" (default) | Light theme "Daylight" |
| --- | --- | --- |
| Background | `#0B0F1A` | `#F7F8FA` |
| Surface (cards, panels) | `#141A2A` | `#FFFFFF` |
| Primary text | `#E8ECF4` | `#121826` |
| Accent, microgravity | `#4DA3FF` | `#1F6FEB` |
| Warm, Earth gravity and hazard | `#FFB454` | `#B45309` |

These values are a starting point for the design phase. Prevention, detection and suppression each get their own hue and icon, used the same way on every page.

### 10.2 Layout and type

- Left sidebar for the main pages, top bar with global search, theme toggle and assistant button.
- Content on a 12-column grid, maximum width 1440 px, cards with 12 px corners and generous spacing.
- Inter for interface text. IBM Plex Mono for numbers, units and PSI identifiers, so values line up in tables.
- The assistant opens as a side panel on any page, and as a full page for long sessions.

### 10.3 Signature elements

- **Flame comparison hero** on the Overview: the same flame at 1 g and in microgravity, with a slider between them, using NASA imagery.
- **Citation chips**: small numbered markers in AI text that open the source passage and the PSI link.
- **Score bars**: each ranking row shows its five sub-scores as a stacked bar, so the reason for the rank is visible without a click.
- **Coverage map**: tested conditions as a heatmap with exploration atmospheres drawn as outlined regions.

### 10.4 Usability rules

- A first-time visitor reaches a useful answer in three clicks from the Overview.
- Technical terms such as "limiting oxygen index" and "co-flow" carry a tooltip that links to the glossary.
- Charts always label axes with units, show the source on hover, and use a palette that is safe for color-blind readers.
- Color is never the only signal. Status and category also use icons or text.
- Loading states use skeletons. AI text streams in. Empty states explain why there is no data and what to try.
- Motion is subtle and is disabled when the system asks for reduced motion.

### 10.5 Accessibility and devices

- WCAG 2.2 level AA: contrast, full keyboard use, visible focus, screen-reader labels on charts and controls.
- Desktop first at 1280 px and wider. Tablet is fully usable. Phones get reading views: Overview, detail pages, assistant.

### 10.6 Imagery and attribution

- Photos and video come from NASA sources, each with a credit line.
- The NASA insignia is not used. The footer states that the site is independent and not endorsed by NASA.

### 10.7 Design deliverables

The agent implements the tokens from section 10.1 as theme variables, builds the component library in code, and checks every page in both themes with screenshots. No separate design file is produced.

## 11. Non-functional requirements

The dashboard must stay fast and usable even when the Claude API or PSI is unavailable, because all core views read stored data.

| Area | Requirement |
| --- | --- |
| Performance | Read endpoints answer in under 300 ms at the 95th percentile. Pages reach largest contentful paint in under 2.5 s. JavaScript is split per page |
| Resilience | If Claude is unreachable, stored summaries and scores still show and the assistant displays a clear notice. If PSI is unreachable, the last snapshot is served with its date |
| Availability | 99% monthly on a single server. Health endpoints for API, database, Redis and worker |
| Security | Plain HTTP on the server IP at launch, because there is no domain. The admin is reachable only through an SSH tunnel. Secrets in environment variables, never in the repository or the browser bundle. CORS allowlist, content security policy, Django security middleware, throttling |
| AI safety | Read-only tools, ingested text handled as data, output validated against schema, per-session limits |
| Privacy | No account or personal data needed. Assistant conversations are stored 30 days under the anonymous session ID, without IP addresses, for quality review. The visitor sees them only during the session, and the About page says they are kept |
| Data integrity | Provenance on every value, checksums on every file, no synthetic or estimated data points |
| Browsers | Last two versions of Chrome, Edge, Firefox and Safari |
| Language | English only |
| Maintainability | Type hints and Ruff on the back end, strict TypeScript on the front end, API client generated from the OpenAPI schema |

**Testing**

- Back end: pytest unit and API tests, 80% line coverage or better. Parsers are tested against saved excerpts of real PSI tables.
- Front end: Vitest and React Testing Library for components, Playwright for the three acceptance scenarios in section 3.
- AI: the golden-set evaluation in section 7.6 runs in CI when prompts change.
- Accessibility: automated axe checks in CI plus scripted keyboard-navigation tests.

## 12. Deployment

The whole system runs from one Docker Compose file: six services on one server, with Nginx as the only public entry point. The agent deploys over SSH, and the site is reached by the server's IP address.

| Service | Role | Notes |
| --- | --- | --- |
| `nginx` | Listens on port 80, serves the built React app, proxies `/api/` | Compression, cache headers for static files, buffering off on the assistant stream path. Does not proxy `/admin/` |
| `web` | Django and DRF under Gunicorn with Uvicorn workers | Runs migrations on release. Stateless. Also bound to `127.0.0.1:8001` on the host for admin access |
| `worker` | Celery worker | Ingestion and AI jobs. Separate queue for batch work |
| `beat` | Celery Beat | Weekly PSI refresh, batch result polling |
| `db` | PostgreSQL | Named volume, nightly dump to a backup directory, restore tested |
| `redis` | Broker and cache | No persistence needed |

**Build**

- The front end is built in a multi-stage Dockerfile; only static files are copied into the Nginx image.
- One back-end image serves `web`, `worker` and `beat` with different start commands.

**Environments**

- Local: `docker compose up` with hot reload and the seeded dataset.
- Production: one server. The agent connects over SSH, pulls the repository, writes `.env`, and runs `docker compose -f docker-compose.prod.yml up -d --build`.
- There is no staging server. AI output is checked locally before each deploy.

**Access without a domain**

- The site is served at `http://<server-ip>/`. `DJANGO_ALLOWED_HOSTS` and the CORS allowlist hold that address. The hosts list also includes localhost and 127.0.0.1, so the admin tunnel is accepted.
- Without a domain there is no publicly trusted certificate, so traffic is plain HTTP. This is acceptable for a public, read-only demo with no user accounts.
- The Django admin is never exposed publicly. It is opened through an SSH tunnel: `ssh -L 8001:localhost:8001 user@server`, then `http://localhost:8001/admin/`.
- The server firewall opens ports 22 and 80 only.
- The Nginx configuration keeps a commented HTTPS server block, ready to enable when a domain is added.

**Supplied by the project owner:** server address, SSH user and key, and the Claude API key.

**Configuration** (environment variables)

`DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS` (server IP, `localhost`, `127.0.0.1`), `DATABASE_URL`, `REDIS_URL`, `ANTHROPIC_API_KEY`, `CLAUDE_MODEL_FAST`, `CLAUDE_MODEL_DEEP`, `CLAUDE_MODEL_FRONTIER`, `AI_DAILY_TOKEN_LIMIT`, `PSI_BASE_URL`, `SENTRY_DSN`.

**Repository layout**

`backend/` (Django project and apps: catalog, ingestion, ai, assistant), `frontend/` (React app), `deploy/` (Nginx config, Compose files), `docs/` (this specification, data dictionary, prompt library).

**Server sizing.** An estimate for version 1 is 2 virtual CPUs, 4 GB of memory and 40 GB of disk, since raw PSI files are not stored.

## 13. Delivery plan

An AI coding agent builds this product. It delivers the hackathon demo first, in eleven ordered steps, numbered 0 to 10, that each end with a check the agent runs itself. The full build then follows six phases; a human team of three would need about 6 to 7 weeks to complete them, as a rough estimate.

### 13.1 Rules for the implementing agent

- Treat this document as the source of truth. Where it is silent, choose the simplest option that fits section 6 and log the choice in `docs/decisions.md`.
- Build in the order of section 13.3. Do not start a step before the previous check passes.
- Never invent data. Seed records come only from PSI and the NASA pages in section 4, each with its URL. Unknown values stay empty.
- Keep secrets in `.env`, never in the repository. Commit a `.env.example` with placeholder values.
- Commit after every step with a message that names the step. Run linters and tests before each commit.
- Keep `README.md` and `docs/progress.md` current: what is built, how to run it, what is left.
- Stop and ask the project owner when PSI data cannot be retrieved, a credential is missing, a check still fails after two fix attempts, or a server action would delete data.

### 13.2 Weekend scope

The weekend goal is one convincing path: pick a crew environment, see ranked investigations, open a cited summary, ask the assistant a follow-up question.

**What is cut for the weekend**

| Full design | Weekend version |
| --- | --- |
| Automated PSI ingestion | 10 to 12 investigations named in the challenge brief, entered by hand as fixtures, each with its PSI link |
| Test runs from every experiment table | Tables from two or three records that publish per-test data |
| Celery, Redis, batch jobs | One management command generates and stores AI output. Compose runs Nginx, Django and PostgreSQL only |
| Twelve pages | Overview, Investigations with detail, Environment ranking, one Coverage chart, Assistant |
| Review queue, golden-set evaluation | The agent checks every demo summary against its cited record. Judges and experts review at the event |
| Two themes | Dark theme first, light theme if time allows |

### 13.3 Build steps

Steps run in order. A step is finished only when its check passes.

| Step | Build | Check |
| --- | --- | --- |
| 0. Access probe | Try the three PSI access routes in section 4.6 and log which one works | Raw content of at least one seed record is saved. If no route works, stop and ask the owner for exports |
| 1. Scaffold | Repository layout from section 12; Compose with Nginx, Django and PostgreSQL; empty React app | `docker compose up` starts all services and `/api/v1/meta/stats/` returns 200 |
| 2. Data model | Models from section 5, migrations, Django admin | Migrations apply cleanly and model tests pass |
| 3. Seed data | Fixtures for the seed set in section 4.6 and two or three test-run tables, loaded by a management command | Record count matches the fixtures and every record has a PSI link |
| 4. Catalogue API | List, detail, filters, search, OpenAPI schema | API tests pass and the schema builds without warnings |
| 5. Catalogue pages | App shell, dark theme tokens, Investigations and detail pages | End-to-end test: browse, filter, open a record |
| 6. AI generation | Extraction as JSON with evidence quotes, summaries as cited prose, run by a management command and stored | Every seeded record has condition ranges or a "not available" mark, and a summary with at least one citation. Every evidence quote is found in its source |
| 7. Ranking and coverage | Reference environments, relevance judgment job, rubric scoring in code, ranking page, one coverage chart | Sub-scores add up to the total, a record without test runs is ranked from its ranges, and the lunar habitat scenario passes end to end |
| 8. Assistant and Overview | Streaming chat with `search_investigations`, `get_investigation` and `get_ranking`, citation chips, number check after the stream, refusal handling, Overview page | Five demo questions return cited answers, an off-topic question is declined, and a status line appears within 1 second |
| 9. Deploy | Production Compose file, deployment over SSH, daily token limit set | The site and the health endpoint answer on the server IP, and the admin opens through the SSH tunnel |
| 10. Handover | README, demo script, list of known limitations | A fresh clone runs with the documented commands |

**Supplied by the project owner.** Server address, SSH user and key; the Claude API key; exported PSI records if the agent cannot read the PSI site; an answer whenever the agent stops with a question.

### 13.4 Full build after the event

Six phases turn the demo into the full specification.

| Phase | Deliverables | Done when |
| --- | --- | --- |
| 0. Discovery | Confirmed PSI access route, inventory of combustion records and their tables, final rubric | Data inventory and API contract are written down |
| 1. Foundation | Automated tier 1 ingestion, Celery and Redis, full admin, CI | All combustion records are in the database with source links |
| 2. Core dashboard | Light theme, complete Investigations and detail pages, review queue | A visitor can browse and read cited summaries in both themes |
| 3. Analysis | Tier 2 ingestion, Data explorer with export, Compare, full Coverage and gaps | The three acceptance scenarios pass in automated tests |
| 4. Assistant and insights | Full tool set, insight cards, Earth applications, Learn | Golden-set evaluation reaches its targets |
| 5. Hardening | Test coverage, accessibility checks, performance tuning, documentation | Success criteria in section 2 are met on the server |

Weekend work carries over: the fixtures become parser test data, and the demo pages are the starting point for phase 2.

## 14. Risks and decisions

The largest risk is data access, not the AI: PSI has no documented API and its records differ widely in depth.

| Risk | Effect | Mitigation |
| --- | --- | --- |
| PSI access route is unstable or blocked | Ingestion cannot run automatically | Discovery first. Fallbacks: the public AWS bucket if it holds combustion records, then a manually exported seed set. Snapshots keep the site running |
| Experiment tables use different layouts, units and missing-value markers | Wrong or mixed values in charts | One parser per layout, raw row kept, AI-assisted mapping with human review, unit tests on real excerpts |
| Some records have no per-test data | Empty charts, misleading comparisons | `data_depth` field drives the interface. Qualitative records are described, not charted |
| AI states something the data does not support | Loss of trust, unsafe conclusions | Citations required, numeric check against records, review queue, evaluation set, visible AI labels |
| Ranking is read as an official safety rating | Misuse in real design decisions | Open rubric, adjustable weights, disclaimer on every ranking view |
| No partial-gravity data | Lunar and Martian answers are indirect | Explicit gap notice, bounds from microgravity and 1 g, gravity field ready for future PSI data |
| Claude API rate limits | Slow assistant or stalled generation | Stored results, prompt caching, retries with backoff, session limits |
| A model is retired or replaced | Output changes | Model IDs in configuration, prompt versions stored, evaluation rerun before any switch |
| No domain, so no HTTPS | Traffic is unencrypted and browsers mark the site as not secure | Public side is read-only with no accounts. Admin only through an SSH tunnel. HTTPS block ready for when a domain is added |

**Decisions**, confirmed by the project owner on 14 November 2026

| Question | Decision | Applied in |
| --- | --- | --- |
| Who builds the product | An AI coding agent, working from this specification | Section 13 |
| Accounts | None. Version 1 stays public and read-only | Section 8.2 |
| Scientific review of AI output | Hackathon judges and experts | Section 7.5 |
| Mars habitat and space station atmospheres | Standard NASA values | Section 5.2 |
| Language | English only | Section 11 |
| Hosting | One server reached over SSH, no domain, access by IP address | Section 12 |
| Claude API budget | Not capped for the build. Public AI endpoints carry a daily token limit as abuse protection | Sections 7.2 and 7.6 |

**Revised after the implementing agent's review**, 14 November 2026: access probe and seed set (4.6), condition ranges and units (5), evidence quotes for JSON jobs, thinking and refusal handling (7.3), ranking rubric (7.4), checks on streamed text (7.5), grader, token limit and latency targets (7.6), comparison and custom ranking endpoints (9), session and tunnel settings (11, 12), build step 0 (13.3).

## 15. Sources

Opened while writing this specification, on 14 November 2026:

- [NASA Glenn: Combustion Science](https://www.nasa.gov/glenn/glenn-expertise-space-exploration/physical-sciences-program/combustion-science/)
- [A Researcher's Guide to: Combustion Science](https://www.nasa.gov/missions/station/a-researchers-guide-to-combustion-science/)
- [PSI database guide (PDF)](https://science.nasa.gov/wp-content/uploads/2024/11/psi-database-guide.pdf)
- [NASA PSI on the AWS Registry of Open Data](https://registry.opendata.aws/nasa-psi/)
- [Public PSI audit by Space Apps team AFAQ (GitHub)](https://github.com/YoussefHegazy74/flame-in-freefall), third-party and unverified
- [Claude models overview](https://platform.claude.com/docs/en/models/overview)
- [Claude API features overview](https://docs.claude.com/en/docs/build-with-claude/overview)

Atmosphere values in section 5.2 were checked against two NASA records found by search: [Risk of Hypobaric Hypoxia from the Exploration Atmosphere](https://ntrs.nasa.gov/citations/20150021491) and a [2024 exploration atmosphere overview](https://ntrs.nasa.gov/citations/20240003211).

The [PSI search page](https://psi.nasa.gov/physci/repo/search?q=combustion&data_source=psi&data_type=investigation) could not be read automatically because it renders in the browser. Investigation names, hardware groupings and atmosphere figures are taken from the challenge brief.

Provided in the brief and listed in section 4 as inputs for ingestion, not yet reviewed in detail: the Apollo 1, Apollo 13 and Mir pages, the three NASA Spinoff pages and the ScienceCast video.
