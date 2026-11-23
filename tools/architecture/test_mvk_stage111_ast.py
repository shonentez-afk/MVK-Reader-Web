import pathlib
import tempfile
import unittest
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from mvk_stage111_ast import analyze


class PublicGraphTests(unittest.TestCase):
    def test_python_local_and_import_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            core = root / "mvk_compatible" / "core"
            core.mkdir(parents=True)
            (core / "helper.py").write_text("def convert(x):\n    return x * 2\n")
            (core / "module.py").write_text(
                "from .helper import convert\n"
                "class Reader:\n"
                "    def start(self, x):\n"
                "        return self.finish(convert(x))\n"
                "    def finish(self, x):\n"
                "        return x\n"
            )
            graph = analyze(root, "test-sha")
            edges = {(e["from"], e["to"], e["type"]) for e in graph["edges"]}
            self.assertIn(("function:mvk_compatible/core/module.py::Reader.start",
                           "function:mvk_compatible/core/module.py::Reader.finish",
                           "call-site"), edges)
            self.assertIn(("function:mvk_compatible/core/module.py::Reader.start",
                           "function:mvk_compatible/core/helper.py::convert",
                           "call-site"), edges)
            self.assertEqual(graph["counts"]["parse_errors"], 0)

    def test_go_declarations_not_fake_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            src = root / "tools/research/native_tcp10230_stage108_live_recording_r6_1/source"
            src.mkdir(parents=True)
            (src / "main.go").write_text("package main\nfunc main() {}\nfunc (r *Rx) read() {}\n")
            graph = analyze(root, "test-sha")
            self.assertTrue(any(n["name"] == "Rx.read" for n in graph["nodes"]))
            self.assertFalse(any(e["type"] == "call-site" for e in graph["edges"]))


if __name__ == "__main__":
    unittest.main()
