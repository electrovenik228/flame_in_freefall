# Known limitations

State of the weekend build on 15 November 2026. What is left is listed in [progress.md](progress.md).

## Waiting on the Claude API account

The account ran out of credit during the build. Until credit is added:

- **The assistant** shows a notice instead of answering. The five demo questions and the off-topic check (build step 8) have not been run live; the logic is tested against a stand-in.
- **The relevance judgment** (fuel and material relevance, safety function) has not been generated. Those two criteria show "not available" in every ranking, the totals are rescaled over atmosphere, flow and gravity, and every row carries the "partial data" tag. Rankings will change once the judgments exist.
- **PSI-39 (CFI) and PSI-47 (DAFT)** have no AI summary or extracted attributes. They are not in the seed set.

After adding credit: `docker compose exec web python manage.py generate_ai`, then `export_ai_output`, and run the live assistant test.

## Data

- **Seed export, not live ingestion.** Records come from the owner's export of PSI, retrieved 14 November 2026. There is no scheduled refresh. PSI-23 was missing from the export.
- **Test runs from seven tables only:** FLEX, ACME CFI-G (normal and inverse flames), BASS-II and Saffire-I, -II and -III. Other experiment tables are stored as text and used by the AI, but not charted.
- **BASS-II flow** is recorded as fan and air display settings, not a speed, so it is kept unconverted and not used for flow match.
- **ACME CFI-G inverse flames** have no ambient oxygen: their oxygen value belongs to the burner gas.
- **Ranges read from record text** may be planned ranges rather than conditions actually run. Their source is shown on each record.
- **No file inventory.** The export has no list of each record's data files, so the files section shows only experiment tables and images. Raw data is reached through the PSI link.
- **One implausible value** was left empty: FLEX row 115 lists 0 mmHg.

## Ranking

- **Flow match is not scored** for the reference environments: the challenge brief gives no ventilation speed, and no NASA figure was confirmed. It is scored for custom atmospheres with a flow window.
- **Gravity points** for 1 g reference tests and electric-field proxies come from phrase matching; the matched sentence is shown.
- The rubric's tolerances (1 percentage point of oxygen, 5 kPa, 2 cm/s) are a first choice, documented on the About page, not a validated model.

## AI

- **Not reviewed by experts yet.** All AI output is marked "not yet reviewed". The admin can approve or hide any item.
- **The number check compares numbers, not meaning.** A number that appears anywhere in the cited record passes, even if it is attached to the wrong quantity.
- **No golden-set evaluation** (30 questions with a grader) exists yet; it is part of the full build.

## Product scope

- Not built in the weekend scope: Compare, Data explorer, Earth applications and Learn pages; insight cards on the Overview; a review queue screen beyond the admin list; Celery, Redis and the weekly refresh.
- **The flame image on the Overview is a drawing**, not NASA imagery.
- **Plain HTTP** on an IP address, as the specification allows. An HTTPS block is ready in the Nginx config for when a domain exists.
- **Not deployed yet.** The production build has been tested locally; deploying needs the SSH user and key.
- **Accessibility** has keyboard use, focus marks, labelled charts with table views and colour-plus-text status, but no automated axe check in CI yet.
