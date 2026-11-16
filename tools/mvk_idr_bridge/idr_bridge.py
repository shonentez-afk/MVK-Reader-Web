"""Offline, read-only IDR -> SQLite knowledge-base builder for Delphi 32-bit EXE.

Uses only Python stdlib. Reconstructed Pascal is treated as evidence, not executable source.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import struct
from datetime import datetime, timezone

MAGIC = b'IDR proj v.3'
METHOD_MARKER = re.compile(r'^//([0-9A-Fa-f]{8})\s*$')
METHOD_DEF = re.compile(r'^\s*(?:\{\*)?\s*(procedure|function|constructor|destructor)\s+(.+?)\s*;', re.I)
ASM_CALL = re.compile(r'^\s*>?\s*([0-9A-Fa-f]{8})\s+call\s+(.+?)\s*$', re.I)
DFM_OBJECT = re.compile(r'^\s*(object|inherited|inline)\s+([\w.]+)\s*:\s*([\w.]+)', re.I)
DFM_PROP = re.compile(r'^\s*([\w.]+)\s*=\s*(.*?)\s*$')
DELPHI_TOKEN = re.compile(r"'(?:''|[^'])*'|#(?:\$[0-9A-Fa-f]+|\d+)")
HEX_ADDR = re.compile(r'^[0-9A-Fa-f]{8}$')

SCHEMA = '''
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE source_files (path TEXT PRIMARY KEY, kind TEXT, bytes INTEGER, sha256 TEXT);
CREATE TABLE functions (address TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL,
  signature TEXT NOT NULL, unit TEXT NOT NULL, source_file TEXT NOT NULL,
  line INTEGER NOT NULL, end_line INTEGER NOT NULL, reconstruction TEXT NOT NULL);
CREATE INDEX functions_name ON functions(name COLLATE NOCASE);
CREATE INDEX functions_unit ON functions(unit);
CREATE TABLE calls (id INTEGER PRIMARY KEY, caller_address TEXT NOT NULL,
  site_address TEXT NOT NULL, raw_target TEXT NOT NULL, target_name TEXT,
  target_address TEXT, resolved_address TEXT, source_file TEXT NOT NULL, line INTEGER NOT NULL,
  FOREIGN KEY(caller_address) REFERENCES functions(address));
CREATE INDEX calls_caller ON calls(caller_address);
CREATE INDEX calls_target ON calls(resolved_address);
CREATE INDEX calls_target_name ON calls(target_name COLLATE NOCASE);
CREATE TABLE forms (name TEXT PRIMARY KEY, class_name TEXT NOT NULL,
  source_file TEXT NOT NULL, line INTEGER NOT NULL);
CREATE TABLE components (path TEXT PRIMARY KEY, form_name TEXT NOT NULL,
  component_name TEXT NOT NULL, class_name TEXT NOT NULL, parent_path TEXT,
  caption TEXT, caption_raw TEXT, properties_json TEXT NOT NULL,
  source_file TEXT NOT NULL, line INTEGER NOT NULL,
  FOREIGN KEY(form_name) REFERENCES forms(name));
CREATE INDEX components_name ON components(component_name COLLATE NOCASE);
CREATE INDEX components_form ON components(form_name);
CREATE TABLE events (id INTEGER PRIMARY KEY, form_name TEXT NOT NULL,
  component_path TEXT NOT NULL, event_name TEXT NOT NULL, handler_name TEXT NOT NULL,
  handler_address TEXT, resolution TEXT NOT NULL, source_file TEXT NOT NULL, line INTEGER NOT NULL);
CREATE INDEX events_component ON events(component_path);
CREATE INDEX events_handler ON events(handler_name COLLATE NOCASE);
'''


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        while b := f.read(1024 * 1024):
            h.update(b)
    return h.hexdigest()


def idp_header(path: Path) -> dict:
    """Parse only the verified IDR v3 header and PE segment directory, NOT entire IDP."""
    with path.open('rb') as f:
        header = f.read(56)
        if len(header) != 56 or header[:12] != MAGIC:
            raise ValueError('Unsupported IDR project header (requires IDR proj v.3)')
        v = struct.unpack('<11I', header[12:])
        version_flags, ep, image_base, image_size, total_size, code_base, code_size, code_start, data_base, data_size, data_start = v
        count_bytes = f.read(4)
        if len(count_bytes) != 4:
            raise ValueError('Truncated IDP segment directory')
        num = struct.unpack('<I', count_bytes)[0]
        if num > 100:
            raise ValueError(f'Unreasonable IDP segment count: {num}')
        segments = []
        for _ in range(num):
            b = f.read(16)
            if len(b) != 16:
                raise ValueError('Truncated IDP segment record')
            start, size, flags, name_size = struct.unpack('<4I', b)
            if name_size > 4096:
                raise ValueError('Unreasonable IDP segment name')
            name = f.read(name_size)
            if len(name) != name_size:
                raise ValueError('Truncated IDP segment name')
            segments.append({'start':f'{start:08X}', 'size':size, 'flags':flags,
                             'name':name.decode('cp1252', 'replace')})
    return {'format': MAGIC.decode('ascii'), 'delphi_version':version_flags & 0x7fff,
            'version_flags':version_flags, 'entry_point':f'{ep:08X}',
            'image_base':f'{image_base:08X}', 'image_size':image_size, 'total_size':total_size,
            'code_base':f'{code_base:08X}', 'code_size':code_size, 'code_start':code_start,
            'data_base':f'{data_base:08X}', 'data_size':data_size, 'data_start':data_start,
            'segments':segments, 'size_bytes':path.stat().st_size, 'sha256':sha256(path),
            'scope':'header_and_segments_only; full IDP object/RTTI records not decoded'}


def decode_delphi_literal(s: str) -> str:
    """Decode only concatenated quoted literals and #decimal / #$hex codepoint tokens."""
    pieces, pos = [], 0
    for token in DELPHI_TOKEN.finditer(s):
        if s[pos:token.start()].strip():
            return s.strip()  # Mixed dynamic expression; don't invent a value.
        raw = token.group(0)
        if raw.startswith("'"):
            pieces.append(raw[1:-1].replace("''", "'"))
        else:
            value = int(raw[2:], 16) if raw.startswith('#$') else int(raw[1:])
            if value > 0x10FFFF:
                return s.strip()
            pieces.append(chr(value))
        pos = token.end()
    if not pieces or s[pos:].strip():
        return s.strip()
    return ''.join(pieces)


