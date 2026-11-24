#!/usr/bin/env python3
"""Reconcile public Stage111 Python AST, Go AST and Qt signal graphs.

One source-independent graph.  NO original MVKView IDR data, raw device data,
or assertion of Win32 runtime parity.  Source links are pinned to one SHA.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from collections import Counter

def combine(py, go, qt):
    snapshots=[py["metadata"]["sha"],go["metadata"]["sha"],qt["metadata"]["sha"]]
    if len(set(snapshots))!=1:
        raise ValueError("mixed revisions: " + repr(snapshots))
    sha=snapshots[0]
    if py["metadata"].get("scope")!="PUBLIC_STAGE111_ONLY":
        raise ValueError("not a Stage111 Python graph")
    if go["metadata"].get("scope")!="PUBLIC_STAGE111_GO_AST_ONLY":
        raise ValueError("not a Stage111 Go graph")
    if qt["metadata"].get("scope")!="PUBLIC_STAGE111_QT_AST_ONLY":
        raise ValueError("not a Stage111 Qt event index")
    nodes={}
    for n in py["nodes"]:
        if not n["path"].endswith(".go"):nodes[n["id"]]=dict(n)
    for n in go["nodes"]:
        nodes[n["id"]]=dict(n)
    edges=[]
    dedupe=set()
    def add(src,dst,kind,line=None,evidence=None):
        if src not in nodes or dst not in nodes:
            return False
        key=(src,dst,kind,line)
        if key in dedupe:return False
        dedupe.add(key)
        edges.append({"from":src,"to":dst,"type":kind,"line":line,
                      "evidence":evidence or "Static AST; not runtime"})
        return True
    for graph in (py,go):
        for edge in graph["edges"]:
            add(edge["from"],edge["to"],edge["type"],edge.get("line"),edge.get("evidence"))
    resolved=0
    unresolved=[]
    for binding in qt["bindings"]:
        target_id=binding["id"]
        path=binding["path"]
        url=binding["url"]
        nodes[target_id]={
           "id":target_id,"type":"qt_signal","name":binding["widget_key"] or binding["widget_expression"],
           "path":path,"line":binding["line"],"url":url,"group":"Qt signal wiring",
           "widget":binding["widget_expression"],"widget_key":binding["widget_key"],
           "signal":binding["signal"],"callback":binding["callback_expression"],
           "resolution":binding["resolution"],"evidence":binding["evidence"]
        }
        add("file:"+path,target_id,"qt-wiring",binding["line"],binding["evidence"])
        callback=binding.get("callback_target")
        method="function:"+path+"::"+callback if callback else ""
        if method and add(target_id,method,"qt-connect",binding["line"],
                          "AST signal.connect callback, not original UI parity"):
            resolved+=1
        else:
            unresolved.append({"binding":target_id,"callback":callback,
                               "reason":"Dynamic/external callback or not indexed; no absence claim"})
    counts=Counter(n["type"] for n in nodes.values())
    kinds=Counter(e["type"] for e in edges)
    return {
       "metadata":{"scope":"PUBLIC_STAGE111_UNIFIED_AST_ONLY","sha":sha,
                   "sources":["Python AST","Go AST","Qt signal.connect AST"],
                   "limitations":"Static only. Delphi/Win32 parity, dynamic dispatch and device acceptance unverified."},
       "counts":{"nodes":len(nodes),"edges":len(edges),"files":counts["file"],
                 "functions":counts["function"],"classes":counts["class"],
                 "qt_signal_bindings":counts["qt_signal"],"qt_targets_resolved":resolved,
                 "qt_targets_unresolved":len(unresolved),"call_sites":kinds["call-site"]},
       "nodes":list(sorted(nodes.values(),key=lambda x:x["id"])),
       "edges":edges,
       "unresolved_qt_targets":unresolved
    }

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--python",type=Path,default=Path("docs/architecture/mvkview-recovery/stage111-public-graph.json"))
    p.add_argument("--go",type=Path,default=Path("docs/architecture/mvkview-recovery/stage111-go-callgraph.json"))
    p.add_argument("--qt",type=Path,default=Path("docs/architecture/mvkview-recovery/stage111-qt-signals.json"))
    p.add_argument("--out",type=Path,default=Path("docs/architecture/mvkview-recovery/stage111-unified-graph.json"))
    a=p.parse_args()
    read=lambda x:json.loads(x.read_text(encoding="utf-8"))
    merged=combine(read(a.python),read(a.go),read(a.qt))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(merged,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(merged["counts"],ensure_ascii=False))
if __name__=="__main__":main()
