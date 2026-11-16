"""Offline contract for opt-in x86 Frida mode. No original app or hook runs."""
from __future__ import annotations
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import queue
import struct
import tempfile
import unittest
import time

from capture_agent.config import CaptureConfig, CaptureError
from capture_agent.frida_trace import FridaTraceObserver, SITES, image_identity, javascript_source
from capture_agent.session import CaptureSession, CaptureService
from test_capture_agent import FakeWindows


def make_exe(folder: Path, *, arch=0x14c, base=0x00400000):
    f=folder / 'mvkview.exe'
    data=bytearray(2048)
    data[:2]=b'MZ'
    struct.pack_into('<I',data,0x3C,0x80)
    data[0x80:0x84]=b'PE\0\0'
    struct.pack_into('<H',data,0x84,arch)
    struct.pack_into('<H',data,0x98,0x10B)
    struct.pack_into('<I',data,0x98+28,base)
    f.write_bytes(data)
    return f


class FakeScript:
    def __init__(self,source,kind='ready'):
        self.source=source
        self.kind=kind
        self.callback=None
        self.unloaded=False
    def on(self,event,callback):
        assert event=='message'
        self.callback=callback
    def load(self):
        if self.kind=='ready':
            self.callback({'type':'send','payload':{'kind':'ready','architecture':'ia32','hook_count':6}},None)
        else:
            self.callback({'type':'send','payload':{'kind':'trace_error','reason':'opcode mismatch'}},None)
    def unload(self):
        self.unloaded=True

class FakeFridaSession:
    def __init__(self,kind):
        self.kind=kind
        self.script=None
        self.detached=False
    def create_script(self,source):
        self.script=FakeScript(source,self.kind)
        return self.script
    def detach(self):
        self.detached=True

class FakeFrida:
    def __init__(self,kind='ready'):
        self.kind=kind
        self.pid=None
        self.session=None
    def attach(self,pid):
        self.pid=pid
        self.session=FakeFridaSession(self.kind)
        return self.session

class FakeTrace:
    def __init__(self,pid,output,exe_path,*,full_arrays=False):
        self.output=output
        self.dropped=0
        self.full_arrays=full_arrays
        self.stopped=False
    def start(self):
        self.output.put_nowait({'source':'frida','payload':{
            'kind':'hit','site':'pre_dc','n':262144,'mode':0},'binary':None})
        self.output.put_nowait({'source':'frida','payload':{
            'kind':'array','site':'pre_fft','array_type':'pre_fft_float32_candidate',
            'byte_length':16,'n':4096},'binary':b'1234567890abcdef'})
        return {'sites':6,'exe_sha256':'a'*64,'arrays':self.full_arrays}
    def stop(self):
        self.stopped=True

class FridaContractTests(unittest.TestCase):
    def test_fixed_six_source_checked_sites_and_no_arbitrary_hook_input(self):
        self.assertEqual(len(SITES),6)
        self.assertEqual([hex(x.original_va) for x in SITES], [
            '0x7d14aa','0x7d14b8','0x7d153d','0x7d154b','0x7d17e7','0x7d1900'])
        js=javascript_source(full_arrays=False)
        self.assertIn('Interceptor.attach',js)
        self.assertIn('Original x86 opcode mismatch',js)
        self.assertIn('"signature":"8b4b04"',js)
        self.assertIn('const ALLOW_ARRAYS = false',js)
        self.assertNotIn('Memory.write',js)
        self.assertNotIn('Process.spawn',js)
        js2=javascript_source(full_arrays=True)
        self.assertIn('const ALLOW_ARRAYS = true',js2)
    def test_pe_x86_identity_and_rejection(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            file=make_exe(root)
            self.assertEqual(image_identity(file)['exe_sha256'],hashlib.sha256(file.read_bytes()).hexdigest())
            make_exe(root,arch=0x8664)
            with self.assertRaises(CaptureError): image_identity(file)
            make_exe(root,base=0x14000000)
            with self.assertRaises(CaptureError): image_identity(file)
    def test_frida_ready_and_rejected_scripts(self):
        with tempfile.TemporaryDirectory() as d:
            file=make_exe(Path(d))
            for kind in ('ready','error'):
                with self.subTest(kind=kind):
                    fake=FakeFrida(kind)
                    out=queue.Queue()
                    agent=FridaTraceObserver(1234,out,str(file),frida_module=fake)
                    if kind=='ready':
                        info=agent.start()
                        self.assertEqual(info['sites'],6)
                        agent._message({'type':'send','payload':{'kind':'hit','site':'pre_dc','n':4096,'secret':'do not store'}},None)
                        self.assertNotIn('secret',out.get_nowait()['payload'])
                        agent._message({'type':'send','payload':{'kind':'array','site':'pre_fft','array_type':'pre_fft_float32_candidate'}},b'X'*(1024*1024+1))
                        self.assertEqual(agent.dropped,1)
                        agent.stop()
                    else:
                        with self.assertRaises(CaptureError): agent.start()
                    self.assertTrue(fake.session.detached)
    def test_trace_requires_separate_consent(self):
        with tempfile.TemporaryDirectory() as d:
            conf=Path(d)/'trace.json'
            conf.write_text(json.dumps({'output_dir':str(Path(d)/'out'),
                                        'auto_trace':True,'trace_arrays':False}))
            svc=CaptureService(backend=FakeWindows())
            with self.assertRaisesRegex(CaptureError,'acknowledge_instrumentation'):
                svc.start(config_path=str(conf),acknowledge_local_capture=True)
            self.assertEqual(svc.status()['status'],'idle')
            bad=Path(d)/'bad.json'
            bad.write_text(json.dumps({'trace_arrays':True}))
            with self.assertRaises(CaptureError): CaptureConfig.load(bad)
    def test_trace_evidence_kept_local_and_hashed(self):
        with tempfile.TemporaryDirectory() as d:
            config=replace(CaptureConfig.defaults(),output_dir=Path(d),auto_trace=True,trace_arrays=True)
            sess=CaptureSession(config,FakeWindows(),FakeWindows().target,tracer_factory=FakeTrace)
            sess.start()
            time.sleep(0.2)
            result=sess.stop()
            self.assertEqual(result['frida_trace_events'],2)
            self.assertTrue(sess.tracer.stopped)
            events=(sess.store.path/'timeline.jsonl').read_text()
            self.assertIn('pre_fft_float32_candidate',events)
            self.assertIn(hashlib.sha256(b'1234567890abcdef').hexdigest(),events)
            self.assertEqual(len(list((sess.store.path/'memory').glob('*.bin'))),1)
            meta=json.loads((sess.store.path/'session.json').read_text())
            self.assertTrue(meta['safety']['frida_runtime_code_interception'])
            zipinfo=sess.store.export()
            self.assertTrue(Path(zipinfo['zip']).is_file())

if __name__=='__main__': unittest.main()