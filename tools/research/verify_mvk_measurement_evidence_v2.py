"""Offline read-only MVKView source audit for Harness measurement evidence.

No executable launch, network, database writes, or original device access.
The emitted JSON has no raw source code or user paths.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import sqlite3
import struct
from pathlib import Path
from urllib.parse import quote

EXPECTED_FUNCTIONS = {
    '00848E78': 'Tmvkform.bTaskConnectClick',
    '00848E84': 'Tmvkform.bTaskViewClick',
    '00846AD4': 'sub_00846AD4',
    '008060B0': 'TMVKThread.Create',
    '00807A98': 'TMVKThread.Execute',
    '0084F7C8': 'Tmvkform.tmInterfaceUpdateTimer',
    '0084F7D0': 'sub_0084F7D0',
    '0084FA6C': 'TBackgroundProcessThread.Execute',
    '0084E914': 'Tmvkform.bWriteAdcClick',
    '0084E988': 'Tmvkform.bWriteValuesClick',
    '00809364': 'sub_00809364',
    '00809400': 'TMVKThread.SetRate',
}
EXPECTED_EVENTS = {
    'bTaskConnectClick': '00848E78',
    'bTaskViewClick': '00848E84',
    'bFreezeUpdateClick': '0084DEA4',
    'bWriteAdcClick': '0084E914',
    'bWriteValuesClick': '0084E988',
    'tmInterfaceUpdateTimer': '0084F7C8',
}
# Source instruction patterns, not an EXE byte-level identity check.
INSNS = [
    ('_Unit128.pas','00848E78','mov','edx,2'),
    ('_Unit128.pas','00848E84','mov','edx,1'),
    ('_Unit128.pas','00846B5C','call','00847040'),
    ('_Unit128.pas','00846EAA','call','TOpenDialog.GetFileName'),
    ('_Unit128.pas','0084F7C8','call','00847248'),
    ('_Unit128.pas','0084F7D0','push','ebp'),
    ('_Unit128.pas','0084FA6C','push','ebx'),
    ('_Unit128.pas','0084FB03','call','TMvkChannelStorage.GetSpectrum'),
    ('_Unit128.pas','0084FB0C','cmp','FTerminated'),
    ('_Unit128.pas','0084FB10','jne','0084FB57'),
    ('_Unit128.pas','0084FB2D','call','TThread.Synchronize'),
    ('_Unit128.pas','0084E936','fstp','[eax+404E0]'),
    ('_Unit128.pas','0084E9B3','fstp','[eax+404E8]'),
    ('_Unit128.pas','0084E95A','cmp','esi,0A'),
    ('_Unit125.pas','00807C12','mov','dx,27F6'),
    ('_Unit125.pas','00807C24','mov','edx,3E8'),
    ('_Unit125.pas','00807C34','mov','edx,1388'),
    ('_Unit125.pas','00807F78','call','TIdIOHandler.ReadUInt32'),
    ('_Unit125.pas','00807F84','call','TIdIOHandler.ReadUInt32'),
    ('_Unit125.pas','00808019','sub','ebx,8'),
    ('_Unit125.pas','00808AD0','call','TThread.Sleep'),
    ('_Unit125.pas','00808B15','je','00807BC2'),
    ('_Unit125.pas','00808B60','jmp','00808B35'),
    ('_Unit125.pas','00808B62','pop','edi'),
    ('_Unit125.pas','00808B68','ret',''),
    ('_Unit125.pas','0080936B','mov','ecx,0E'),
    ('_Unit125.pas','00809370','mov','edx,1'),
    ('_Unit125.pas','00809375','call','TMVKThread.QueueCommand'),
    ('_Unit125.pas','00807F52','call','TIdIOHandler.Write'),
]
EXPECTED_CALLERS = {
    '0084C50A': '0084C4C8',  # mSpecLines1Click
    '0084C5A0': '0084C514',  # mSpecType1Click
    '0084FB03': '0084FA6C',  # background Execute
    '00809375': '00809364',  # SetRate helper -> QueueCommand
}
EXCEPTION_EVENTS = {
    '008088A2': 'errDisconnected',
    '008088CE': 'errNotResponding',
    '008088FA': 'errCannotConnect',
    '00808923': 'errTransferError',
}


def connect_read_only(path: Path) -> sqlite3.Connection:
    uri = 'file:' + quote(str(path.resolve()), safe='/:') + '?mode=ro'
    c = sqlite3.connect(uri, uri=True)
    c.execute('PRAGMA query_only = ON')
    return c


def insn_map(path: Path) -> dict[str, str]:
    result = {}
    data = path.read_text(encoding='utf-8', errors='replace')
    pattern = re.compile(r'^\s*>?([0-9A-F]{8})\s+(\S.*)$', re.MULTILINE)
    for match in pattern.finditer(data):
        result[match.group(1)] = match.group(2).strip()
    return result


def verify(db: Path, sources: Path, idp: Path, evidence: Path | None = None) -> dict:
    checks = []
    def record(name: str, passed: bool):
        checks.append({'check':name, 'pass':bool(passed)})

    with connect_read_only(db) as c:
        meta = dict(c.execute('SELECT key,value FROM meta'))
        header_meta = json.loads(meta['idp_header'])
        with idp.open('rb') as f:
            header=f.read(64)
        record('idp_v3_header', header.startswith(b'IDR proj v.3'))
        record('idp_image_base', struct.unpack_from('<I',header,20)[0] == int(header_meta['image_base'],16))
        record('idp_entry', struct.unpack_from('<I',header,16)[0] == int(header_meta['entry_point'],16))
        record('idp_sha256', hashlib.sha256(idp.read_bytes()).hexdigest()==header_meta['sha256'])
        for name in ['_Unit125.pas','_Unit128.pas','mvkform.dfm']:
            r=c.execute('SELECT sha256 FROM source_files WHERE path=?',(name,)).fetchone()
            sha=hashlib.sha256((sources/name).read_bytes()).hexdigest()
            record('pas_dfm_sha_'+name, bool(r and sha==r[0]))
        for addr,name in EXPECTED_FUNCTIONS.items():
            row=c.execute('SELECT name FROM functions WHERE address=?',(addr,)).fetchone()
            record('function_'+addr, bool(row and row[0] == name))
        for name,addr in EXPECTED_EVENTS.items():
            row=c.execute('SELECT handler_address FROM events WHERE handler_name=?',(name,)).fetchone()
            record('dfm_event_'+name, bool(row and row[0]==addr))
        for site,owner in EXPECTED_CALLERS.items():
            row=c.execute('SELECT caller_address FROM calls WHERE site_address=?',(site,)).fetchone()
            record('call_owner_'+site, bool(row and row[0]==owner))

    code={name:insn_map(sources/name) for name in ['_Unit125.pas','_Unit128.pas']}
    for fname,address,mnemonic,needle in INSNS:
        original=code[fname].get(address,'').lower()
        expected=(mnemonic+' ').lower()
        record('instruction_'+address, ((original.startswith(expected) and needle.lower() in original) if needle else original == mnemonic.lower()))
    for address,key in EXCEPTION_EVENTS.items():
        original=code['_Unit125.pas'].get(address,'')
        # Error handler starts at this address; search only bounded successor instructions.
        near=' '.join(code['_Unit125.pas'].get(f'{x:08X}','') for x in range(int(address,16),int(address,16)+40))
        record('exception_'+address, bool(original and key.lower() in near.lower()))

    evidence_version = None
    if evidence:
        source=json.loads(evidence.read_text(encoding='utf-8'))
        evidence_version = source.get('version')
        record('harness_v2_evidence', evidence_version == 2)
    return {
        'contract': 'MVK_3SOURCE_MEASUREMENT_STATIC_V2',
        'scope': 'original IDP header + source-listed PAS/DFM + read-only sqlite; no live EXE or device verification',
        'evidence_version':evidence_version,
        'passed':sum(1 for x in checks if x['pass']),
        'total':len(checks),
        'failed':[x['check'] for x in checks if not x['pass']],
        'checks_passed':all(x['pass'] for x in checks),
    }


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db',required=True,type=Path)
    p.add_argument('--sources',required=True,type=Path)
    p.add_argument('--idp',required=True,type=Path)
    p.add_argument('--evidence',type=Path)
    a=p.parse_args()
    result=verify(a.db,a.sources,a.idp,a.evidence)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['checks_passed'] else 2

if __name__=='__main__':raise SystemExit(main())