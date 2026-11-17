#!/usr/bin/env python3
"""Local-only MVKView source triage: IDP + Projects.7z + SQLite.

No network, no writes to private inputs, no original source upload.
Accepts three independent inputs and emits metadata/evidence only.
The IDR project has direct symbol records but not a fully decoded IDA DB.
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.util
import hashlib
import json
from pathlib import Path
import sqlite3
import struct

SOURCES = (
    'mvkform.dfm', '_Unit115.pas', '_Unit125.pas', '_Unit128.pas',
)
HANDLERS = {
    '00848E78': ('Tmvkform.bTaskConnectClick', '_Unit128.pas'),
    '00848E6C': ('Tmvkform.bTaskConfigIPClick', '_Unit128.pas'),
    '0084E914': ('Tmvkform.bWriteAdcClick', '_Unit128.pas'),
    '0084E988': ('Tmvkform.bWriteValuesClick', '_Unit128.pas'),
    '0084E020': ('Tmvkform.bWriteTableClick', '_Unit128.pas'),
    '0084DEC4': ('Tmvkform.mRate1Click', '_Unit128.pas'),
}


def archive_bytes(path: Path) -> dict[str, bytes]:
    name = ctypes.util.find_library('archive')
    if not name:
        raise RuntimeError('libarchive required locally to inspect Projects.7z')
    lib = ctypes.CDLL(name)
    lib.archive_read_new.restype = ctypes.c_void_p
    for attr in ('archive_read_support_filter_all',
                 'archive_read_support_format_all',
                 'archive_read_data_skip', 'archive_read_free'):
        getattr(lib, attr).argtypes = [ctypes.c_void_p]
    lib.archive_read_open_filename.argtypes = [
        ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t]
    lib.archive_read_next_header.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
    lib.archive_entry_pathname.argtypes = [ctypes.c_void_p]
    lib.archive_entry_pathname.restype = ctypes.c_char_p
    lib.archive_read_data.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
    lib.archive_read_data.restype = ctypes.c_ssize_t
    reader = lib.archive_read_new()
    if not reader:
        raise RuntimeError('Could not initialize libarchive')
    found: dict[str, bytes] = {}
    try:
        if lib.archive_read_support_filter_all(reader) < 0:
            raise RuntimeError('Archive filters unsupported')
        if lib.archive_read_support_format_all(reader) < 0:
            raise RuntimeError('7z format unsupported')
        if lib.archive_read_open_filename(reader, str(path).encode(), 65536):
            raise RuntimeError('Cannot read original 7z archive')
        while True:
            item = ctypes.c_void_p()
            status = lib.archive_read_next_header(reader, ctypes.byref(item))
            if status == 1:
                break
            if status < 0:
                raise RuntimeError('Corrupt 7z archive header')
            path_in_archive = lib.archive_entry_pathname(item).decode('utf-8')
            basename = path_in_archive.rsplit('/', 1)[-1]
            if path_in_archive == f'Projects/{basename}' and basename in SOURCES:
                if basename in found:
                    raise ValueError('Duplicated original archive source')
                chunks = []
                count = 0
                buffer = ctypes.create_string_buffer(65536)
                while True:
                    n = lib.archive_read_data(reader, buffer, len(buffer))
                    if n < 0:
                        raise RuntimeError('Corrupt 7z source bytes')
                    if n == 0:
                        break
                    count += n
                    if count > 16 * 1024 * 1024:
                        raise ValueError('Unexpectedly oversized Pascal/DFM')
                    chunks.append(ctypes.string_at(buffer, n))
                found[basename] = b''.join(chunks)
            else:
                lib.archive_read_data_skip(reader)
    finally:
        lib.archive_read_free(reader)
    if set(found) != set(SOURCES):
        raise ValueError('Missing Pascal/DFM from actual Projects.7z')
    return found


def verify(idp: Path, archive: Path, sqlite_path: Path) -> dict:
    for p in (idp, archive, sqlite_path):
        if not p.is_file() or p.is_symlink():
            raise ValueError('Original project source not found or unsafe')
    idp_bytes = idp.read_bytes()
    if not idp_bytes.startswith(b'IDR proj v.3') or len(idp_bytes) < 64:
        raise ValueError('Wrong original IDR binary header')
    version, entry, base, image_size, total_size, code_base, code_size = struct.unpack_from(
        '<7I', idp_bytes, 12)
    with sqlite3.connect(f'file:{sqlite_path}?mode=ro', uri=True) as db:
        if db.execute('PRAGMA quick_check(1)').fetchone()[0] != 'ok':
            raise ValueError('SQLite IDR index failed integrity')
        row = db.execute("SELECT value FROM meta WHERE key='idp_header'").fetchone()
        if row is None:
            raise ValueError('SQLite lacks matching original IDP provenance')
        header = json.loads(row[0])
        if (header.get('format') != 'IDR proj v.3'
                or header.get('delphi_version') != version
                or header.get('entry_point') != f'{entry:08X}'
                or header.get('image_base') != f'{base:08X}'
                or header.get('image_size') != image_size
                or header.get('total_size') != total_size
                or header.get('code_base') != f'{code_base:08X}'
                or header.get('code_size') != code_size
                or header.get('sha256') != hashlib.sha256(idp_bytes).hexdigest()
                or header.get('size_bytes') != len(idp_bytes)):
            raise ValueError('IDP binary and SQLite embedded header mismatch')
        pas = archive_bytes(archive)
        for source_name, source in pas.items():
            row = db.execute('SELECT bytes,sha256 FROM source_files WHERE path=?',
                             (source_name,)).fetchone()
            digest = hashlib.sha256(source).hexdigest()
            if row != (len(source), digest):
                raise ValueError('Archive Pascal/DFM disagrees with SQLite source index')
        result = {}
        for addr, (name, file) in HANDLERS.items():
            marker = f'#{addr} {name}'.encode('ascii')
            if marker not in idp_bytes:
                raise ValueError('IDP is missing expected handler symbol')
            row = db.execute('SELECT name,source_file,line FROM functions WHERE address=?',
                             (addr,)).fetchone()
            if not row or row[:2] != (name, file) or type(row[2]) is not int:
                raise ValueError('SQLite IDR function does not match binary symbol')
            if f'//{addr}'.encode() not in pas[file]:
                raise ValueError('Original archive PAS missing function address')
            if name.startswith('Tmvkform.b'):
                event = db.execute('SELECT handler_address FROM events WHERE handler_name=?',
                                   (name.split('.', 1)[1],)).fetchone()
                if event != (addr,):
                    raise ValueError('DFM event and binary handler address disagree')
            result[name] = addr
        # Type-layout records inside IDP contain these TMVKThread boolean
        # offsets; the archive Pascal instruction bodies independently use
        # the same offsets rather than merely repeating function names.
        field_markers = {
            'TMVKThread.WriteData': (b'\xce\x00\x04\x00\x09WriteData', b'+400CE'),
            'TMVKThread.WriteValues': (b'\xcf\x00\x04\x00\x0bWriteValues', b'+400CF'),
        }
        for field_name, (binary_marker, source_marker) in field_markers.items():
            if (binary_marker not in idp_bytes or
                    source_marker not in pas['_Unit128.pas']):
                raise ValueError('Original IDP field offset and Pascal disagree')
        return {
            'original_thread_write_field_offsets_verified': {
                'TMVKThread.WriteData': '0x400CE',
                'TMVKThread.WriteValues': '0x400CF',
            },
            'triple_source_verification': True,
            'idp_header_and_hash_verified': True,
            'archive_pascal_and_dfm_sha256_match_sqlite': True,
            'source_file_count_verified': len(pas),
            'handler_idp_sqlite_pas_event_links_verified': result,
            'sqlite_integrity': 'ok',
            'private_file_bytes_exported': False,
            'full_original_delphi_parity_verified': False,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--idp', type=Path, required=True)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--sqlite', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.idp, args.archive, args.sqlite),
                     ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
