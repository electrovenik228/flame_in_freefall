# Progress

Weekend build, section 13.3 of the specification. A step is done only when its check has passed.

| Step | Status | Check result |
| --- | --- | --- |
| 0. Access probe | Done | Owner export `psi-combustion-seed.json` holds all 12 seed records; see decisions log |
| 1. Scaffold | Done | `docker compose up` starts db, web and nginx; `/api/v1/meta/stats/` returns 200 |
| 2. Data model | Done | Migrations apply cleanly on a fresh database; 9 model and scaffold tests pass |
| 3. Seed data | Done | 23 investigations loaded, equal to the fixture; every record has its PSI link; 749 test runs from 7 tables |
| 4. Catalogue API | Done | 31 tests pass; OpenAPI schema builds with `--validate --fail-on-warn` |
| 5. Catalogue pages | Done | Playwright: browse, filter, open a record (4 tests pass); pages checked by screenshot in dark and light themes |
| 6. AI generation | Done for the seed set | All 12 seed records, and 21 of 23 in total, have verified evidence quotes, ranges or a "not available" mark, and a cited summary. PSI-39 and PSI-47 are pending: the API account ran out of credit |
| 7. Ranking and coverage | Done, AI judgment pending credit | Sub-scores add up to the total (test); a record without test runs is ranked from its ranges (test); the lunar habitat scenario passes end to end in the browser. The relevance judgment job is built and tested but has not run for lack of API credit, so fuel and safety show as "not available" and totals are rescaled |
| 8. Assistant and Overview | Partly passed, live run pending credit | Status line appears within 1 second (browser test). Streaming, citation chips, number check, refusal handling, limits: 9 tests against a stand-in for the Claude API. Five demo questions and the off-topic decline are written as a browser test (`E2E_ASSISTANT=live`) and wait for API credit |
| 9. Deploy | Not started | |
| 10. Handover | Not started | |
