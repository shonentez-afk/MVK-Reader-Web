"""Synthetic test for read-only native Go AST graph (no device traffic)."""
import json
import pathlib
import subprocess
import tempfile
import unittest

SCRIPT=pathlib.Path(__file__).with_name("mvk_stage111_go_ast.go")
DIR="tools/research/native_tcp10230_stage108_live_recording_r6_1/source"

class GoASTTests(unittest.TestCase):
    def test_go_direct_and_receiver_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp)
            source=root/DIR
            source.mkdir(parents=True)
            (source/"main.go").write_text(
                "package main\n"
                "type Receiver struct{}\n"
                "func Start() { run() }\n"
                "func run() {}\n"
                "func (r *Receiver) OnFrame(){r.Process(); Start()}\n"
                "func (r *Receiver) Process(){}\n",
                encoding="utf-8")
            out=root/"graph.json"
            subprocess.run(["go","run",str(SCRIPT),"--repo",str(root),"--sha","synthetic",
                            "--out",str(out)],check=True,capture_output=True,text=True)
            data=json.loads(out.read_text(encoding="utf-8"))
            calls={(e["from"].split("::")[-1],e["to"].split("::")[-1])
                   for e in data["edges"] if e["type"]=="call-site"}
            self.assertIn(("Start","run"),calls)
            self.assertIn(("Receiver.OnFrame","Receiver.Process"),calls)
            self.assertIn(("Receiver.OnFrame","Start"),calls)
            self.assertEqual(data["counts"]["direct_call_sites"],3)
            self.assertEqual(data["metadata"]["scope"],"PUBLIC_STAGE111_GO_AST_ONLY")
if __name__=="__main__":unittest.main()
