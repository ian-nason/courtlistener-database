#!/usr/bin/env python3
"""Build courtlistener.duckdb from CourtListener's bulk data (Free Law Project).
Source: https://www.courtlistener.com/help/api/bulk-data/ (Free Law Project).
Loads pinned PostgreSQL CSV exports in bounded batches, including oral-argument
speech-to-text transcripts. Source schemas are checked explicitly; retired oral
columns are preserved for compatibility. See README.md for scope and caveats.
"""
from __future__ import annotations

import argparse
import bz2
import json
import re
import csv
import hashlib
import tempfile
import sys
import time
from pathlib import Path

from datapond_build import Checker, build_columns_table, ensure_metadata, export_dictionary
from datapond_build.session import connect
from stream_csv import chunks
from download_sources import sha256

RAW = Path("data/raw")
TMP = Path("data/tmp")
DEFAULT_OUTPUT = "courtlistener.duckdb"
SOURCE_URL = "https://www.courtlistener.com/help/api/bulk-data/"
MANIFEST_PATH = Path(__file__).resolve().parent / "docs/bulk_manifest.json"
MANIFEST = json.loads(MANIFEST_PATH.read_text())
LOAD_AUDIT = {}

# Verified against the pinned 2026-09-30 load script: this schema field is not
# included in the official originating-court CSV export.
SOURCE_SCHEMA_OMISSIONS = {"originating-court-information": {"date_rehearing_denied"}}
LEGACY_ORAL_COLUMNS = ["id", "date_created", "date_modified", "source", "case_name_short", "case_name", "case_name_full", "judges", "sha1", "download_url", "local_path_mp3", "local_path_original_file", "filepath_ia", "ia_upload_failure_count", "duration", "processing_complete", "date_blocked", "blocked", "stt_status", "stt_google_response", "docket_id"]


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
    "oral_arguments": "Oral-argument audio metadata and source-provided speech-to-text transcripts; transcription can contain errors",
    "opinion_cluster_panel": "Judge-to-opinion-cluster panel links (person_id joins judges; cluster ids refer to CourtListener opinion clusters, not included here)",
    "opinion_joined_by": "Judge-to-opinion 'joined by' links (person_id joins judges; opinion ids refer to CourtListener opinions, not included here)",
}
JOIN_HINTS = {
    "stt_google_response": "Retired upstream field; retained as NULL for compatibility. Use stt_transcript.",
    "stt_transcript": "Source speech-to-text transcript; may contain recognition errors",
    "person_id": "CourtListener person id; joins judges.id",
    "fjc_id": "Federal Judicial Center judge id (the directory's jid, not nid); joins fjc-judges.judges.jid for 3,710 of 3,711 judges",
    "court_id": "CourtListener court code; joins courts.id",
    "financial_disclosure_id": "Joins financial_disclosures.id",
    "school_id": "Joins schools.id",
    "position_id": "Joins positions.id",
    "race_id": "CourtListener race code id; decoded in judge_races.race",
}


