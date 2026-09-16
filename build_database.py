#!/usr/bin/env python3
"""Build courtlistener.duckdb from CourtListener's bulk data (Free Law Project).
Source: https://www.courtlistener.com/help/api/bulk-data/ -- PostgreSQL COPY exports of the
judge database (people, positions, education, political affiliations, retention events),
courts, and the federal judicial financial disclosures, plus oral-argument metadata and the
judge-to-opinion panel links. The docket/opinion/citation exports have been 14-byte stubs
since March 2024 and are not loaded. Run ./download_data.sh first (docs/bulk_manifest.json).

Types come from the bulk schema.sql: each CSV's header is matched to the schema table with
the same column set, so a column is INTEGER/DOUBLE/BOOLEAN/DATE/TIMESTAMP exactly as in
CourtListener's database; PostgreSQL's t/f booleans and empty NULLs are converted.
"""
from __future__ import annotations

import argparse
import bz2
import json
import re
import shutil
import sys
import time
from pathlib import Path

from datapond_build import Checker, build_columns_table, ensure_metadata, export_dictionary
from datapond_build.session import connect

RAW = Path("data/raw")
TMP = Path("data/tmp")
DEFAULT_OUTPUT = "courtlistener.duckdb"
SOURCE_URL = "https://www.courtlistener.com/help/api/bulk-data/"
MANIFEST = json.load(open("docs/bulk_manifest.json"))

# bulk file kind -> (table here, schema table for types; None = infer)
KINDS = {
    "people-db-people": ("judges", "people_db_person"),
    "people-db-positions": ("positions", "people_db_position"),
    "people-db-educations": ("educations", "people_db_education"),
    "people-db-schools": ("schools", "people_db_school"),
    "people-db-political-affiliations": ("political_affiliations", "people_db_politicalaffiliation"),
    "people-db-races": ("judge_races", "people_db_person_race"),
    "people-db-retention-events": ("retention_events", "people_db_retentionevent"),
    "courts": ("courts", "search_court"),
    "courthouses": ("courthouses", "search_courthouse"),
    "originating-court-information": ("originating_court_information", "search_originatingcourtinformation"),
    "financial-disclosures": ("financial_disclosures", "disclosures_financialdisclosure"),
    "financial-disclosures-agreements": ("disclosure_agreements", "disclosures_agreement"),
    "financial-disclosures-debts": ("disclosure_debts", "disclosures_debt"),
    "financial-disclosures-gifts": ("disclosure_gifts", "disclosures_gift"),
    "financial-disclosures-non-investment-income": ("disclosure_non_investment_income", "disclosures_noninvestmentincome"),
    "financial-disclosures-positions": ("disclosure_positions", "disclosures_position"),
    "financial-disclosures-reimbursements": ("disclosure_reimbursements", "disclosures_reimbursement"),
    "financial-disclosures-spousal-income": ("disclosure_spousal_income", "disclosures_spouseincome"),
    "oral-arguments": ("oral_arguments", "audio_audio"),
    "search_opinioncluster_panel": ("opinion_cluster_panel", "search_opinioncluster_panel"),
    "search_opinion_joined_by": ("opinion_joined_by", "search_opinion_joined_by"),
}
# CourtListener's race codes (people_db.models.Race) for judge_races.race_id
RACES = {1: ("w", "White"), 2: ("b", "Black or African American"), 3: ("i", "American Indian or Alaska Native"), 4: ("a", "Asian"),
         5: ("p", "Native Hawaiian or Other Pacific Islander"), 6: ("h", "Hispanic/Latino"), 7: ("mena", "Middle Eastern/North African"), 8: ("o", "Other")}

