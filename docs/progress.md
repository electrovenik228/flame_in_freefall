# Progress

Weekend build, section 13.3 of the specification. A step is done only when its check has passed.

| Step | Status | Check result |
| --- | --- | --- |
| 0. Access probe | Done | Owner export `psi-combustion-seed.json` holds all 12 seed records; see decisions log |
| 1. Scaffold | Done | `docker compose up` starts db, web and nginx; `/api/v1/meta/stats/` returns 200 |
| 2. Data model | Done | Migrations apply cleanly on a fresh database; 9 model and scaffold tests pass |
| 3. Seed data | Not started | |
| 4. Catalogue API | Not started | |
| 5. Catalogue pages | Not started | |
| 6. AI generation | Not started | |
| 7. Ranking and coverage | Not started | |
| 8. Assistant and Overview | Not started | |
| 9. Deploy | Not started | |
| 10. Handover | Not started | |
