"""Atomically publish a validated CourtListener candidate; resume verification safely."""
import argparse
import dataclasses
import datetime
import hashlib
import json
import os
import pathlib
import re

import duckdb
import yaml

os.environ.setdefault('HF_HUB_DISABLE_XET', '1')
from huggingface_hub import HfApi, CommitOperationAdd
from datapond_build.publish import CardSpec

CONFIG = {'memory_limit': '128MB', 'threads': '1', 'max_temp_directory_size': '0B'}
EXPECTED_REPO = 'Nason/courtlistener-database'
EXPECTED_FILE = 'courtlistener.duckdb'


def checksum(path):
    digest = hashlib.sha256()
    with pathlib.Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024**2), b''):
            digest.update(chunk)
    return digest.hexdigest()


def validation_report(document):
    report = document.get('validation', document)
    required = {'status', 'sha256', 'bytes', 'counts', 'schemas', 'queries', 'dates'}
    if not isinstance(report, dict) or not required <= report.keys():
        raise ValueError('Validation requires status, sha256, bytes, counts, schemas, queries and dates')
    if report['status'] != 'validated' or not re.fullmatch(r'[0-9a-f]{64}', report['sha256']):
        raise ValueError('Candidate is not validated')
    if not isinstance(report['bytes'], int) or report['bytes'] <= 0 or not report['counts']:
        raise ValueError('Invalid validation size or table counts')
    for table, count in report['counts'].items():
        if not re.fullmatch(r'[a-z_]+', table) or not isinstance(count.get('new'), int) or count['new'] < 0:
            raise ValueError('Invalid validated table count')
    if set(report['schemas']) != set(report['counts']):
        raise ValueError('Validation schema/table sets differ')
    return report


def remote_identity(api, spec, revision, size, sha):
    paths = api.get_paths_info(spec.repo, [spec.file], repo_type='dataset', revision=revision)
    if len(paths) != 1 or paths[0].size != size:
        raise RuntimeError('Remote artifact size mismatch')
    info = paths[0]
    if info.lfs is None or info.lfs.sha256 != sha:
        raise RuntimeError('Remote LFS artifact hash mismatch')
    return 'lfs-sha256'


def check_tables(con, alias, report):
    tables = con.execute(f'SELECT table_name,row_count FROM {alias}._metadata ORDER BY table_name').fetchall()
    expected = {t: item['new'] for t, item in report['counts'].items()}
    if dict(tables) != expected:
        raise RuntimeError('Metadata differs from validated counts')
    actual = {t: con.execute(f'SELECT COUNT(*) FROM {alias}."{t}"').fetchone()[0] for t, _ in tables}
    if actual != expected:
        raise RuntimeError('Actual counts differ from validation')
    for table, schema in report['schemas'].items():
        columns = [(x[0], x[1]) for x in con.execute(f'DESCRIBE {alias}."{table}"').fetchall()]
        if columns != [tuple(x) for x in schema['columns']]:
            raise RuntimeError('Full schema differs from validation')
    if con.execute(f'SELECT DISTINCT license FROM {alias}._metadata').fetchall() != [('Public Domain Mark / public records (CourtListener bulk data)',)]:
        raise RuntimeError('License metadata differs from authoritative source label')
    judges = con.execute(f'SELECT COUNT(*),COUNT(fjc_id) FROM {alias}.judges').fetchone()
    if list(judges) != report['queries']['judges']:
        raise RuntimeError('Judge identifiers differ from validation')
    disclosure_years = con.execute(f'SELECT MIN(year),MAX(year) FROM {alias}.financial_disclosures').fetchone()
    if list(disclosure_years) != report['dates']['disclosure_years']:
        raise RuntimeError('Disclosure coverage differs from validation')
    return tables, actual