def parse_source_methods(path: Path, rel: str):
    text = path.read_bytes().decode('cp1252', errors='replace')
    lines = text.split('\n')
    methods = []
    # Parse implementation rather than only class interface; this preserves traceable source positions.
    in_impl = False
    for i, line in enumerate(lines):
        if line.strip().lower() == 'implementation':
            in_impl = True
        if not in_impl:
            continue
        m = METHOD_MARKER.match(line)
        if not m or i + 1 >= len(lines):
            continue
        next_line = lines[i+1].strip()
        sig = METHOD_DEF.match(next_line)
        if sig is None:
            continue
        kind = sig.group(1).lower()
        tail = sig.group(2)
        # Parameter types may contain nested angle brackets; the first '(' starts the argument list.
        name = re.split(r'\(', tail, maxsplit=1)[0].strip()
        if not name or len(name) > 280:
            continue
        methods.append({'address':m.group(1).upper(), 'kind':kind,
                        'name':name, 'signature':next_line.strip().removeprefix('{*'),
                        'unit':path.stem, 'source_file':rel, 'line':i+2,
                        'start_idx':i, 'end_idx':len(lines),
                        'reconstruction':'commented_stub' if next_line.startswith('{*') else 'decompiled_asm'})
    calls=[]
    for i, method in enumerate(methods):
        end = methods[i+1]['start_idx'] if i+1 < len(methods) else len(lines)
        method['end_idx'] = end
        method['end_line'] = end
        for offset in range(method['start_idx']+1, end):
            mm = ASM_CALL.match(lines[offset])
            if not mm:
                continue
            raw_target = mm.group(2).strip()
            left = raw_target.split(';',1)[0].strip()
            target_address = left.upper() if HEX_ADDR.fullmatch(left) else None
            target_name = None if target_address else left
            if target_name and len(target_name)>240:
                target_name=target_name[:240]
            calls.append({'caller_address':method['address'], 'site_address':mm.group(1).upper(),
                          'raw_target':raw_target[:300], 'target_name':target_name,
                          'target_address':target_address, 'source_file':rel, 'line':offset+1})
    for row in methods:
        row.pop('start_idx');row.pop('end_idx')
    return methods,calls


