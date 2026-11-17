"""Synthetic-only tests; no private MVKView source or hardware in repository."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import sqlite3
import tempfile
import unittest

MODULE_PATH=Path(__file__).with_name('verify_mvk_measurement_evidence_v2.py')
spec=importlib.util.spec_from_file_location('mvk_evidence_v2_check',MODULE_PATH)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class SourceEvidenceCheckerTests(unittest.TestCase):
    def test_address_parser_handles_nested_instructions(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'_Unit128.pas'
            p.write_text('''//0084F7C8\n 0084F7C8    call        00847248\n>0084FB10    jne         0084FB57\n 0084FB2D    call        TThread.Synchronize\n''')
            entries=mod.insn_map(p)
            self.assertEqual(entries['0084F7C8'],'call        00847248')
            self.assertEqual(entries['0084FB10'],'jne         0084FB57')
            self.assertEqual(entries['0084FB2D'],'call        TThread.Synchronize')
    def test_read_only_sqlite_cannot_mutate(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'test.sqlite'
            with sqlite3.connect(p) as c:
                c.execute('CREATE TABLE t(v TEXT)')
            with mod.connect_read_only(p) as c:
                with self.assertRaises(sqlite3.OperationalError):
                    c.execute("INSERT INTO t(v) VALUES ('x')")
                self.assertEqual(c.execute('SELECT COUNT(*) FROM t').fetchone()[0],0)
    def test_source_checks_and_caller_rules_are_unique(self):
        sites=[(fname,addr) for fname,addr,*_ in mod.INSNS]
        self.assertEqual(len(sites),len(set(sites)))
        self.assertEqual(mod.EXPECTED_CALLERS['0084FB03'],'0084FA6C')
        self.assertEqual(mod.EXPECTED_CALLERS['00809375'],'00809364')
        self.assertEqual(mod.EXPECTED_FUNCTIONS['00848E84'],'Tmvkform.bTaskViewClick')

if __name__=='__main__':unittest.main()