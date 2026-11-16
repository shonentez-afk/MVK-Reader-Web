"""Run: python -m unittest discover -s tests -v"""
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from idr_bridge import idp_header, decode_delphi_literal, parse_dfm, parse_source_methods, build
from mcp_server import IDRService, dispatch, tool_specs, norm_address

class StaticTests(unittest.TestCase):
    def test_delphi_strings(self):
        self.assertEqual(decode_delphi_literal("#1052#1042#1050' 1.0'"),'МВК 1.0')
        self.assertEqual(decode_delphi_literal("'Don''t'"),"Don't")
        self.assertEqual(decode_delphi_literal("CaptionGetter"),'CaptionGetter')
        self.assertEqual(decode_delphi_literal("'$'"),'$')
        self.assertEqual(decode_delphi_literal('#$041F#1056'),'ПР')
    def test_addr(self):
        self.assertEqual(norm_address('0x007d13d4'),'007D13D4')
        with self.assertRaises(ValueError): norm_address('7D13D4');
        with self.assertRaises(ValueError): norm_address('foo')

class BuildTests(unittest.TestCase):
    def setUp(self):
        self.d=tempfile.TemporaryDirectory(); self.root=Path(self.d.name)
        self.idp=self.root/'demo.idp'
        import struct
        header=b'IDR proj v.3'+struct.pack('<11I',2014,0x401000,0x400000,0x800000,0x10000,
                        0x401000,0x10000,0x1000,0x0,0x0,0x0)
        header+=struct.pack('<I',1)+struct.pack('<4I',0x401000,100,0,5)+b'.text'
        self.idp.write_bytes(header+b'\x00'*100)
        self.src=self.root/'Projects'; self.src.mkdir()
        (self.src/'_Unit1.pas').write_text('''unit _Unit1;\ninterface\nimplementation\n//00401200\nprocedure TForm1.bStartClick(Sender:TObject);\nbegin\n{*\n 00401200    mov         edx,2\n 00401205    call        00401300\n*}\nend;\n\n//00401300\n{*procedure sub_00401300(?:?);\nbegin\n 00401300    call        System.DoSomething\nend;*}\n''')
        (self.src/'Form1.dfm').write_text("""object Form1: TForm1
  Caption = #1052#1042#1050
  object bStart: TButton
    Caption = #1048#1079#1084#1077#1088#1077#1085#1080#1077
    OnClick = bStartClick
  end
end
""")
        self.db=self.root/'index.sqlite';self.out=self.root/'out'
    def tearDown(self):self.d.cleanup()
    def test_header(self):
        h=idp_header(self.idp)
        self.assertEqual(h['delphi_version'],2014)
        self.assertEqual(h['image_base'],'00400000')
        self.assertEqual(len(h['segments']),1)
    def test_bad_magic(self):
        self.idp.write_bytes(b'not IDR proj')
        with self.assertRaises(ValueError):idp_header(self.idp)
    def test_parsers(self):
        functions,calls=parse_source_methods(self.src/'_Unit1.pas','_Unit1.pas')
        self.assertEqual(functions[0]['address'],'00401200')
        self.assertEqual(functions[0]['line'],5)
        self.assertEqual(functions[1]['name'],'sub_00401300')
        self.assertEqual(calls[0]['target_address'],'00401300')
        form,components,events=parse_dfm(self.src/'Form1.dfm','Form1.dfm')
        self.assertEqual(form['name'],'Form1')
        self.assertEqual(len(components),2)
        self.assertEqual(components[1]['caption'],'Измерение')
        self.assertEqual(events[0]['handler_name'],'bStartClick')
    def test_build_and_service(self):
        b=build(self.idp,self.src,self.db,self.out)
        self.assertEqual(b['source_counts']['functions'],2)
        self.assertEqual(b['source_counts']['events_resolved'],1)
        s=IDRService(self.db,self.src)
        self.assertEqual(s.stats()['counts']['linked_calls'],1)
        self.assertEqual(s.component('bStart')['matches'][0]['caption'],'Измерение')
        self.assertEqual(s.event_chain('bStart')['chains'][0]['event']['handler_address'],'00401200')
        self.assertEqual(s.callers('00401300')['callers'][0]['caller_address'],'00401200')
        self.assertEqual(s.code('00401200')['code'][1]['text'].strip(),'procedure TForm1.bStartClick(Sender:TObject);')
        self.assertIn('tools',dispatch(s,'tools/list',{}))
        self.assertIn('serverInfo',dispatch(s,'initialize',{}))
        data=dispatch(s,'tools/call',{'name':'idr_event_chain','arguments':{'component_name':'bStart'}})
        self.assertFalse(data['isError'])
        self.assertEqual(json.loads(data['content'][0]['text'])['chains'][0]['event']['handler_name'],'bStartClick')
        self.assertTrue((self.out/'ghidra_labels.csv').exists())
        self.assertTrue((self.out/'event_handlers.csv').exists())
    def test_readonly(self):
        build(self.idp,self.src,self.db,self.out)
        srv=IDRService(self.db)
        with self.assertRaises(sqlite3.OperationalError):srv.c.execute("DROP TABLE events")
    def test_mcp_no_actions(self):
        self.assertTrue(all('click' not in t['name'] and 'attach' not in t['name'] for t in tool_specs()))

if __name__=='__main__':unittest.main()