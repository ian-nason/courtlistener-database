# CourtListener judges, courts and financial disclosures as a DuckDB database

The parts of [CourtListener's bulk data](https://www.courtlistener.com/help/api/bulk-data/)
(Free Law Project) that are actually exported today: the judge database, the court
registry, federal judicial financial disclosures, oral-argument metadata and the
judge-to-opinion panel links. Companion to
[fjc-judges](https://github.com/ian-nason/fjc-judges-database) (the FJC's biographical
directory, which these judges join on `fjc_id`) and
[scdb](https://github.com/ian-nason/scdb-database).

| Table | One row per | Rows |
|-------|-------------|-----:|
| `judges` | person (federal and state judges and some other public figures) | 16,190 |
| `positions` | position held: judgeships, clerkships, offices, practice | 51,289 |
| `educations` / `schools` | degree / school | 12,777 / 6,011 |
| `political_affiliations` | recorded party affiliation | 8,486 |
| `judge_races` | person-to-race link (decoded) | 6,542 |
| `courts` / `courthouses` | court / courthouse address | 3,353 / 3,352 |
| `originating_court_information` | lower-court details for appellate dockets | 3 |
| `financial_disclosures` | federal judicial financial disclosure report, 1987-2022 | 32,336 |
| `disclosure_gifts`, `disclosure_debts`, `disclosure_reimbursements`, `disclosure_agreements`, `disclosure_positions`, `disclosure_non_investment_income`, `disclosure_spousal_income` | line item on a report | 2,025 / 18,775 / 33,472 / 10,007 / 37,050 / 15,302 / 20,174 |
| `oral_arguments` | oral-argument recording (metadata only) | see dictionary |
| `opinion_cluster_panel` / `opinion_joined_by` | judge-to-opinion links | see dictionary |
| `v_judge_positions` (view) | position with judge and court names | 51,289 |

Keys: `judges.id` = `person_id` everywhere; `courts.id` = `court_id`;
`financial_disclosures.id` = `financial_disclosure_id`; `judges.fjc_id` =
`fjc-judges.judges.jid` (3,710 of 3,711 match). Columns and null rates: `DICTIONARY.md`.

## Quick start

```python
import datapond
con = datapond.connect("courtlistener")
con.sql("""
    SELECT j.name_last, j.name_first, d.year, COUNT(g.id) AS gifts
    FROM financial_disclosures d JOIN judges j ON j.id = d.person_id
    LEFT JOIN disclosure_gifts g ON g.financial_disclosure_id = d.id
    WHERE d.year >= 2018 GROUP BY 1, 2, 3 HAVING COUNT(g.id) > 0 ORDER BY 4 DESC LIMIT 20
""").show()
```

```sql
-- judges' careers alongside the FJC directory
SELECT c.name_last, c.name_first, p.court_name, p.date_start, s.appointing_president
FROM "courtlistener".v_judge_positions p
JOIN "courtlistener".judges c ON c.id = p.person_id
JOIN "fjc-judges".judges f ON f.jid = c.fjc_id
JOIN "fjc-judges".federal_judicial_service s ON s.nid = f.nid AND s.commission_date = p.date_start
WHERE p.position_type = 'jud' ORDER BY p.date_start DESC LIMIT 20;
```
(the second query needs `datapond.connect(["courtlistener", "fjc-judges"])`).

## How it was built

Each bulk CSV (PostgreSQL `COPY ... FORMAT csv`, every field quoted, backslash-escaped,
unquoted empty = NULL) is matched to the table in CourtListener's `schema.sql` with the same
column set and typed from it: integers, doubles, booleans (`t`/`f`), dates and timestamps.
The empty `retention-events` export is not loaded as a table.

## Researcher caveats

- **What CourtListener no longer exports in bulk.** The docket, opinion, opinion-cluster,
  citation and disclosure-investment files in the bucket have been 14-byte stubs since
  March 2024, so this database has judges and disclosures but not dockets, opinion text or
  investment holdings. `opinion_cluster_panel` and `opinion_joined_by` reference cluster and
  opinion ids that resolve only on courtlistener.com.
- **Financial disclosures are extracted from PDFs by Free Law Project**; values are the
  reports' letter codes and free text, coverage by year is uneven (1,759 reports for 2020,
  12 for 2022 as of the January 2025 export), and `is_amended` marks amended filings.
- **Positions cover more than judgeships** (`position_type` is NULL for 21,225 of 51,289
  rows: practice, government and academic positions); filter `position_type = 'jud'`
  and its variants for the bench.
- **The judge database is not only federal**: state judges are included with varying
  completeness, and `fjc_id` is populated only for Article III judges.
- Exports are dated 2025-01-31 (2024-05-06 for oral arguments); rebuild with
  `download_data.sh` when Free Law publishes newer files.

## Build

```bash
uv sync && ./download_data.sh && uv run python build_database.py && uv run python publish_to_hf.py --verify
```

## License

Code: MIT. Data: public records compiled by Free Law Project; CourtListener asks for credit
when its data is used.
