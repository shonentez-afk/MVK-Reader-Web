"""Tests for public-only reconciliation: no private source payloads."""
import pathlib
import sys
import unittest

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from mvk_stage111_merge_graphs import combine

SHA="b"*40
PATH="mvk_compatible/desktop/start.py"
GO="tools/research/native_tcp10230_stage108_live_recording_r6_1/source/main.go"
def node(kind,path,name):
    return {"id":f"{kind}:{path}"+(f"::{name}" if kind!="file" else ""),
            "type":kind,"path":path,"name":name}

def fixtures():
    f=node("file",PATH,"start.py")
    fn=node("function",PATH,"Ui.run")
    old_go=node("file",GO,"main.go")
    py={"metadata":{"scope":"PUBLIC_STAGE111_ONLY","sha":SHA},
        "nodes":[f,fn,old_go],"edges":[{"from":f["id"],"to":fn["id"],"type":"contains"}]}
    new_go=node("function",GO,"main")
    go={"metadata":{"scope":"PUBLIC_STAGE111_GO_AST_ONLY","sha":SHA},
        "nodes":[old_go,new_go],"edges":[{"from":old_go["id"],"to":new_go["id"],"type":"contains"}]}
    def binding(line,callback):
        return {"id":f"qt:{PATH}:{line}","path":PATH,"line":line,"url":"https://github.test/source",
          "widget_expression":"self.button","widget_key":"button","signal":"clicked",
          "callback_expression":callback or "lambda: other.run()",
          "callback_target":callback,"resolution":"bound_self" if callback else "expression_dynamic",
          "evidence":"Python AST Qt connect"}
    qt={"metadata":{"scope":"PUBLIC_STAGE111_QT_AST_ONLY","sha":SHA},
        "bindings":[binding(8,"Ui.run"),binding(9,None)]}
    return py,go,qt

class MergeTests(unittest.TestCase):
    def test_single_graph_dedupes_go_and_joins_qt_target(self):
        d=combine(*fixtures())
        ids=[x["id"] for x in d["nodes"]]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertEqual(d["counts"]["qt_signal_bindings"],2)
        self.assertEqual(d["counts"]["qt_targets_resolved"],1)
        self.assertEqual(d["counts"]["qt_targets_unresolved"],1)
        edge={(x["from"],x["to"],x["type"]) for x in d["edges"]}
        self.assertIn((f"qt:{PATH}:8",f"function:{PATH}::Ui.run","qt-connect"),edge)
        self.assertNotIn((f"qt:{PATH}:9",f"function:{PATH}::Ui.run","qt-connect"),edge)
    def test_mixed_sha_rejected(self):
        py,go,qt=fixtures()
        qt["metadata"]["sha"]="c"*40
        with self.assertRaisesRegex(ValueError,"mixed revisions"): combine(py,go,qt)
if __name__=="__main__":unittest.main()
