"""Read-only literal address evidence test; not original IDR or device access."""
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
from mvk_stage111_address_refs import analyze

class AddressRefsTest(unittest.TestCase):
    def test_function_scoping_and_address_exactness(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);d=root/"mvk_compatible/core";d.mkdir(parents=True)
            (d/"example.py").write_text(
                "class Receiver:\n"
                " def read(self):\n"
                "  # Original source 00807A98; check 0x007D13D4\n"
                "  return '00807A981' # invalid longer hex\n",
                encoding="utf-8")
            o=analyze(root,"s")
            items=[x for x in o["references"] if x["address"] in ("00807A98","007D13D4")]
            self.assertEqual(len(items),2)
            self.assertTrue(all(x["owner"]=="Receiver.read" for x in items))
            self.assertTrue(all("#L" in x["url"] for x in items))
            self.assertEqual(o["counts"]["unique_addresses"],2)
    def test_arbitrary_large_hex_is_not_original_address(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);d=root/"mvk_compatible/desktop";d.mkdir(parents=True)
            (d/"x.py").write_text("v='abcdef120084E988ffff0000'\n",encoding="utf-8")
            o=analyze(root,"s")
            self.assertEqual(o["counts"]["address_mentions"],0)

if __name__=="__main__":unittest.main()