def parse_dfm(path: Path, rel: str):
    lines = path.read_bytes().decode('cp1252', errors='replace').split('\n')
    comps=[];stack=[]
    for i,line in enumerate(lines):
        indent=len(line)-len(line.lstrip(' '))
        om=DFM_OBJECT.match(line)
        if om:
            while stack and stack[-1]['indent']>=indent:
                stack.pop()
            name,cls=om.group(2),om.group(3)
            parent=stack[-1]['path'] if stack else None
            path_key=(parent+'/' if parent else '')+name
            row={'path':path_key,'component_name':name,'class_name':cls,
                 'parent_path':parent,'properties':{},'source_file':rel,'line':i+1,'indent':indent,
                 'event_lines':{}}
            comps.append(row);stack.append(row)
            continue
        if not stack or not line.strip() or line.lstrip().startswith('end'):
            continue
        if indent<=stack[-1]['indent']:
            while stack and indent<=stack[-1]['indent']:
                stack.pop()
            if not stack:
                continue
        pm=DFM_PROP.match(line)
        if not pm:continue
        key,value=pm.group(1),pm.group(2)
        if key.startswith('On') and re.fullmatch(r'[\w.]+',value):
            stack[-1]['event_lines'][key]=(value,i+1)
        if key in {'Caption','Text','Hint','ImageName','ImageIndex','ActivePage','Visible','Enabled',
                   'TabVisible','Left','Top','Width','Height','Align','TabOrder','Checked',
                   'Position','ModalResult','Menu','PopupMenu','ItemIndex','Tag','Min','Max','Value','TextHint'}:
            stack[-1]['properties'][key]=value[:500]
    if not comps:return [],[]
    root=comps[0];frm=root['component_name'];class_name=root['class_name']
    form={'name':frm,'class_name':class_name,'source_file':rel,'line':root['line']}
    events=[]
    for row in comps:
        for evt,(handler,line) in row['event_lines'].items():
            events.append({'form_name':frm,'component_path':row['path'],
                           'event_name':evt,'handler_name':handler,
                           'source_file':rel,'line':line})
        row['form_name']=frm
        row['caption_raw']=row['properties'].get('Caption')
        row['caption']=decode_delphi_literal(row['caption_raw']) if row['caption_raw'] else None
        row.pop('indent');row.pop('event_lines')
    return form,comps,events


