#!/usr/bin/env python3
"""Find public Stage111 source references to possible original Delphi VA addresses.

Read-only lexical evidence, NO access to IDR/7z/original binaries.
An address literal is only a research hint, never function parity.
"""
from __future__ import annotations
import argparse,ast,json,pathlib,re
from collections import Counter

DIRS=("mvk_compatible/core","mvk_compatible/desktop",
      "tools/research/native_tcp10230_stage108_live_recording_r6_1/source")
PAT=re.compile(r"(?<![0-9A-Fa-f])(?:0x)?(00[4-8][0-9A-Fa-f]{5})(?![0-9A-Fa-f])",re.I)
BASE="https://github.com/shonentez-afk/MVK-Reader-Web/blob/"

def owners(source,rel):
    """Provide a strict method ownership hint for Python source lines."""
    if not rel.endswith(".py"):return []
    try:tree=ast.parse(source,filename=rel)
    except SyntaxError:return []
    bounds=[]
    def add(node,prefix=""):
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
            name=prefix+node.name
            bounds.append((node.lineno,getattr(node,"end_lineno",node.lineno),name))
            # Nested methods are not assumed without separate AST definition.
        elif isinstance(node,ast.ClassDef):
            for child in node.body:add(child,node.name+".")
    for top in tree.body:add(top)
    return bounds

def analyze(repo,sha="UNPINNED"):
    repo=pathlib.Path(repo)
    records=[];file_count=0
    for dirname in DIRS:
        folder=repo/dirname
        if not folder.is_dir():continue
        for path in sorted(folder.glob("*")):
            if path.suffix not in (".py",".go") or path.name.endswith("_test.go"):continue
            if path.name=="__init__.py":continue
            file_count+=1
            rel=path.relative_to(repo).as_posix()
            src=path.read_text(encoding="utf-8-sig",errors="replace")
            fn_bounds=owners(src,rel)
            for line,content in enumerate(src.splitlines(),1):
                for m in PAT.finditer(content):
                    addr=m.group(1).upper()
                    overlaps=[(b-a,a,name) for a,b,name in fn_bounds if a<=line<=b]
                    owner=min(overlaps)[2] if overlaps else ""
                    records.append({
                      "address":addr,"path":rel,"line":line,"owner":owner,
                      "literal":m.group(0),"excerpt":content.strip()[:240],
                      "evidence":"literal address in public Stage111 source; no original parity",
                      "url":f"{BASE}{sha}/{rel}#L{line}"
                    })
    records.sort(key=lambda x:(x["address"],x["path"],x["line"]))
    return {"metadata":{"scope":"PUBLIC_STAGE111_ADDRESS_LITERALS_ONLY","sha":sha,
                        "limitations":"Address-shaped literals may be unrelated to original. Private IDR matching must be performed locally."},
            "counts":{"files_scanned":file_count,"address_mentions":len(records),
                      "unique_addresses":len({x["address"] for x in records}),
                      "owner_scoped":sum(bool(x["owner"]) for x in records)},
            "references":records}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo",type=pathlib.Path,default=pathlib.Path("."))
    p.add_argument("--sha",default="UNPINNED")
    p.add_argument("--out",type=pathlib.Path,default=pathlib.Path(
        "docs/architecture/mvkview-recovery/stage111-address-references.json"))
    a=p.parse_args()
    result=analyze(a.repo,a.sha)
    if not result["counts"]["files_scanned"]:raise SystemExit("Source checkout missing")
    target=a.out if a.out.is_absolute() else a.repo/a.out
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result["counts"],ensure_ascii=False))
if __name__=="__main__":main()
