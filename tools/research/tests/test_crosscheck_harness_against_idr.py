"""Synthetic tests only; no original MVK binaries or Delphi sources are bundled."""
import importlib.util
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

MODULE_PATH=Path(__file__).resolve().parents[1]/'crosscheck_harness_against_idr.py'
spec=importlib.util.spec_from_file_location('crosscheck_harness_against_idr',MODULE_PATH)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class ReconcileTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory()
  self.addCleanup(self.temp.cleanup)
  root=Path(self.temp.name)
  self.db=root/'fixture.sqlite';self.pas=root/'pas';self.pas.mkdir()
  c=sqlite3.connect(self.db)
  c.executescript('''CREATE TABLE functions (address TEXT PRIMARY KEY,name TEXT,unit TEXT);
       CREATE TABLE calls (caller_address TEXT,site_address TEXT,raw_target TEXT,target_name TEXT,resolved_address TEXT);
       CREATE TABLE events (component_path TEXT,event_name TEXT,handler_name TEXT,handler_address TEXT);''')
  c.execute('INSERT INTO functions VALUES(?,?,?)',('00401000','TExample.Start','_Unit128.pas'))
  c.execute('INSERT INTO calls VALUES(?,?,?,?,?)',('00401000','00401005','00401050',None,'00401050'))
  c.execute('INSERT INTO events VALUES(?,?,?,?)',('form/bTaskConnect','OnClick','Start','00401000'))
  c.commit();c.close()
  (self.pas/'_Unit128.pas').write_text(' //00401000\n  00401000    mov     edx,2\n  00401005    call    00401050\n  00401007    ret\n',encoding='utf-8')
  self.evidence=root/'evidence.json'
  self.evidence.write_text(json.dumps({'address_availability_audit':{'results':[
     {'address':'00401000','found':False},{'address':'00401005','found':False},
     {'address':'00401055','found':False},{'address':'00402000','found':True}]}},indent=2),encoding='utf-8')
 def test_three_way_reconciliation(self):
  r=mod.crosscheck(self.db,self.evidence,self.pas)
  self.assertEqual(r['totals'],{'addresses_audited':4,'ghidra_false':3,'false_but_idr_entry':1,'false_but_pas_instruction':1,'false_unresolved':1})
  self.assertEqual(len(r['dfm_event_links']),1)
  self.assertIn('GHIDRA_UNDEFINED_BUT_SOURCE_INSTRUCTION',[x['classification'] for x in r['audit']])
 def test_without_pas_sources_is_conservative(self):
  r=mod.crosscheck(self.db,self.evidence)
  self.assertEqual(r['totals']['false_but_pas_instruction'],0)
  self.assertEqual(r['totals']['false_unresolved'],2)
 def test_reject_malformed_addresses(self):
  self.evidence.write_text(json.dumps({'address_availability_audit':{'results':[{'address':'\\0x401000','found':False}]}}),encoding='utf-8')
  with self.assertRaises(ValueError):mod.crosscheck(self.db,self.evidence,self.pas)
 def test_db_is_readonly(self):
  before=self.db.read_bytes()
  mod.crosscheck(self.db,self.evidence,self.pas)
  self.assertEqual(before,self.db.read_bytes())

if __name__=='__main__':unittest.main()