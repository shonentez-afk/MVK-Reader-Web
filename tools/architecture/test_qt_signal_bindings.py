"""Synthetic AST tests for PySide6 connect bindings; no Qt import or device."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
from mvk_stage111_qt_signals import analyze

class QtSignalTests(unittest.TestCase):
    def test_bound_and_lambda_with_original_component_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            folder=root/"mvk_compatible/desktop";folder.mkdir(parents=True)
            (folder/"controls.py").write_text(
                "class Controls:\n"
                " def build(self):\n"
                "  self.buttons['bWriteAdc'].clicked.connect(self.write_adc)\n"
                "  self.buttons['bWriteValues'].clicked.connect(lambda: self.write_values(True))\n"
                "  self.timer.timeout.connect(lambda: self.write_values(False))\n"
                "  self.other.changed.connect(self.window.remote_method)\n"
                " def write_adc(self): pass\n"
                " def write_values(self,flag): pass\n",encoding="utf-8")
            d=analyze(root,"0123456789"*4)
            self.assertEqual(d["counts"]["bindings"],4)
            by={x["widget_key"]:x for x in d["bindings"] if x["widget_key"].startswith("b")}
            self.assertEqual(by["bWriteAdc"]["callback_target"],"Controls.write_adc")
            self.assertEqual(by["bWriteValues"]["callback_target"],"Controls.write_values")
            self.assertEqual(by["bWriteValues"]["resolution"],"bound_self")
            self.assertEqual(by["bWriteAdc"]["signal"],"clicked")
            self.assertEqual(d["counts"]["dynamic_or_external"],1)
            self.assertTrue(all("#L" in x["url"] for x in d["bindings"]))
    def test_no_deduction_from_caption_or_comments(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/"mvk_compatible/desktop";folder.mkdir(parents=True)
            (folder/"x.py").write_text(
                "def wire(self):\n"
                "  # bTaskConnect original button; not an actual widget key\n"
                "  control.clicked.connect(lambda checked: self.enter_measure_mode(checked))\n",
                encoding="utf-8")
            d=analyze(root,"test")
            self.assertEqual(len(d["bindings"]),1)
            self.assertEqual(d["bindings"][0]["widget_key"],"")
            self.assertEqual(d["bindings"][0]["callback_target"],None)
if __name__=="__main__": unittest.main()