TABLE_DESCRIPTIONS = {
    "judges": "One row per person in CourtListener's judge database (federal and state judges, plus some other public figures): names, "
              "birth/death, gender, religion, FJC judge id (fjc_id joins fjc-judges.judges.jid)",
    "positions": "One row per position held: judgeships (court_id joins courts), clerkships, offices and other jobs, with nomination, "
                 "confirmation, start and termination dates, appointer, predecessor and how the seat was obtained",
    "educations": "One row per degree (school_id joins schools)",
    "schools": "Law schools and universities",
    "political_affiliations": "One row per recorded party affiliation with its source and dates",
    "judge_races": "Person-to-race links (race_id decoded in the race column)",
    "retention_events": "One row per retention election or reappointment for a position",
    "courts": "Every court CourtListener tracks (federal, state, tribal, special), with jurisdiction, PACER and FJC ids, dates and parent court",
    "courthouses": "Courthouse addresses per court",
    "originating_court_information": "Lower-court information for appellate dockets (judges, dates, docket numbers)",
    "financial_disclosures": "One row per federal judicial financial disclosure report (person_id joins judges): year, report type, "
                             "amendment flag, page count and the original PDF's storage path",
    "disclosure_agreements": "Agreements reported on a disclosure (financial_disclosure_id joins financial_disclosures)",
    "disclosure_debts": "Liabilities reported on a disclosure, with value code",
    "disclosure_gifts": "Gifts reported on a disclosure",
    "disclosure_non_investment_income": "Non-investment income (teaching, book royalties ...) reported on a disclosure",
    "disclosure_positions": "Outside positions reported on a disclosure",
    "disclosure_reimbursements": "Travel reimbursements reported on a disclosure",
    "disclosure_spousal_income": "Spousal income reported on a disclosure",
    "oral_arguments": "Oral-argument audio metadata (case name, docket, court, date, duration); the 2024-05-06 export",
    "opinion_cluster_panel": "Judge-to-opinion-cluster panel links (person_id joins judges; cluster ids refer to CourtListener opinion clusters, not included here)",
    "opinion_joined_by": "Judge-to-opinion 'joined by' links (person_id joins judges; opinion ids refer to CourtListener opinions, not included here)",
}
JOIN_HINTS = {
    "person_id": "CourtListener person id; joins judges.id",
    "fjc_id": "Federal Judicial Center judge id (the directory's jid, not nid); joins fjc-judges.judges.jid for 3,710 of 3,711 judges",
    "court_id": "CourtListener court code; joins courts.id",
    "financial_disclosure_id": "Joins financial_disclosures.id",
    "school_id": "Joins schools.id",
    "position_id": "Joins positions.id",
    "race_id": "CourtListener race code id; decoded in judge_races.race",
}


def load_schema() -> dict[str, list[tuple[str, str]]]:
    sql = next(RAW.glob("schema-*.sql")).read_text()
    tables = {}
    for m in re.finditer(r"CREATE TABLE public\.(\w+) \((.*?)\n\);", sql, flags=re.S):
        cols = []
        for line in m.group(2).splitlines():
            line = line.strip().rstrip(",")
            cm = re.match(r'^"?(\w+)"?\s+(.+?)(?:\s+DEFAULT .*|\s+NOT NULL.*)?$', line)
            if cm and not line.startswith("CONSTRAINT"):
                cols.append((cm.group(1), cm.group(2).strip()))
        tables[m.group(1)] = cols
    return tables


def duck_type(pg: str) -> str:
    pg = re.sub(r"\(.*\)", "", pg).strip()
    return {"integer": "INTEGER", "smallint": "INTEGER", "bigint": "BIGINT", "double precision": "DOUBLE", "numeric": "DOUBLE",
            "boolean": "BOOLEAN", "date": "DATE", "timestamp with time zone": "TIMESTAMP", "timestamp without time zone": "TIMESTAMP",
            "text": "VARCHAR", "character varying": "VARCHAR", "jsonb": "VARCHAR"}.get(pg, "VARCHAR")