def load_schema() -> dict[str, list[tuple[str, str]]]:
    sql = (RAW / MANIFEST["schema"]["file"]).read_text()
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
    entry = MANIFEST[kind]
    src = RAW / entry["file"]
    if src.stat().st_size != entry["size"]:
        raise ValueError(f"{kind}: source size differs from manifest")
    if "sha256" in entry:
        actual_hash = sha256(src)
        if actual_hash != entry["sha256"]:
            raise ValueError(f"{kind}: source checksum differs from manifest")
    escape = entry.get("escape", "\\" if entry["date"] >= "2025-01-01" else '"')
    types = dict(schema.get(pg_table, []))
    if not types:
        raise ValueError(f"{kind}: missing schema table {pg_table}")
    TMP.mkdir(parents=True, exist_ok=True)
    total, batches, raw_bytes = 0, 0, 0
    with bz2.open(src, "rb") as source:
        header_bytes = source.readline(65537)
        if len(header_bytes) > 65536 or not header_bytes.endswith(b"\n"):
            raise ValueError(f"{kind}: missing or oversized CSV header")
        header = next(csv.reader([header_bytes.decode("utf-8-sig").rstrip("\r\n")]))
        if len(header) != len(set(header)) or any(not re.fullmatch(r"[a-z_][a-z0-9_]*", c) for c in header):
            raise ValueError(f"{kind}: invalid or duplicate column names")
        missing = set(types) - set(header)
        if set(header) - set(types) or not missing <= SOURCE_SCHEMA_OMISSIONS.get(kind, set()):
            raise ValueError(f"{kind}: source/schema column mismatch: missing={sorted(set(types)-set(header))}, extra={sorted(set(header)-set(types))}")
        typed = {c: duck_type(types[c]) for c in header}
        output_columns = list(header)
        if table == "oral_arguments":
            if not (set(LEGACY_ORAL_COLUMNS) - set(header)) <= {"stt_google_response"}:
                raise ValueError("Unexpected oral-argument compatibility layout")
            typed["stt_google_response"] = "VARCHAR"
            output_columns = LEGACY_ORAL_COLUMNS + [c for c in header if c not in LEGACY_ORAL_COLUMNS]
        columns = ", ".join(f"'{c}': 'VARCHAR'" for c in header)
        con.execute(f"CREATE TABLE {table} (" + ", ".join(f'"{c}" {typed[c]}' for c in output_columns) + ")")
        for payload, expected_rows in chunks(source, header=header_bytes, escape=escape):
            with tempfile.NamedTemporaryFile(dir=TMP, prefix=table+"-", suffix=".csv", delete=False) as temporary:
                path = Path(temporary.name)
                temporary.write(payload)
            try:
                escaped_path = str(path).replace("'", "''")
                con.execute(f"CREATE OR REPLACE TEMP TABLE _raw AS SELECT * FROM read_csv('{escaped_path}', auto_detect=false, header=true, delim=',', quote='\"', escape='{escape}', new_line='\\n', columns={{{columns}}}, max_line_size=8388608, buffer_size=33554432, parallel=false)")
                actual_rows = con.execute("SELECT COUNT(*) FROM _raw").fetchone()[0]
                if actual_rows != expected_rows:
                    raise ValueError(f"{kind}: CSV record count differs ({expected_rows} vs {actual_rows})")
                invalid_exprs, checked = [], []
                for col in header:
                    typ = typed[col]
                    raw = f'NULLIF("{col}", \'\')'
                    if typ == "BOOLEAN":
                        invalid = f"{raw} NOT IN ('t','f')"
                    elif typ in ("INTEGER", "BIGINT"):
                        invalid = f"NOT regexp_full_match({raw}, '[+-]?[0-9]+') OR TRY_CAST({raw} AS {typ}) IS NULL"
                    elif typ in ("DOUBLE", "DATE", "TIMESTAMP"):
                        cast_type = "TIMESTAMPTZ" if typ == "TIMESTAMP" else typ
                        invalid = f"TRY_CAST({raw} AS {cast_type}) IS NULL"
                    else:
                        continue
                    checked.append(col)
                    invalid_exprs.append(f"COUNT(*) FILTER (WHERE {raw} IS NOT NULL AND ({invalid}))")
                bad = con.execute("SELECT " + ", ".join(invalid_exprs) + " FROM _raw").fetchone() if invalid_exprs else []
                failures = {col: count for col, count in zip(checked, bad) if count}
                if failures:
                    raise ValueError(f"{kind}: invalid typed values (including fractional or overflowing integers): {failures}")
                exprs = [cast(c, typed[c]) if c in header else f'NULL::{typed[c]} AS "{c}"' for c in output_columns]
                con.execute(f"INSERT INTO {table} SELECT {', '.join(exprs)} FROM _raw")
                con.execute("DROP TABLE _raw")
                con.execute("CHECKPOINT")
            finally:
                path.unlink(missing_ok=True)
            total += actual_rows
            batches += 1
            raw_bytes += len(payload) - len(header_bytes)
            if batches % 25 == 0:
                print(f"    {kind}: {total:,} records, {batches} batches, {raw_bytes / 1024**2:.1f} MiB source", flush=True)
    actual = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    if actual != total:
        raise ValueError(f"{kind}: final count mismatch")
    LOAD_AUDIT[kind] = {"table": table, "source_records": total, "table_rows": actual, "batches": batches, "uncompressed_bytes": raw_bytes + len(header_bytes), "escape": escape, "source_sha256": entry.get("sha256"), "typed_columns": typed, "schema_only_columns_not_exported": sorted(missing), "compatibility_null_columns": [c for c in output_columns if c not in header], "conversion_failures": 0}
    return actual


