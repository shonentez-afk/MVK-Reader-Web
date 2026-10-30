"""Stage111R: independent offline integrity receipt for a CircleCI Windows EXE.

Checks the actual PE executable, SHA256SUMS and BUILD_INFO after PyInstaller.
No network or protected measurement data are accessed or committed.
The result proves build-time consistency, NOT original MVKView parity or that
an independently downloaded artifact has the same bytes.
"""
from __future__ import annotations
import argparse
import hashlib
import hmac
import json
from pathlib import Path
import re
import sys

EXE_NAME = 'MVKViewCompatible_Stage111_PREVIEW.exe'
SHA_NAME = 'SHA256SUMS.txt'
INFO_NAME = 'BUILD_INFO.txt'
RECEIPT_NAME = 'BUILD_VERIFICATION.json'
SHA_RE = re.compile(r'[0-9a-fA-F]{40}\Z')
HASH_LINE = re.compile(r'([0-9a-fA-F]{64})  MVKViewCompatible_Stage111_PREVIEW\.exe\Z')
BRANCH = 'research/stage111-mvkview-desktop-20261029'
MAX_BYTES = 2 * 1024**3


def _plain_file(folder: Path, name: str) -> Path:
    p = folder / name
    if p.is_symlink() or not p.is_file() or p.stat().st_size == 0:
        raise ValueError(f'Missing or invalid regular artifact: {name}')
    if p.resolve().parent != folder.resolve():
        raise ValueError('Artifact must stay inside selected dist directory')
    return p


def verify_preview(dist: str | Path, *, expected_commit: str,
                   expected_branch: str = BRANCH) -> dict:
    """Re-read all three files independently and validate the PE header."""
    if not isinstance(expected_commit, str) or not SHA_RE.fullmatch(expected_commit):
        raise ValueError('Expected commit must be an exact 40-hex Git SHA')
    if expected_branch != BRANCH:
        raise ValueError('Preview branch must be the isolated research branch')
    folder = Path(dist)
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError('Dist must be a real local directory')
    exe = _plain_file(folder, EXE_NAME)
    sha_file = _plain_file(folder, SHA_NAME)
    info_file = _plain_file(folder, INFO_NAME)
    if exe.stat().st_size > MAX_BYTES or sha_file.stat().st_size > 256 or info_file.stat().st_size > 256:
        raise ValueError('Artifact or manifest exceeds safety limits')
    try:
        sha_line = sha_file.read_text(encoding='ascii').strip('\r\n')
        metadata = info_file.read_text(encoding='ascii').splitlines()
    except UnicodeError as exc:
        raise ValueError('Manifest must be ASCII') from exc
    match = HASH_LINE.fullmatch(sha_line)
    if not match:
        raise ValueError('SHA256SUMS manifest must contain exact EXE name and SHA256')
    if len(metadata) != 2 or not metadata[0].startswith('commit=') or not metadata[1].startswith('branch='):
        raise ValueError('BUILD_INFO must contain commit and branch in exact order')
    actual_commit = metadata[0].removeprefix('commit=')
    actual_branch = metadata[1].removeprefix('branch=')
    if actual_commit.lower() != expected_commit.lower() or actual_branch != expected_branch:
        raise ValueError('EXE BUILD_INFO commit/branch mismatch')
    with exe.open('rb') as stream:
        header = stream.read(64)
        if len(header) < 64 or header[:2] != b'MZ':
            raise ValueError('Expected Windows Portable Executable MZ header')
        pe_offset = int.from_bytes(header[0x3c:0x40], 'little')
        if not 64 <= pe_offset <= min(4096, exe.stat().st_size-4):
            raise ValueError('Invalid PE header offset')
        stream.seek(pe_offset)
        if stream.read(4) != b'PE\0\0':
            raise ValueError('Missing Windows PE signature')
    h = hashlib.sha256()
    with exe.open('rb') as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(data)
    checksum = h.hexdigest()
    if not hmac.compare_digest(checksum, match.group(1).lower()):
        raise ValueError('SHA256SUMS does not match actual EXE bytes')
    return {
        'source': 'STAGE111R_LOCAL_WINDOWS_PREVIEW_BUILD_INTEGRITY',
        'file': EXE_NAME,
        'sha256': checksum,
        'size_bytes': exe.stat().st_size,
        'source_commit': actual_commit,
        'source_branch': actual_branch,
        'pe_header_verified': True,
        'build_manifest_verified': True,
        'sha256_actual_exe_matches_manifest': True,
        'separate_download_integrity_verified': False,
        'original_delphi_compatibility_verified': False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Offline CircleCI Windows preview verification')
    parser.add_argument('--dist', required=True)
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--expected-branch', default=BRANCH)
    parser.add_argument('--receipt-json')
    args = parser.parse_args(argv)
    try:
        result = verify_preview(args.dist, expected_commit=args.expected_commit,
                                expected_branch=args.expected_branch)
        receipt = json.dumps(result, ensure_ascii=False, indent=2)
        if args.receipt_json is not None:
            target = Path(args.receipt_json)
            if (target.name != RECEIPT_NAME or target.parent.resolve() != Path(args.dist).resolve()
                    or target.is_symlink()):
                raise ValueError('Receipt must be inside dist under the fixed name')
            target.write_text(receipt + '\n', encoding='utf-8')
        print(receipt)
        return 0
    except (OSError, ValueError, TypeError) as exc:
        parser.exit(2, 'Windows preview integrity verification failed: ' + str(exc) + '\n')


if __name__ == '__main__':
    sys.exit(main())
