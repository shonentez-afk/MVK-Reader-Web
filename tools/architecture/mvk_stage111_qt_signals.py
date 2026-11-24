#!/usr/bin/env python3
"""Public read-only PySide6 signal-to-callback graph for Stage111.

Extracts AST .connect(callback) sites and the widget/handler expression.
Dynamic lambdas and external receivers are *candidates*, never proof of parity.
No original MVKView files are opened.
"""
from __future__ import annotations
import argparse
import ast
import json
import pathlib
import re

BASE="https://github.com/shonentez-afk/MVK-Reader-Web/blob/"
ROOT="mvk_compatible/desktop"
CALLBACK_METHODS={"clicked","toggled","triggered","currentChanged","currentIndexChanged",
                  "valueChanged","timeout","finished","itemDoubleClicked","itemChanged",
                  "currentItemChanged","currentRowChanged","editingFinished","sigMouseMoved",
                  "ready","failed","errorOccurred","readyReadStandardOutput","stateChanged",
                  "textChanged","activated","selectionChanged","pressed","released"}

def source_segment(src,node):
    return (ast.get_source_segment(src,node) or "").strip()

def callback_target(node,cls):
    """Resolve only simple local bound references, and one-call lambdas."""
    if isinstance(node,ast.Attribute) and isinstance(node.value,ast.Name):
        if node.value.id=="self" and cls: return cls+"."+node.attr, "bound_self"
        return None,"external_or_dynamic"
    if isinstance(node,ast.Name): return node.id,"unqualified"
    if isinstance(node,ast.Lambda):
        calls=[part for part in ast.walk(node.body) if isinstance(part,ast.Call)]
        if len(calls)==1:
            return callback_target(calls[0].func,cls)
        return None,"lambda_multi_or_dynamic"
    return None,"expression_dynamic"

def analyze(repo,sha):
    repo=pathlib.Path(repo)
    folder=repo/ROOT
    if not folder.is_dir():raise ValueError("Stage111 desktop directory not found")
    records=[]
    errors=[]
    for path in sorted(folder.glob("*.py")):
        if path.name=="__init__.py":continue
        rel=path.relative_to(repo).as_posix()
        src=path.read_text(encoding="utf-8-sig")
        try:tree=ast.parse(src,filename=rel)
        except SyntaxError as err:
            errors.append({"file":rel,"error":str(err)});continue
        sections=[]
        for item in tree.body:
            if isinstance(item,(ast.FunctionDef,ast.AsyncFunctionDef)):sections.append((item,None))
            if isinstance(item,ast.ClassDef):
                sections.extend((m,item.name) for m in item.body
                                if isinstance(m,(ast.FunctionDef,ast.AsyncFunctionDef)))
        for method,cls in sections:
            seen=set()
            for node in ast.walk(method):
                if not isinstance(node,ast.Call) or not isinstance(node.func,ast.Attribute):continue
                if node.func.attr!="connect" or not isinstance(node.func.value,ast.Attribute):continue
                signal_expr=node.func.value
                sig=signal_expr.attr
                if sig not in CALLBACK_METHODS and not sig.lower().startswith(("sig","on")):
                    # Unknown custom Qt signal still recorded (never asserted as unconnected).
                    pass
                if not node.args:continue
                target,how=callback_target(node.args[0],cls)
                widget=source_segment(src,signal_expr.value)
                callback=source_segment(src,node.args[0])
                # A literal object name is proven only when present in the
                # actual receiver expression, not inferred from similar names.
                match=re.search(r"""(?:buttons|file_action_buttons)\[\s*['"]([^'"]+)['"]\s*\]""",widget)
                component=match.group(1) if match else ""
                if not component:
                    dot=re.match(r"self\.([A-Za-z_]\w*)$",widget)
                    if dot:component=dot.group(1)
                line=node.lineno
                key=(rel,line,widget,sig,callback)
                if key in seen:continue
                seen.add(key)
                identifier=f"qt:{rel}:{line}"
                records.append({
                    "id":identifier,"path":rel,"line":line,"owner":(cls+"." if cls else "")+method.name,
                    "widget_expression":widget,"widget_key":component,
                    "signal":sig,"callback_expression":callback,
                    "callback_target":target,"resolution":how,
                    "evidence":"Python AST Qt connect, not runtime execution or original parity",
                    "url":f"{BASE}{sha}/{rel}#L{line}"
                })
    records.sort(key=lambda x:(x["path"],x["line"],x["id"]))
    return {"metadata":{"scope":"PUBLIC_STAGE111_QT_AST_ONLY","sha":sha,
                        "limitations":"AST signal.connect syntax only; dynamically generated connections may be missed"},
            "counts":{"bindings":len(records),"resolved_bound_targets":sum(x["resolution"]=="bound_self" for x in records),
                      "dynamic_or_external":sum(x["resolution"]!="bound_self" for x in records),
                      "files_scanned":len(list(folder.glob("*.py")))-int((folder/"__init__.py").exists()),
                      "parse_errors":len(errors)},
            "bindings":records,"errors":errors}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo",type=pathlib.Path,default=pathlib.Path("."))
    p.add_argument("--sha",default="UNPINNED")
    p.add_argument("--out",type=pathlib.Path,default=pathlib.Path(
       "docs/architecture/mvkview-recovery/stage111-qt-signals.json"))
    args=p.parse_args()
    result=analyze(args.repo,args.sha)
    if result["errors"] or result["counts"]["bindings"]<1:raise SystemExit(str(result["errors"]) or "No Qt bindings")
    dst=args.out if args.out.is_absolute() else args.repo/args.out
    dst.parent.mkdir(parents=True,exist_ok=True)
    dst.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result["counts"],ensure_ascii=False))
if __name__=="__main__":main()
