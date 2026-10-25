"""Move an existing local Collector data set into a fresh installation.
No instrument network connection. Never overwrites destination files.
"""
import argparse, json, shutil, sqlite3, sys, tempfile
from datetime import datetime, timezone
from pathlib import Path

FILES=('collector/devices.json','collector/collector.sqlite3')

def transfer(old:Path,new:Path):
    old=old.resolve(); new=new.resolve()
    if old==new: raise ValueError('Old and new folders must differ')
    if not old.is_dir() or not new.is_dir(): raise ValueError('Both folders must exist')
    for name in FILES:
        if not (old/name).is_file():raise FileNotFoundError(f'Missing source: {old/name}')
    config=json.loads((old/FILES[0]).read_text(encoding='utf-8'))
    if not isinstance(config.get('devices'),list):raise ValueError('Invalid devices.json')
    # Never re-enable polling. Transfer explicitly disabled instrument configuration only.
    if any(d.get('enabled',False) or d.get('interval_seconds') is not None for d in config['devices']):
        raise ValueError('Source configuration contains enabled polling; safe transfer refused')
    targets=[new/name for name in FILES]
    # A fresh installation may contain sample files. Require explicit removal of those
    # before transfer rather than overwrite even a seemingly empty SQLite database.
    if any(p.exists() for p in targets):
        raise FileExistsError('Destination has devices.json or collector.sqlite3. No files modified. Move only after separately saving existing destination data.')
    with sqlite3.connect(f'file:{(old/FILES[1]).as_posix()}?mode=ro',uri=True) as source:
        if source.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise ValueError('Source SQLite integrity failed')
        # Snapshot avoids copying a database in the middle of a write.
        temp=Path(tempfile.mkstemp(prefix='mvk_snapshot_',suffix='.sqlite3',dir=new/'collector')[1])
        try:
            with sqlite3.connect(temp) as out:source.backup(out)
            with sqlite3.connect(temp) as check:
                if check.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('SQLite backup integrity failed')
            (new/FILES[0]).write_bytes((old/FILES[0]).read_bytes())
            temp.replace(new/FILES[1])
        finally:
            temp.unlink(missing_ok=True)
    return targets

def main():
    p=argparse.ArgumentParser(description='Safe one-time data transfer (NO instrument operations)')
    p.add_argument('--old',required=True,type=Path)
    p.add_argument('--new',required=True,type=Path)
    args=p.parse_args()
    try:
        paths=transfer(args.old,args.new)
        print('TRANSFER COMPLETED:',*(str(p) for p in paths),sep='\n')
    except Exception as exc:
        print('TRANSFER ABORTED:',type(exc).__name__,str(exc),file=sys.stderr)
        return 1
    return 0
if __name__=='__main__':raise SystemExit(main())
