"""Read-only checks: public LikeC4 source references must resolve locally."""
from pathlib import Path
import re
import unittest

REPO=Path(__file__).resolve().parents[2]
MODEL=REPO/"docs/architecture/mvkview-recovery/likec4/model.c4"
VIEWS=MODEL.with_name("views.c4")
LINK=re.compile(r"^\s*link\s+https://github\.com/shonentez-afk/MVK-Reader-Web/blob/([0-9a-f]{40})/([^\s]+)",re.M)

class LikeC4SourceContractTest(unittest.TestCase):
    def test_pinned_links_are_local_sources(self):
        text=MODEL.read_text(encoding="utf-8")
        self.assertIn("9f6a3a74535408253f883ae9b49903363c77a69d",text)
        refs=LINK.findall(text)
        self.assertGreaterEqual(len(refs),6)
        for sha,fragment in refs:
            self.assertEqual(sha,"9f6a3a74535408253f883ae9b49903363c77a69d")
            path,_,anchor=fragment.partition("#")
            src=REPO/path
            self.assertTrue(src.is_file(),f"Broken pinned LikeC4 source path: {path}")
            if anchor:
                self.assertRegex(anchor,r"^L\d+$")
                n=int(anchor[1:])
                self.assertLessEqual(n,len(src.read_text(encoding="utf-8",errors="replace").splitlines()))
    def test_public_only_two_model_files(self):
        text=MODEL.read_text(encoding="utf-8")
        views=VIEWS.read_text(encoding="utf-8")
        self.assertIn("specification {",text)
        self.assertIn("model {",text)
        self.assertIn("view index {",views)
        self.assertIn("view components of stage111 {",views)
        for forbidden in ("Projects.7z","mvkview.idp","mvk_idr(1).sqlite"):
            self.assertNotIn(forbidden,views)
            # Private names are mentioned only in a comment; no data or bytes are present.
            self.assertNotIn(forbidden,text)
if __name__=="__main__":unittest.main()