def render_card(spec, rows, report, snapshot):
    front = {'license': spec.license, 'license_name': spec.license_name,
             'license_link': spec.license_link, 'tags': spec.tags,
             'pretty_name': spec.pretty_name, 'size_categories': [spec.size_category]}
    table = '\n'.join(f'| `{name}` | {description} | {count:,} | {columns} |'
                      for name, description, count, columns in rows)
    url = f'https://huggingface.co/datasets/{spec.repo}/resolve/main/{spec.file}'
    return ('---\n' + yaml.safe_dump(front, sort_keys=False) + '---\n\n'
            + f'# {spec.title or spec.pretty_name}\n\n{spec.intro.strip()}\n\n'
            + f'**{sum(x["new"] for x in report["counts"].values()):,} rows across {len(rows)} tables.** '
            + f'Source snapshot: {snapshot}. Database: {report["bytes"]:,} bytes.\n\n'
            + '| Table | Description | Rows | Columns |\n|---|---|---:|---:|\n' + table
            + '\n\n## Query it remotely\n\n```sql\nINSTALL httpfs; LOAD httpfs;\n'
            + f"ATTACH '{url}' AS {spec.alias} (READ_ONLY);\n\n{spec.quick_start_sql.strip()}\n```\n\n"
            + 'Python: `pip install datapond`. R: `install.packages("datapond")` '
            + '([CRAN](https://cran.r-project.org/package=datapond)).\n\n'
            + spec.footer.strip() + '\n')


def verify_remote(api, spec, revision, report):
    verified = {}
    con = duckdb.connect(config=CONFIG)
    try:
        con.execute('LOAD httpfs')
        for ref in [revision, 'main']:
            identity = remote_identity(api, spec, ref, report['bytes'], report['sha256'])
            url = f'https://huggingface.co/datasets/{spec.repo}/resolve/{ref}/{spec.file}'
            con.execute(f"ATTACH '{url}' AS {spec.alias} (READ_ONLY)")
            tables, actual = check_tables(con, spec.alias, report)
            example = con.execute(spec.quick_start_sql).fetchall()
            if not example:
                raise RuntimeError('Remote card example returned no rows')
            verified[ref] = {'identity': identity, 'tables': tables, 'actual_counts': actual,
                             'example_rows': len(example)}
            con.execute(f'DETACH {spec.alias}')
        if api.repo_info(spec.repo, repo_type='dataset').sha != revision:
            raise RuntimeError('Main head changed during verification')
    finally:
        con.close()
    return verified


def save_receipt(path, receipt):
    temporary = path.with_suffix('.new')
    temporary.write_text(json.dumps(receipt, indent=2, default=str))
    temporary.replace(path)