def cast(col: str, typ: str) -> str:
    raw = f'NULLIF("{col}", \'\')'
    if typ == "BOOLEAN":
        return f"CASE {raw} WHEN 't' THEN TRUE WHEN 'f' THEN FALSE END AS \"{col}\""
    if typ == "TIMESTAMP":
        return f"TRY_CAST({raw} AS TIMESTAMPTZ)::TIMESTAMP AS \"{col}\""
    if typ in ("INTEGER", "BIGINT", "DOUBLE", "DATE"):
        return f"TRY_CAST({raw} AS {typ}) AS \"{col}\""
    return f"{raw} AS \"{col}\""


def load(con, kind: str, schema: dict) -> int:
    table, pg_table = KINDS[kind]
    src = RAW / MANIFEST[kind]["file"]
    TMP.mkdir(parents=True, exist_ok=True)
    csv = TMP / src.name.replace(".bz2", "")
    with bz2.open(src, "rb") as fi, open(csv, "wb") as fo:
        shutil.copyfileobj(fi, fo)
    # PostgreSQL COPY ... (FORMAT csv, ESCAPE '\\'): every field quoted, an unquoted empty
    # field is NULL, embedded quotes are backslash-escaped. The sniffer trips on the
    # backslash escapes, so the dialect and the header's columns are given explicitly.
    with open(csv, encoding="utf-8") as fh:
        header = fh.readline().rstrip("\n").split(",")
    columns = ", ".join(f"'{c}': 'VARCHAR'" for c in header)
    # the 2025 exports escape quotes with a backslash; the older oral-arguments export doubles them
    for escape in ("\\", '"'):
        try:
            con.execute(f"CREATE OR REPLACE TABLE _raw AS SELECT * FROM read_csv('{csv}', auto_detect=false, header=true, delim=',', "
                        f"quote='\"', escape='{escape}', new_line='\\n', columns={{{columns}}}, max_line_size=8388608)")
            break
        except Exception as e:  # noqa: BLE001 - try the other escape convention
            last = e
    else:
        raise last
    types = dict(schema.get(pg_table, []))
    if types and set(types) != set(header):
        print(f"    note: {kind} header differs from schema table {pg_table} (older export); typing the common columns")
    exprs = [cast(c, duck_type(types[c]) if c in types else "VARCHAR") for c in header]
    con.execute(f"CREATE TABLE {table} AS SELECT {', '.join(exprs)} FROM _raw")
    con.execute("DROP TABLE _raw")
    csv.unlink()
    return con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def run_validation(con) -> int:
    ck = Checker("Validation")
    ck.query(con, "judges > 10,000", "SELECT COUNT(*) FROM judges", lambda n: n > 10000, lambda n: f"{n:,}")
    ck.query(con, "judges.id unique", "SELECT COUNT(*) - COUNT(DISTINCT id) FROM judges", lambda n: n == 0, str)
    ck.query(con, "positions > 15,000", "SELECT COUNT(*) FROM positions", lambda n: n > 15000, lambda n: f"{n:,}")
    ck.query(con, "every position has a judge", "SELECT COUNT(*) FROM positions p LEFT JOIN judges j ON j.id = p.person_id WHERE j.id IS NULL", lambda n: n == 0, str)
    ck.query(con, "judgeship court ids exist in courts (> 99%)",
             "SELECT COUNT(*) FILTER (WHERE c.id IS NOT NULL) * 1.0 / COUNT(*) FROM positions p LEFT JOIN courts c ON c.id = p.court_id WHERE p.court_id IS NOT NULL",
             lambda v: v > 0.99, lambda v: f"{v:.2%}")
    ck.query(con, "financial disclosures > 20,000", "SELECT COUNT(*) FROM financial_disclosures", lambda n: n > 20000, lambda n: f"{n:,}")
    ck.query(con, "every disclosure has a judge", "SELECT COUNT(*) FROM financial_disclosures d LEFT JOIN judges j ON j.id = d.person_id WHERE j.id IS NULL", lambda n: n == 0, str)
    ck.query(con, "disclosure years plausible (from the 1980s, through 2022 or later)", "SELECT MIN(year) || '-' || MAX(year) FROM financial_disclosures",
             lambda s: s[:4] >= "1980" and s[-4:] >= "2022", str)
    ck.query(con, "every gift row joins a disclosure",
             "SELECT COUNT(*) FROM disclosure_gifts g LEFT JOIN financial_disclosures d ON d.id = g.financial_disclosure_id WHERE d.id IS NULL", lambda n: n == 0, str)
    ck.query(con, "judges with an FJC id > 3,000", "SELECT COUNT(fjc_id) FROM judges", lambda n: n > 3000, lambda n: f"{n:,}")
    ck.query(con, "courts > 1,500", "SELECT COUNT(*) FROM courts", lambda n: n > 1500, lambda n: f"{n:,}")
    ck.query(con, "positions.date_start typed DATE", "SELECT data_type FROM information_schema.columns WHERE table_name = 'positions' AND column_name = 'date_start'", lambda t: t == "DATE", str)
    ck.query(con, "v_judge_positions runs", "SELECT COUNT(*) FROM v_judge_positions", lambda n: n > 10000, lambda n: f"{n:,}")
    return ck.report()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, default=Path(DEFAULT_OUTPUT))
    a = ap.parse_args()
    t0 = time.time()
    schema = load_schema()
    con = connect(a.output, fresh=True, memory_limit="2GB", threads=2)
    counts = {}
    for kind in KINDS:
        if kind not in MANIFEST:
            print(f"  {kind}: not in the manifest, skipped")
            continue
        n = load(con, kind, schema)
        if n == 0:  # an empty export (retention events in 2025-01-31) is not published as an empty table
            print(f"  {KINDS[kind][0]}: empty export, table dropped")
            con.execute(f"DROP TABLE {KINDS[kind][0]}")
            continue
        counts[KINDS[kind][0]] = n
        print(f"  {KINDS[kind][0]}: {n:,} rows")
    con.execute("ALTER TABLE judge_races ADD COLUMN race VARCHAR")
    for rid, (code, label) in RACES.items():
        con.execute("UPDATE judge_races SET race = ? WHERE race_id = ?", [label, rid])
    con.execute("""
        CREATE VIEW v_judge_positions AS
        SELECT j.id AS person_id, j.name_first, j.name_middle, j.name_last, j.name_suffix, j.date_dob, j.gender, j.fjc_id,
               p.id AS position_id, p.position_type, p.job_title, p.court_id, c.full_name AS court_name, c.jurisdiction AS court_jurisdiction,
               p.appointer_id, p.how_selected, p.date_nominated, p.date_confirmation, p.date_start, p.date_termination, p.termination_reason
        FROM positions p JOIN judges j ON j.id = p.person_id LEFT JOIN courts c ON c.id = p.court_id""")
    print("\nMetadata + dictionary")
    ensure_metadata(con, descriptions=TABLE_DESCRIPTIONS, tables=list(counts), source_url=SOURCE_URL, license="CC0 / public records (CourtListener bulk data)", replace=True)
    build_columns_table(con, join_hints=JOIN_HINTS, tables=list(counts) + ["v_judge_positions"])
    export_dictionary(con, Path("DICTIONARY.md"), title="courtlistener Data Dictionary",
                      intro=[f"Source: [CourtListener bulk data]({SOURCE_URL}) (Free Law Project), exports of "
                             + ", ".join(sorted({v['date'] for k, v in MANIFEST.items() if k in KINDS})) + ".",
                             "Column names and types are CourtListener's own (bulk schema.sql); see its API docs for field meanings.",
                             "`v_judge_positions` joins positions to judges and courts."],
                      style="registry", tables=list(counts) + ["v_judge_positions"])
    con.execute("CHECKPOINT")
    failures = run_validation(con)
    con.close()
    print(f"\nBUILD DONE in {time.time() - t0:.0f}s; " + ", ".join(f"{k} {v:,}" for k, v in counts.items()) + f"; {a.output.stat().st_size / 1024**2:.0f} MB")
    if failures:
        print(f"BUILD FAILED: {failures} check(s) failed -- do not publish this file")
        sys.exit(1)


if __name__ == "__main__":
    main()
