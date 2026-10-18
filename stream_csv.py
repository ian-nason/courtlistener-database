"""Bounded record splitting for the PostgreSQL CSV exports used by CourtListener.

Records are retained byte-for-byte. DuckDB handles field parsing and escaping;
this module only locates newlines outside quoted fields for small load batches.
"""
import re

SPECIAL = re.compile(rb'["\\]')


def records(stream, *, escape='\\', max_record_bytes=8 * 1024**2):
    if escape not in ('\\', '"'):
        raise ValueError('Unsupported CSV escape convention')
    quoted = False
    parts, size = [], 0
    while True:
        line = stream.readline(max_record_bytes + 1)
        if not line:
            if quoted:
                raise ValueError('Unterminated quoted CSV record')
            if parts:
                yield b''.join(parts)
            return
        size += len(line)
        if size > max_record_bytes:
            raise ValueError(f'CSV record exceeds {max_record_bytes} bytes')
        parts.append(line)
        escaped, previous = False, -2
        for match in SPECIAL.finditer(line):
            pos, char = match.start(), match.group()
            if pos != previous + 1:
                escaped = False
            if escaped:
                escaped = False
            elif char == b'\\' and escape == '\\' and quoted:
                escaped = True
            elif char == b'"':
                quoted = not quoted
            previous = pos
        if not quoted:
            yield b''.join(parts)
            parts, size = [], 0


def chunks(stream, *, header, escape='\\', max_bytes=8 * 1024**2, max_rows=10000,
           max_record_bytes=8 * 1024**2):
    batch, size = [], len(header)
    for record in records(stream, escape=escape, max_record_bytes=max_record_bytes):
        if len(header) + len(record) > max_bytes:
            raise ValueError('CSV record plus header exceeds batch byte limit')
        if batch and (size + len(record) > max_bytes or len(batch) >= max_rows):
            yield header + b''.join(batch), len(batch)
            batch, size = [], len(header)
        batch.append(record)
        size += len(record)
    if batch:
        yield header + b''.join(batch), len(batch)