def run_validation(con) -> int:
    ck = Checker("Validation")
    ck.query(con, "judges > 10,000", "SELECT COUNT(*) FROM judges", lambda n: n > 10000, lambda n: f"{n:,}")
    ck.query(con, "judges.id unique", "SELECT COUNT(*) - COUNT(DISTINCT id) FROM judges", lambda n: n == 0, str)
    for table in ["originating_court_information", "oral_arguments"]:
        ck.query(con, table + ".id unique", f"SELECT COUNT(*) - COUNT(DISTINCT id) FROM {table}", lambda n: n == 0, str)
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
    global RAW, TMP, MANIFEST
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, default=Path(DEFAULT_OUTPUT))
    ap.add_argument("--raw-dir", type=Path, default=RAW)
    ap.add_argument("--temp-dir", type=Path, default=TMP)
    ap.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    ap.add_argument("--dictionary", type=Path, default=Path("DICTIONARY.md"))
    ap.add_argument("--audit", type=Path)
    a = ap.parse_args()
    RAW, TMP = a.raw_dir, a.temp_dir
    MANIFEST = json.loads(a.manifest.read_text())
    t0 = time.time()
    if a.output.exists() or Path(str(a.output) + ".wal").exists():
        raise FileExistsError(f"Refusing to overwrite existing database or WAL: {a.output}")
    if a.dictionary.exists() or (a.audit and a.audit.exists()):
        raise FileExistsError("Refusing to overwrite dictionary or audit")
    missing = [str(RAW / MANIFEST[k]["file"]) for k in ["schema", *KINDS] if k in MANIFEST and not (RAW / MANIFEST[k]["file"]).is_file()]
    if missing:
        raise FileNotFoundError("Missing sources: " + ", ".join(missing))
    schema = load_schema()
    spill = TMP / "duckdb-spill"
    spill.mkdir(parents=True, exist_ok=True)
    con = connect(":memory:", memory_limit="256MB", threads=1, temp_dir=spill)
    # Transcripts can be tens of KiB per row. Bound the native storage row group
    # as well as the input batch, so checkpointing cannot accumulate 122,880 rows.
    escaped_output = str(a.output.resolve()).replace("'", "''")
    con.execute(f"ATTACH '{escaped_output}' AS candidate (ROW_GROUP_SIZE 2048)")
    con.execute("USE candidate")
    con.execute("SET max_temp_directory_size = '128MiB'")
    con.execute("SET TimeZone = 'UTC'")
    counts = {}
    for kind in KINDS:
        if kind not in MANIFEST:
            print(f"  {kind}: not in the manifest, skipped")
            continue
        n = load(con, kind, schema)
        if n == 0:  # an empty source export is not published as an empty table
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
    ensure_metadata(con, descriptions=TABLE_DESCRIPTIONS, tables=list(counts), source_url=SOURCE_URL, license="Public Domain Mark / public records (CourtListener bulk data)", replace=True)
    build_columns_table(con, join_hints=JOIN_HINTS, tables=list(counts) + ["v_judge_positions"], column_batch=8)
    missing_stats = con.execute("SELECT COUNT(*) FROM _columns WHERE null_pct IS NULL").fetchone()[0]
    if missing_stats:
        raise RuntimeError(f"Dictionary statistics failed for {missing_stats} columns")
    export_dictionary(con, a.dictionary, title="courtlistener Data Dictionary",
                      intro=[f"Source: [CourtListener bulk data]({SOURCE_URL}) (Free Law Project), exports of "
                             + ", ".join(sorted({v['date'] for k, v in MANIFEST.items() if k in KINDS})) + ".",
                             "Column names and types are CourtListener's own (bulk schema.sql); see its API docs for field meanings.",
                             "`v_judge_positions` joins positions to judges and courts."],
                      style="registry", tables=list(counts) + ["v_judge_positions"])
    con.execute("CHECKPOINT")
    failures = run_validation(con)
    con.close()
    if a.audit:
        a.audit.write_text(json.dumps({"status": "validated" if not failures else "failed", "tables": LOAD_AUDIT, "validation_failures": failures}, indent=2))
    print(f"\nBUILD DONE in {time.time() - t0:.0f}s; " + ", ".join(f"{k} {v:,}" for k, v in counts.items()) + f"; {a.output.stat().st_size / 1024**2:.0f} MB")
    if failures:
        print(f"BUILD FAILED: {failures} check(s) failed -- do not publish this file")
        sys.exit(1)


if __name__ == "__main__":
    main()