def main():
    p = argparse.ArgumentParser()
    for option in ['db', 'provenance', 'dictionary', 'receipt']:
        p.add_argument('--' + option, type=pathlib.Path, required=True)
    p.add_argument('--expected-parent')
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--verify-only', action='store_true')
    p.add_argument('--commit')
    a = p.parse_args()
    if pathlib.Path(str(a.db) + '.wal').exists():
        raise RuntimeError('Candidate has a WAL; complete and verify its checkpoint before publication')
    if a.verify_only:
        if a.dry_run or not a.commit or not re.fullmatch(r'[0-9a-f]{40}', a.commit):
            p.error('--verify-only requires a full --commit and cannot combine with --dry-run')
    elif not a.expected_parent or not re.fullmatch(r'[0-9a-f]{40}', a.expected_parent):
        p.error('Upload/dry-run requires a full --expected-parent')
    elif a.receipt.exists():
        raise FileExistsError('Receipt already exists; inspect it and use --verify-only after upload')
    repo = pathlib.Path(__file__).resolve().parent
    card_data = yaml.safe_load((repo / 'card.yaml').read_text())
    fields = {field.name for field in dataclasses.fields(CardSpec)}
    if set(card_data) - fields:
        raise ValueError('Unsupported card fields')
    spec = CardSpec(**card_data)
    if spec.repo != EXPECTED_REPO or spec.file != EXPECTED_FILE or spec.alias != 'cl':
        raise RuntimeError('Unexpected publication destination or alias')
    provenance = json.loads(a.provenance.read_text())
    snapshot = datetime.date.fromisoformat(provenance['source_snapshot']).isoformat()
    report = validation_report(provenance)
    sha, size = checksum(a.db), a.db.stat().st_size
    if report['sha256'] != sha or report['bytes'] != size:
        raise RuntimeError('Candidate differs from validated provenance')
    if checksum(a.dictionary) != provenance['dictionary_sha256']:
        raise RuntimeError('Dictionary differs from validated build')
    if 'stt_transcript' not in a.dictionary.read_text():
        raise RuntimeError('Dictionary lacks transcript columns')
    con = duckdb.connect(config=CONFIG)
    try:
        path = str(a.db.resolve()).replace("'", "''")
        con.execute(f"ATTACH '{path}' AS cl (READ_ONLY)")
        tables, _ = check_tables(con, 'cl', report)
        example = con.execute(spec.quick_start_sql).fetchall()
        if not example:
            raise RuntimeError('Local card example returned no rows')
        rows = con.execute('SELECT table_name,description,row_count,column_count FROM cl._metadata ORDER BY row_count DESC,table_name').fetchall()
    finally:
        con.close()
    card = render_card(spec, rows, report, snapshot)
    front = yaml.safe_load(card.split('---', 2)[1])
    if front.get('license_name') != 'public-domain' or front.get('license_link') != 'https://www.courtlistener.com/help/api/bulk-data/':
        raise RuntimeError('Card lacks authoritative public-domain details')
    a.receipt.with_suffix('.README.md').write_text(card)
    api = HfApi()
    if a.verify_only:
        receipt = {'repo': spec.repo, 'commit': a.commit, 'sha256': sha, 'bytes': size,
                   'url': f'https://huggingface.co/datasets/{spec.repo}/commit/{a.commit}',
                   'previous_commit': provenance['previous_artifact']['commit'],
                   'status': 'uploaded_pending_verification'}
        if a.receipt.exists():
            saved = json.loads(a.receipt.read_text())
            if saved.get('commit') != a.commit or saved.get('sha256') != sha or saved.get('repo') != spec.repo:
                raise RuntimeError('Receipt belongs to another artifact or commit')
            receipt.update(saved)
    else:
        current = api.repo_info(spec.repo, repo_type='dataset')
        if current.sha != a.expected_parent:
            raise RuntimeError('Published head changed; inspect before retrying')
        previous = api.get_paths_info(spec.repo, [spec.file], repo_type='dataset', revision=current.sha)
        if len(previous) != 1 or previous[0].lfs is None:
            raise RuntimeError('Existing destination is not an LFS artifact')
        print(json.dumps({'destination': spec.repo, 'bytes': size, 'sha256': sha, 'parent': current.sha,
                          'tables': tables, 'example_rows': len(example), 'dry_run': a.dry_run}), flush=True)
        if a.dry_run:
            return
        operations = [CommitOperationAdd(path_in_repo=spec.file, path_or_fileobj=str(a.db)),
                      CommitOperationAdd(path_in_repo='README.md', path_or_fileobj=card.encode()),
                      CommitOperationAdd(path_in_repo=f'sources-{snapshot}.json', path_or_fileobj=str(a.provenance)),
                      CommitOperationAdd(path_in_repo='DICTIONARY.md', path_or_fileobj=str(a.dictionary))]
        commit = api.create_commit(repo_id=spec.repo, repo_type='dataset', parent_commit=a.expected_parent,
                                   num_threads=1, operations=operations,
                                   commit_message=f'Refresh CourtListener snapshot {snapshot}; bounded transcript ingestion')
        receipt = {'repo': spec.repo, 'commit': commit.oid, 'url': commit.commit_url, 'sha256': sha,
                   'bytes': size, 'status': 'uploaded_pending_verification', 'previous_commit': a.expected_parent}
        save_receipt(a.receipt, receipt)
        print(json.dumps(receipt), flush=True)
    receipt.update(status='verified', remote_checks=verify_remote(api, spec, receipt['commit'], report))
    save_receipt(a.receipt, receipt)
    print(json.dumps(receipt, indent=2), flush=True)


if __name__ == '__main__':
    main()
