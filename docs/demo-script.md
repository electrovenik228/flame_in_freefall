# Demo script

About five minutes. It follows the weekend goal: pick a crew environment, see ranked investigations, open a cited summary, ask the assistant a follow-up question. Before you start, check that the site loads and, if you want the live assistant, that the Claude API key has credit.

## 1. Overview (30 seconds)

Open the site. Point out:

- The flame slider: the same flame at 1 g and in free fall. It is a drawn illustration.
- The counts: 23 Combustion Science records from NASA PSI, 749 test runs with conditions.
- The three safety tiles and the incident cards. Each incident quote links to the NASA page it comes from.

Say: every number on a chart comes from the database; every AI statement links to the PSI record it is based on.

## 2. Lunar habitat ranking (90 seconds)

Click **Rank for a lunar habitat**.

- The atmosphere line: 30% oxygen or more, 70.3 kPa (10.2 psi) or less, 1/6 g, from the challenge brief.
- Each row has a stacked bar, one colour per criterion, so the reason for the rank is visible without a click.
- Open **Breakdown** on the top row. Each criterion has a weight, a score and one sentence of explanation with its source. The points add up to the total.
- Point out the **Partial data** tag: a criterion without data is left out and the total rescaled, never counted as zero.
- Drag the **Atmosphere match** weight down to 0. The order changes at once, in the browser, with no request. Press **Reset**.
- Read the box on the right: not a safety rating; PSI has no partial-gravity data.

## 3. A cited summary (60 seconds)

Click the top record's name, or open ACME CFI-G (PSI-159).

- PSI identifier, DOI and **View on PSI** at the top.
- The AI summary: switch between **Plain** and **Expert**. Click a numbered chip to see the exact source passage and the PSI link.
- The label under it: AI-generated, model, date, not yet reviewed by an expert.
- **Quoted evidence for the attributes read by AI** under Test conditions: every attribute has a word-for-word quote, checked by a program.
- Scroll to **Variables**: what varied between tests and what stayed fixed, computed from the 333 test runs.

## 4. Coverage map (45 seconds)

Open **Coverage and gaps**.

- Each cell counts test runs at that oxygen and pressure. The dashed box is the lunar habitat window; the markers are Earth, the station and Mars.
- Gap cards: the spacesuit atmosphere (100% oxygen, 29.6 kPa) has no test run inside it; the cards name the nearest investigations.
- The partial-gravity card names the records that can bound lunar and Martian behaviour.

## 5. Assistant (60 seconds, needs API credit)

Open **Research assistant** and ask: *How do BASS-II and Saffire differ in sample size and flow?*

- A status line appears within a second while it looks up the records.
- The answer streams in with numbered sources. When it ends, a mark says whether its numbers were found in the cited records.
- Ask something off topic, such as a recipe: it declines in one sentence.

If the key has no credit, the assistant shows a plain notice and the rest of the site keeps working. Say so and move on.

## 6. Close (15 seconds)

Open **About and method**: data sources, the rubric with its weights, the AI disclosure, the limitations, and how to cite the PSI record.

## Model-data scenario, if asked

Investigations, then **Has test runs** and **Flow speed recorded** shows the three Saffire records: air flow 20 or 30 cm/s, oxygen 21.5 to 22.1% where recorded. Each record's **Export all rows as CSV** gives every test run with its PSI file, row number and retrieval date. The full Data explorer is part of the next phase.
