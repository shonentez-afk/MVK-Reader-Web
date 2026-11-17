#!/usr/bin/env python3
"""Compare Ghidra/Harness address 'not found' reports with an offline IDR bridge DB.

Read-only inputs: JSON, SQLite, optional Pascal disassembly export directory.
This is an evidence reconciliation tool, NOT a firmware or instrument driver.
"""
import argparse
import json
import re
import sqlite3
from pathlib import Path

INSN = re.compile(r'^\s*>?\s*([0-9A-Fa-f]{8})\s+([A-Za-z][A-Za-z0-9_]*)\b')

def source_instruction_index(root):
    """Map VA to instruction owner file; never copy source bodies to result."""
    out = {}
    if root is None:
        return out
    root=Path(root)
    for name in ('_Unit115.pas','_Unit125.pas','_Unit128.pas'):
        path = root/name
        if not path.is_file():
            continue
        # Decode all originals as CP1251. Numerical opcode lines remain ASCII.
        with path.open(encoding='cp1251',errors='replace') as f:
            for ln, line in enumerate(f,1):
                m=INSN.match(line)
                if m:
                    addr=m.group(1).upper()
                    out.setdefault(addr,[]).append({'unit':name,'line':ln,'mnemonic':m.group(2).lower()})
    return out

def crosscheck(db,evidence,pas_root=None):
    ev=json.loads(Path(evidence).read_text(encoding='utf-8'))
    rows=ev.get('address_availability_audit',{}).get('results',[])
    if not isinstance(rows,list):
        raise ValueError('Address audit results must be a list')
    src_index=source_instruction_index(pas_root)
    conn=sqlite3.connect(f'file:{Path(db).resolve()}?mode=ro',uri=True)
    conn.row_factory=sqlite3.Row
    audit=[]
    for row in rows:
        addr=row['address'].upper().removeprefix('0X')
        if not re.fullmatch(r'[0-9A-F]{8}',addr):
            raise ValueError('Unsafe or malformed address '+repr(addr))
        direct=conn.execute('SELECT name,unit FROM functions WHERE address=?',(addr,)).fetchone()
        previous=conn.execute('SELECT address,name,unit FROM functions WHERE address<=? ORDER BY address DESC LIMIT 1',(addr,)).fetchone()
        next_fn=conn.execute('SELECT address,name FROM functions WHERE address>? ORDER BY address LIMIT 1',(addr,)).fetchone()
        source=src_index.get(addr,[])
        current={'address':addr,'ghidra_function_found':bool(row.get('found')),
                 'idr_function_entry':dict(direct) if direct else None,
                 'pas_instruction_at_va':source,
                 'preceding_idr_function':dict(previous) if previous else None,
                 'next_idr_function':dict(next_fn) if next_fn else None}
        if row.get('found') is False and direct:
            current['classification']='GHIDRA_UNDEFINED_BUT_IDR_ENTRY'
        elif row.get('found') is False and source:
            current['classification']='GHIDRA_UNDEFINED_BUT_SOURCE_INSTRUCTION'
        elif row.get('found') is False:
            current['classification']='UNRESOLVED_BY_AVAILABLE_SOURCE'
        else:
            current['classification']='GHIDRA_RECOGNIZED'
        audit.append(current)
    entries=[x for x in audit if x['classification']=='GHIDRA_UNDEFINED_BUT_IDR_ENTRY']
    interior=[x for x in audit if x['classification']=='GHIDRA_UNDEFINED_BUT_SOURCE_INSTRUCTION']
    unresolved=[x for x in audit if x['classification']=='UNRESOLVED_BY_AVAILABLE_SOURCE']
    # Grounded independent call sites from the decompiled Pascal call-site index.
    watch=['00848E7D','00848200','0084FB03','0084C50A','0084C5A0','0084F7C8']
    call_sites=[]
    for site in watch:
        for row in conn.execute('SELECT caller_address,site_address,raw_target,target_name,resolved_address FROM calls WHERE site_address=?',(site,)):
            call_sites.append(dict(row))
    # Anchor DFM event links directly in the database extracted from original DFM.
    event_links=[]
    for component in ['bTaskConnect','bFreezeUpdate','bWriteAdc','bWriteValues','tmInterfaceUpdate']:
        for row in conn.execute('SELECT component_path,event_name,handler_name,handler_address FROM events WHERE component_path LIKE ?',('%/'+component,)):
            event_links.append(dict(row))
    conn.close()
    return {
      'schema':'mvk_harness_idr_reconciliation_v1',
      'source_basis':{'sqlite_used':True,'pas_index_used':bool(src_index)},
      'totals':{'addresses_audited':len(audit),'ghidra_false':sum(not x['ghidra_function_found'] for x in audit),
        'false_but_idr_entry':len(entries),'false_but_pas_instruction':len(interior),
        'false_unresolved':len(unresolved)},
      'audit':audit,'confirmed_call_sites':call_sites,'dfm_event_links':event_links,
      'analysis_limitations':["IDR bridge indexes source PAS plus DFM; IDP project internals beyond header/segments are not decoded.",
         "Source presence does not prove the local EXE is byte-for-byte the same build without independent hash comparison.",
         "An address that Ghidra doesn't label as a function is not evidence that executable bytes are missing.",
         "A 12-byte in-memory command queue entry is not proof of a 12-byte on-wire packet.",
         "ConfigModbus* names are not evidence that the measurement stream on TCP/10230 uses Modbus/TCP."]}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--db',required=True)
    ap.add_argument('--evidence',required=True)
    ap.add_argument('--pas-root')
    ap.add_argument('--out',help='optional local JSON result path')
    args=ap.parse_args()
    result=crosscheck(args.db,args.evidence,args.pas_root)
    data=json.dumps(result,indent=2,ensure_ascii=False)+'\n'
    if args.out:
        Path(args.out).write_text(data,encoding='utf-8')
    t=result['totals']
    print('AUDIT',json.dumps(t,ensure_ascii=False))
    for row in result['audit']:
        if not row['ghidra_function_found']:
            print(row['address'],row['classification'],'source_fn='+str(row['idr_function_entry']['name'] if row['idr_function_entry'] else '-'))

if __name__=='__main__':
    main()