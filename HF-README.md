---
license: other
license_name: public-domain
license_link: https://www.courtlistener.com/help/api/bulk-data/
tags:
- judges
- federal-courts
- financial-disclosures
- judiciary
- courtlistener
- free-law
- duckdb
- datapond
pretty_name: CourtListener judges, courts and federal judicial financial disclosures
  (bulk data)
size_categories:
- 1M<n<10M
---

# CourtListener Judges, Disclosures and Oral Arguments

September 30, 2026 snapshot: 16,191 judge-database people, 51,291 positions,
3,361 courts, 32,336 federal judicial disclosure reports (1987-2022), and
103,710 oral-argument records, including 103,418 source speech-to-text transcripts.
Twenty tables include education, party affiliations, race, disclosure line items,
lower-court information and judge-to-opinion links. Transcripts may contain recognition
errors. Join `judges.fjc_id` to `fjc-judges.judges.jid`, not its `nid` field. Of 3,711 populated IDs, 3,710 match the October 17 FJC snapshot.

**2,277,934 rows across 20 tables.** Source snapshot: 2026-09-30. Database: 3,251,122,176 bytes.

| Table | Description | Rows | Columns |
|---|---|---:|---:|
| `originating_court_information` | Lower-court information for appellate dockets (judges, dates, docket numbers) | 1,060,419 | 16 |
| `opinion_cluster_panel` | Judge-to-opinion-cluster panel links (person_id joins judges; cluster ids refer to CourtListener opinion clusters, not included here) | 835,616 | 3 |
| `oral_arguments` | Oral-argument audio metadata and source-provided speech-to-text transcripts; transcription can contain errors | 103,710 | 23 |
| `positions` | One row per position held: judgeships (court_id joins courts), clerkships, offices and other jobs, with nomination, confirmation, start and termination dates, appointer, predecessor and how the seat was obtained | 51,291 | 38 |
| `disclosure_positions` | Outside positions reported on a disclosure | 37,050 | 7 |
| `disclosure_reimbursements` | Travel reimbursements reported on a disclosure | 33,472 | 10 |
| `financial_disclosures` | One row per federal judicial financial disclosure report (person_id joins judges): year, report type, amendment flag, page count and the original PDF's storage path | 32,336 | 16 |
| `disclosure_spousal_income` | Spousal income reported on a disclosure | 20,174 | 7 |
| `disclosure_debts` | Liabilities reported on a disclosure, with value code | 18,775 | 8 |
| `judges` | One row per person in CourtListener's judge database (federal and state judges, plus some other public figures): names, birth/death, gender, religion, FJC judge id (fjc_id joins fjc-judges.judges.jid) | 16,191 | 26 |
| `disclosure_non_investment_income` | Non-investment income (teaching, book royalties ...) reported on a disclosure | 15,302 | 8 |
| `educations` | One row per degree (school_id joins schools) | 12,777 | 8 |
| `disclosure_agreements` | Agreements reported on a disclosure (financial_disclosure_id joins financial_disclosures) | 10,007 | 7 |
| `political_affiliations` | One row per recorded party affiliation with its source and dates | 8,486 | 10 |
| `judge_races` | Person-to-race links (race_id decoded in the race column) | 6,542 | 4 |
| `schools` | Law schools and universities | 6,011 | 6 |
| `courthouses` | Courthouse addresses per court | 3,361 | 11 |
| `courts` | Every court CourtListener tracks (federal, state, tribal, special), with jurisdiction, PACER and FJC ids, dates and parent court | 3,361 | 20 |
| `disclosure_gifts` | Gifts reported on a disclosure | 2,025 | 8 |
| `opinion_joined_by` | Judge-to-opinion 'joined by' links (person_id joins judges; opinion ids refer to CourtListener opinions, not included here) | 1,028 | 3 |

## Quick start

```sql
SET memory_limit='128MiB'; SET threads=1; SET max_temp_directory_size='0B';
INSTALL httpfs; LOAD httpfs;
ATTACH 'https://huggingface.co/datasets/Nason/courtlistener-database/resolve/3bb4dfe4482b8b7c8a04f40ab7a1c5710d7205d6/courtlistener.duckdb' AS cl (READ_ONLY);

SELECT j.id AS judge_id, j.name_last, j.name_first, d.year, COUNT(g.id) AS gifts
FROM cl.financial_disclosures d JOIN cl.judges j ON j.id = d.person_id
LEFT JOIN cl.disclosure_gifts g ON g.financial_disclosure_id = d.id
WHERE d.year >= 2018 GROUP BY 1, 2, 3, 4 HAVING COUNT(g.id) > 0 ORDER BY gifts DESC, judge_id, d.year LIMIT 20;
```

Install/upgrade Python with `python -m pip install --upgrade datapond` (the examples use 0.1.5), or install released R datapond from [CRAN](https://cran.r-project.org/package=datapond) with `install.packages("datapond")`. R 0.1.1 remains a separate development version. The catalog ID is `courtlistener`.

Remote queries run on your machine. File size is disk storage, not required RAM; selected columns reduce transfer, but filters and a final `LIMIT` do not guarantee a small scan. A 128 MiB setting limits DuckDB's buffer pool, not the whole Python/R process. Larger queries can fail with spill disabled. Download only when you have room for the file, temporary download bytes and any existing copy. The direct SQL above sets limits before attachment.

The gift query counts recorded items by person and report year, not unique reports or a population rate. Grouping by the person ID prevents equal names from being merged. Check `is_amended` and the source reports before interpreting totals.

[Dictionary](https://huggingface.co/datasets/Nason/courtlistener-database/blob/3bb4dfe4482b8b7c8a04f40ab7a1c5710d7205d6/DICTIONARY.md) · [Source and caveats](https://github.com/ian-nason/courtlistener-database#source-interpretation-and-compatibility)

Build pipeline and caveats: https://github.com/ian-nason/courtlistener-database
Source: Free Law Project, CourtListener bulk data (Public Domain Mark); please credit CourtListener.
Financial disclosures have uneven coverage and end in 2022. Dockets, opinion text,
investment holdings and audio files are not included. Position dates include an upstream
year-0217 outlier, retained as supplied. Other source dates extend from year 0022 to 3036; these outliers do not describe meaningful coverage. Quoted empty strings and unquoted missing values
both normalize to NULL, preserving the earlier database convention. Transcripts increase
the file size to about 3.03 GiB; use selected columns and filters for remote queries.