def build(idp:Path, source_root:Path, db:Path, out:Path) -> dict:
    if not idp.is_file():raise FileNotFoundError(idp)
    if not source_root.is_dir():raise NotADirectoryError(source_root)
    header=idp_header(idp)
    paths=sorted(p for p in source_root.rglob('*') if p.is_file() and p.suffix.lower() in {'.pas','.dfm','.dpr'})
    db.parent.mkdir(parents=True,exist_ok=True)
    out.mkdir(parents=True,exist_ok=True)
    if db.exists():db.unlink()
    conn=sqlite3.connect(db)
    conn.executescript(SCHEMA)
    with conn:
        conn.execute('INSERT INTO meta VALUES (?,?)',('idp_header',json.dumps(header,ensure_ascii=False)))
        conn.execute('INSERT INTO meta VALUES (?,?)',('builder', 'mvk_idr_bridge_v1'))
        for path in paths:
            rel=path.relative_to(source_root).as_posix()
            kind=path.suffix[1:].lower()
            conn.execute('INSERT INTO source_files VALUES (?,?,?,?)',(rel,kind,path.stat().st_size,sha256(path)))
            if kind=='pas':
                methods,calls=parse_source_methods(path,rel)
                for f in methods:
                    conn.execute('INSERT OR IGNORE INTO functions VALUES (?,?,?,?,?,?,?,?,?)',
                      (f['address'],f['name'],f['kind'],f['signature'],f['unit'],f['source_file'],
                       f['line'],f['end_line'],f['reconstruction']))
                for c in calls:
                    conn.execute('INSERT INTO calls (caller_address,site_address,raw_target,target_name,target_address,resolved_address,source_file,line) VALUES (?,?,?,?,?,?,?,?)',
                      (c['caller_address'],c['site_address'],c['raw_target'],c['target_name'],
                       c['target_address'],None,c['source_file'],c['line']))
            elif kind=='dfm':
                form,comps,events=parse_dfm(path,rel)
                if not form:continue
                conn.execute('INSERT OR IGNORE INTO forms VALUES (?,?,?,?)',tuple(form.values()))
                for comp in comps:
                    conn.execute('INSERT OR IGNORE INTO components VALUES (?,?,?,?,?,?,?,?,?,?)',
                      (comp['path'],comp['form_name'],comp['component_name'],comp['class_name'],
                       comp['parent_path'],comp['caption'],comp['caption_raw'],
                       json.dumps(comp['properties'],ensure_ascii=False),comp['source_file'],comp['line']))
                for e in events:
                    conn.execute('INSERT INTO events (form_name,component_path,event_name,handler_name,handler_address,resolution,source_file,line) VALUES (?,?,?,?,?,?,?,?)',
                      (e['form_name'],e['component_path'],e['event_name'],e['handler_name'],None,'unresolved',e['source_file'],e['line']))
        # Resolve direct call references by address and unique decompiled symbol name.
        functions=conn.execute('SELECT address,name FROM functions').fetchall()
        by_name={};by_lower={}
        for address,name in functions:
            by_lower.setdefault(name.casefold(),[]).append(address)
        rows=conn.execute('SELECT id,target_name,target_address FROM calls').fetchall()
        for id_,symbol,adr in rows:
            resolved=None
            if adr and conn.execute('SELECT 1 FROM functions WHERE address=?',(adr,)).fetchone():
                resolved=adr
            elif symbol:
                candidates=by_lower.get(symbol.casefold(),[])
                if len(candidates)==1:resolved=candidates[0]
            if resolved:
                conn.execute('UPDATE calls SET resolved_address=? WHERE id=?',(resolved,id_))
        # Bind Delphi form event handler name to owning class; fallback only if unique.
        for id_,form,handler in conn.execute('SELECT id,form_name,handler_name FROM events').fetchall():
            cls=conn.execute('SELECT class_name FROM forms WHERE name=?',(form,)).fetchone()[0]
            candidates=by_lower.get(f'{cls}.{handler}'.casefold(),[])
            if not candidates:
                suffix=f'.{handler}'.casefold()
                candidates=[addr for addr,name in functions if name.casefold().endswith(suffix)]
            if len(candidates)==1:
                conn.execute('UPDATE events SET handler_address=?,resolution=? WHERE id=?',
                             (candidates[0],'exact_unique',id_))
            elif len(candidates)>1:
                conn.execute('UPDATE events SET resolution=? WHERE id=?',('ambiguous',id_))
    conn.row_factory=sqlite3.Row
    counts={name:conn.execute(f'SELECT COUNT(*) FROM {name}').fetchone()[0]
            for name in ['source_files','functions','calls','forms','components','events']}
    counts['events_resolved']=conn.execute("SELECT COUNT(*) FROM events WHERE resolution='exact_unique'").fetchone()[0]
    counts['calls_resolved']=conn.execute('SELECT COUNT(*) FROM calls WHERE resolved_address IS NOT NULL').fetchone()[0]
    counts['dfm_class_count']=conn.execute('SELECT COUNT(DISTINCT class_name) FROM components').fetchone()[0]
    counts['pas_count']=conn.execute("SELECT COUNT(*) FROM source_files WHERE kind='pas'").fetchone()[0]
    counts['dfm_count']=conn.execute("SELECT COUNT(*) FROM source_files WHERE kind='dfm'").fetchone()[0]
    counts['dpr_count']=conn.execute("SELECT COUNT(*) FROM source_files WHERE kind='dpr'").fetchone()[0]
    meta={'schema_version':1,'built_utc':datetime.now(timezone.utc).isoformat(),
          'idp':header,'source_counts':counts,'sources':'user-supplied MVKView IDR project and reconstructed Delphi export',
          'limitations':['Recovered IDR code is not guaranteed compiling Delphi source',
                         'IDP internal records not fully decoded; header and segment directory only',
                         'Dynamically dispatched, computed, and indirect calls are not resolved',
                         'A linked DFM event proves wiring, not runtime execution',
                         'No hardware/control actions or memory instrumentation performed']}
    (out/'manifest.json').write_text(json.dumps(meta,indent=2,ensure_ascii=False),encoding='utf-8')
    # Export Ghidra-compatible source metadata as plain CSV without unsafe command injection.
    with (out/'ghidra_labels.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.writer(f);w.writerow(['address','name','unit','source_file','line','reconstruction'])
        for r in conn.execute('SELECT address,name,unit,source_file,line,reconstruction FROM functions ORDER BY address'):
            w.writerow(tuple(r))
    with (out/'event_handlers.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.writer(f);w.writerow(['form','component_path','event','handler','address','resolution','source_file','line'])
        for r in conn.execute('SELECT form_name,component_path,event_name,handler_name,handler_address,resolution,source_file,line FROM events ORDER BY form_name,component_path'):
            w.writerow(tuple(r))
    with (out/'forms_components.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.writer(f);w.writerow(['form','component_path','class','caption','properties_json','source_file','line'])
        for r in conn.execute('SELECT form_name,path,class_name,caption,properties_json,source_file,line FROM components ORDER BY form_name,path'):
            w.writerow(tuple(r))
    important=['bTaskConnect','bTaskView','bTaskConfigCh','bTaskConfigIP','Pages','bSpecCopyValue','bSpecSaveValue']
    lines=["# MVKView IDR — отчёт фактической реконструкции", "", "Сформировано из приложенных `mvkview.idp` и `Projects.7z`; всё извлечено статически без запуска MVKView.", "",
           "## Покрытие", "", "| Набор | Количество |", "|---|---:|"]
    for k,v in counts.items():lines.append(f'| {k} | {v:,} |')
    lines += ['', '## Проверенные ориентиры', '', '| Компонент | Событие | Обработчик | Адрес | Источник |', '|---|---|---|---|---|']
    for name in important:
        matches=conn.execute('SELECT c.component_name,e.event_name,e.handler_name,e.handler_address,e.source_file,e.line FROM components c JOIN events e ON c.path=e.component_path WHERE c.component_name=? ORDER BY e.event_name',(name,)).fetchall()
        for r in matches:
            lines.append(f'| `{r[0]}` | `{r[1]}` | `{r[2]}` | `{r[3] or "unresolved"}` | `{r[4]}:{r[5]}` |')
    g=conn.execute("SELECT address,source_file,line FROM functions WHERE name='TMvkChannelStorage.GetSpectrum'").fetchone()
    if g:
        lines+=['', '### GetSpectrum', '', f'`TMvkChannelStorage.GetSpectrum`: `{g[0]}` (`{g[1]}:{g[2]}`).', '', 'Вызовы в восстановленном машинном коде:', '']
        for x in conn.execute('SELECT c.caller_address,f.name,c.site_address,c.source_file,c.line FROM calls c JOIN functions f ON f.address=c.caller_address WHERE c.resolved_address=? ORDER BY c.site_address',(g[0],)):
            lines.append(f'- `{x[2]}` — `{x[1]}` (`{x[0]}`), `{x[3]}:{x[4]}`')
    lines+=['','## Границы доказательств','', '- Адреса и переходы получены из восстановленного IDR-листинга, а не из динамической трассировки.',
            '- Полные записи IDP, включая RTTI и InfoRec, отдельно не декодировались.',
            '- Элементы с `Caption = "$"` имеют динамическую подпись: её нельзя достоверно восстановить из DFM.',
            '- Для аппаратных кнопок запрещено автоматическое выполнение; MCP-мост предоставляет только чтение.','']
    (out/'AUDIT_RU.md').write_text('\n'.join(lines),encoding='utf-8')
    conn.close()
    return meta


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--idp',type=Path,required=True)
    ap.add_argument('--sources',type=Path,required=True,help='Directory containing reconstructed PAS/DFM')
    ap.add_argument('--db',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args()
    manifest=build(a.idp,a.sources,a.db,a.out)
    print(json.dumps(manifest['source_counts'],ensure_ascii=False,indent=2))

if __name__=='__main__':main()