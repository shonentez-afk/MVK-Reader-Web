"""CI-only: downgrade a generated Z31R v1.5 B to the exact v1.4 storage guards.

No original process, source measurement, or debugger is required. This file
must not be used as an actual capture script for a user.
"""
from pathlib import Path
import hashlib
import json
import sys

def main(folder: Path) -> None:
    script=folder/'RESUME_B_FROM_14AA.txt'
    cfgpath=folder/'capture_config.json'
    body=script.read_text(encoding='ascii')
    anchor='cmp mem.base($z31r_ctx_storage),0\nje Z31R_FAIL_STORAGE\n'
    if body.count(anchor)!=1: raise ValueError('missing new storage pointer guard')
    start=body.index(anchor)
    end=body.index('cmp dword:[$z31r_ctx_storage+0x18],',start)
    assert 'Z31R_B_STORAGE_PROBE' in body[start:end]
    body=body[:start]+anchor+'cmp dword:[$z31r_ctx_storage+0x0C],0x1\njne Z31R_FAIL_STORAGE\n'+body[end:]
    start=body.index('Z31R_FAIL_STORAGE:\n')
    end=body.index('Z31R_FAIL_FILTER:\n', start)
    body=body[:start]+('Z31R_FAIL_STORAGE:\n'
        'log "Z31R_FAIL_STORAGE: invalid storage pointer or FAdcDataType not 1 (float ring)."\n'
        'jmp Z31R_ABORT\n')+body[end:]
    body=body.replace('// Z31R V1.5 RESUME B','// Z31R V1.4 RESUME B')
    if 'Z31R_FAIL_STORAGE_TYPE' in body or 'Z31R_B_STORAGE_PROBE' in body:
        raise ValueError('incomplete fixture downgrade')
    script.write_text(body,encoding='ascii',newline='\n')
    cfg=json.loads(cfgpath.read_text(encoding='utf-8-sig'))
    cfg['script_b_sha256']=hashlib.sha256(script.read_bytes()).hexdigest()
    cfgpath.write_text(json.dumps(cfg,ensure_ascii=True),encoding='utf-8')
    print('Z31R_TEST_FIXTURE_V14_CREATED: synthetic generated B only; not for debugger')

if __name__=='__main__':
    if len(sys.argv)!=2: raise SystemExit('Usage: generate_v14_storage_fixture.py RUN_FOLDER')
    main(Path(sys.argv[1]))
