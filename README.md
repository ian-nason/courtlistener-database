# CourtListener judges, courts, disclosures and oral arguments in DuckDB

This database contains selected [CourtListener bulk exports](https://www.courtlistener.com/help/api/bulk-data/)
from Free Law Project, dated **September 30, 2026**: **2,277,934 rows across 20 tables**.
The approximately **3.03 GiB** file includes source speech-to-text transcripts. It joins
the companion [FJC judges directory](https://github.com/ian-nason/fjc-judges-database)
through `judges.fjc_id`.

| Table | One row per | Rows |
| --- | --- | ---: |
| `judges` | judge-database person | 16,191 |
| `positions` | position held, including nonjudicial employment | 51,291 |
| `educations` / `schools` | degree / school | 12,777 / 6,011 |
| `political_affiliations` | recorded affiliation | 8,486 |
| `judge_races` | person-to-race link, with decoded label | 6,542 |
| `courts` / `courthouses` | court / courthouse address | 3,361 / 3,361 |
| `originating_court_information` | appellate docket's lower-court information | 1,060,419 |
| `financial_disclosures` | judicial disclosure report, 1987–2022 | 32,336 |
| `disclosure_agreements` | agreement | 10,007 |
| `disclosure_debts` | liability | 18,775 |
| `disclosure_gifts` | gift | 2,025 |
| `disclosure_non_investment_income` | income item | 15,302 |
| `disclosure_positions` | outside position | 37,050 |
| `disclosure_reimbursements` | reimbursement | 33,472 |
| `disclosure_spousal_income` | spousal income item | 20,174 |
| `oral_arguments` | recording metadata, with transcripts when supplied | 103,710 |
| `opinion_cluster_panel` / `opinion_joined_by` | judge-to-opinion link | 835,616 / 1,028 |

`v_judge_positions` joins the 51,291 positions to judges and courts. Keys are
`judges.id = person_id`, `courts.id = court_id`, and
`financial_disclosures.id = financial_disclosure_id`. Of 3,711 populated FJC IDs,
3,710 match the October 17, 2026 FJC directory's `judges.jid`.
See [DICTIONARY.md](DICTIONARY.md) for columns, types and null rates and
[refresh provenance](docs/refresh-2026-09-30.json) for source identities and audit results.

## Quick start

```python
import datapond
con = datapond.connect("courtlistener")
con.sql("""
    SELECT j.name_last, j.name_first, d.year, COUNT(g.id) AS gifts
    FROM financial_disclosures d JOIN judges j ON j.id = d.person_id
    LEFT JOIN disclosure_gifts g ON g.financial_disclosure_id = d.id
    WHERE d.year >= 2018
    GROUP BY 1, 2, 3 HAVING COUNT(g.id) > 0 ORDER BY 4 DESC LIMIT 20
""").show()
```

R is available on [CRAN](https://cran.r-project.org/package=datapond):

```r
install.packages("datapond")
con <- datapond::dp_connect("courtlistener")
DBI::dbGetQuery(con, "SELECT COUNT(*) AS judges FROM judges")
DBI::dbDisconnect(con, shutdown = TRUE)
```

Remote queries should select needed columns and filter early. Transcript text accounts
for most of the database size; avoid collecting the whole table into application memory.

Originating-court information grew from 38,926 to 1,060,419 source records; its IDs
and oral-argument IDs were checked for uniqueness as well as matching source counts.

## Source interpretation and compatibility

- The 23 pinned source files total 731,431,632 compressed bytes. CourtListener publishes
  quarterly snapshots, not incremental changes. A snapshot date does not imply every
  table has observations through that date.
- There are 103,418 populated `stt_transcript` values. These source speech-to-text
  transcripts may contain recognition errors; audio files are not included.
- All previous column names, types and order remain. `stt_transcript`, `stt_source`
  and originating `docket_number_raw` are additive. Retired `stt_google_response`
  remains NULL in its original position, matching every row in the previous artifact.
- Types follow the pinned PostgreSQL schema. The originating-court export omits
  `date_rehearing_denied`, as confirmed by its official import script; this specific
  schema-only field is excluded. Other unexpected schema differences fail the build.
- PostgreSQL backslash escaping and quoted newlines are parsed explicitly. As in the
  previous database, quoted empty strings and unquoted missing values both become NULL.
  Integer overflow, fractional integer values and invalid dates/booleans fail conversion.
  Numeric/DOUBLE columns retain the prior floating-point representation and can round decimals.
- Disclosure reports are extracted from PDFs and have uneven coverage: 1,759 reports
  for 2020, 14 for 2021, and 12 for 2022. `is_amended` identifies amended reports.
- Position type is NULL in 21,225 rows. Positions include law practice, government
  and academic jobs. The latest recorded start is 2024-12-31. Position ID 44355 has
  source date `0217-08-11`; it is retained without inventing a correction. Across all
  date columns, supplied outliers extend from `0022-01-01` (position 22118 termination)
  to `3036-03-30` (originating-court record 966838 judgment entry). Both extremes were
  verified against raw exports. These are data-quality limits, not meaningful coverage.
- Judges include federal and state courts with varying completeness. Empty retention
  events are omitted. Dockets, opinion text and investment holdings are not included;
  opinion link targets must be resolved through CourtListener.

## Bounded local build

Use the existing environment and a new output directory. Python 3.10+ and DuckDB
1.4.4+ are required; the refresh used DuckDB 1.5.5 and read/storage compatibility
was checked with the existing 1.4.4 runtime. This recipe does not publish.

```bash
work="/path/to/new-refresh"
mkdir -p "$work"
.venv/bin/python download_sources.py --manifest docs/bulk_manifest.json \
  --raw-dir "$work/data/raw" --receipt "$work/verified-manifest.json"
DATAPOND_MEMORY_LIMIT=256MB DATAPOND_THREADS=1 .venv/bin/python build_database.py \
  --manifest "$work/verified-manifest.json" --raw-dir "$work/data/raw" \
  --temp-dir "$work/chunks" --output "$work/courtlistener.duckdb" \
  --dictionary "$work/DICTIONARY.md" --audit "$work/build-audit.json"
.venv/bin/python -m unittest test_refresh test_streaming test_download_sources test_publish_checked -v
```

The builder refuses existing databases/WALs, dictionaries and audit files. Downloads
stream to temporary files and reject changed identities, sizes or pinned hashes before
installation; existing unverified files are preserved. CSV batches are at most 8 MiB
and 10,000 records. The builder defaults to 256 MB DuckDB memory, one thread, 128 MiB
spill, and **2,048-row native storage groups**, with checkpoints between batches.
An external monitor should also bound total RSS and scratch space, because DuckDB's
memory setting does not cover every allocation. The September build used 467 MiB peak
RSS and 3.22 MiB peak spill, completing in 214 seconds.

When reopening a candidate for writes, attach it with `(ROW_GROUP_SIZE 2048)` using
the same memory/temp limits. A direct open followed by a metadata checkpoint caused
unexpectedly large scratch use during this refresh and was stopped. Keep original
artifacts and failed staging files until recovery has been verified.

## Audited publication and recovery

`publish_checked.py` requires a validated provenance file, exact database and dictionary
SHA-256, matching actual counts and schemas, a working card example, and the expected
existing Hugging Face parent commit. Use `--dry-run` first. It uploads database, card,
dictionary and provenance in one commit, with one standard-LFS worker and existing
authentication. It verifies LFS identity and pinned/main queries using 128 MB DuckDB
and the already installed HTTP extension. No automatic software installation occurs.

An upload receipt is saved before remote queries. If verification fails, inspect the
receipt and use `--verify-only --commit FULL_COMMIT_SHA`; do not upload again. If a
network error occurs before the receipt is saved, inspect the remote head before retrying.

The previous hosted snapshot is immutable at
[`012f6e85`](https://huggingface.co/datasets/Nason/courtlistener-database/tree/012f6e852fe9ca113419ca4d9609642be064ae2f).
The original local database is retained. Recovery should restore that revision's database
and README in a new atomic commit guarded by the current parent, and remove only new
hosted metadata paths absent from that revision after inspecting its file list. Keep
local evidence. No reset, deletion of the original, or rollback has been performed.

## License and attribution

Code: MIT. Free Law Project marks the [bulk data](https://www.courtlistener.com/help/api/bulk-data/)
with a [Public Domain Mark](https://creativecommons.org/publicdomain/mark/1.0/) and says
it is free of known copyright restrictions. This is the source's public-domain status
statement, not a CC0 dedication added by this project. Database metadata and the hosted
card identify that source statement and link to it. Please credit CourtListener and
Free Law Project when using the data.
