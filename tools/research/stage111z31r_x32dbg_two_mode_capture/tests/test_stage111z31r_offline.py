"""Deterministic synthetic tests, no original MVKView, x32dbg or private data."""
from pathlib import Path
import hashlib
import importlib.util
import json
import math
import re
import struct
import tempfile
import unittest

SOURCE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('z31r_verify',SOURCE/'Verify-Capture.py')
ver=importlib.util.module_from_spec(spec)
spec.loader.exec_module(ver)


def put32(target,offset,value):
    struct.pack_into('<I',target,offset,value)


def synth_run(root,*,n=4096,end=16999,mode=2,broken_end=False,corrupt_normalized=False):
    cap=16384
    a_len=n
    b_len=n+102
    common=[]
    for i in range(b_len):
        signal=(math.sin(i*.057)+math.cos(i*.071)+.15)*.3
        common.append(struct.pack('<f',signal))
    data=b''.join(common)
    for phase,code,length in [('A',0,a_len),('B',20,b_len)]:
        p=root/phase
        p.mkdir(parents=True)
        e=end+1 if phase=='B' and broken_end else end
        window=data[-length*4:]
        if corrupt_normalized and phase=='B':
            arr=bytearray(window);arr[-32]^=0x08;window=bytes(arr)
        for field in ['pre_dc','after_dc','pre_fft','after_fft','after_y','final']:
            params=bytearray(60)
            put32(params,4,length if field in ('pre_dc','after_dc') else n)
            put32(params,8,code)
            put32(params,0x18,mode)
            put32(params,0x20,e)
            put32(params,0x28,0 if field in ('pre_dc','after_dc') else n//2)
            put32(params,0x2C,0 if field in ('pre_dc','after_dc') else (65536 if not code else 32768))
            if field=='final':
                struct.pack_into('<3f',params,0x30,3.14,20.,1.6)
            (p/('params_'+field+'.bin')).write_bytes(params)
        (p/'summary_triplet.bin').write_bytes((p/'params_final.bin').read_bytes()[0x30:0x3C])
        s=bytearray(0x38)
        put32(s,4,0x3F800000)
        put32(s,0x0C,0)
        put32(s,0x10,cap)
        put32(s,0x14,cap-1)
        put32(s,0x18,65536)
        put32(s,0x20,e)
        put32(s,0x28,0)
        put32(s,0x34,0x70000000)
        (p/'storage.bin').write_bytes(s)
        (p/'frange.bin').write_bytes(struct.pack('<f',1.0))
        first_index=(e-length)%(cap)
        first_count=min(cap-first_index,length)
        (p/'ring_head.bin').write_bytes(window[:first_count*4])
        if first_count<length:
            (p/'ring_tail.bin').write_bytes(window[first_count*4:])
        (p/'input_normalized_pre_dc.bin').write_bytes(window)
        (p/'input_after_dc.bin').write_bytes(window)
        (p/'before_fft.bin').write_bytes((window[-n*4:]))
        vals=[0.1+0.001*i for i in range(n//2)]
        vals[:2]=[0.,0.]
        power=struct.pack('<%df'%(n//2),*vals)
        (p/'power_before_mode.bin').write_bytes(power)
        (p/'power_after_mode.bin').write_bytes(power)
        (p/'display_y.bin').write_bytes(struct.pack('<%df'%(n//2),*[max(0.,x)*.75 for x in vals]))
    cfg={'schema':ver.SCHEMA,'adc_claim':4,'fft_n':n,
        'raw_sample_rate_hz':65536,'spectrum_mode':mode,'envelope_code':20}
    (root/'capture_config.json').write_text(json.dumps(cfg),encoding='utf8')


class TestStaticScript(unittest.TestCase):
    def test_resume_scripts_start_exactly_at_current_int3(self):
        for stage in ('A','B'):
            body=(SOURCE/f'RESUME_{stage}_FROM_14AA.template.txt').read_text('ascii')
            self.assertIn('cmp eip,0x007D14AA',body)
            self.assertIn('jne Z31R_FAIL_RESUME_ENTRY',body)
            self.assertIn('Z31R_FAIL_RESUME_ENTRY:',body)
            self.assertNotIn('run 0x007D14AA',body)
            self.assertIn('run 0x007D14B8',body)
            self.assertIn('run 0x007D153D',body)
            self.assertIn('run 0x007D154B',body)
            self.assertIn('run 0x007D17E7',body)
            self.assertIn('run 0x007D1900',body)
            self.assertIn('Z31R_FAIL_MEMORY',body)
            self.assertIn('Z31R_FAIL_HISTORY',body)
            self.assertIn('Z31R_FAIL_FRAME',body)
            self.assertIn('Z31R_FAIL_FILTER',body)
            self.assertIn('Z31R_FAIL_OPCODE',body)
            self.assertIn('cmp mem.base($z31r_chk_address),mem.base($z31r_chk_last)',body)
            self.assertIn('cmp dword:[$z31r_ctx_storage+0x0C],0x0',body)
            self.assertNotIn('cmp dword:[$z31r_ctx_storage+0x0C],0x1',body)
            self.assertIn('Z31R_FAIL_STORAGE_TYPE',body)
            self.assertIn('STORAGE_PROBE',body)
            self.assertIn('cmp $z31r_ctx_start,dword:[$z31r_ctx_storage+0x28]',body)
            self.assertTrue(body.isascii())
            for field in ('params_pre_dc.bin','input_normalized_pre_dc.bin',
                          'ring_head.bin','input_after_dc.bin','before_fft.bin',
                          'power_before_mode.bin','power_after_mode.bin',
                          'display_y.bin','summary_triplet.bin','params_final.bin'):
                self.assertIn('__OUT__\\'+stage+'\\'+field,body)
            labels={x[:-1] for x in body.splitlines() if x.endswith(':') and x.startswith('Z31R_')}
            for line in body.splitlines():
                m=re.match(r'^(?:j[a-z]+|call) (Z31R_[A-Z_]+)$',line)
                if m:
                    self.assertIn(m.group(1),labels,'unresolved script label '+m.group(1))

    def test_no_cross_mode_wait_inside_running_script(self):
        a=(SOURCE/'RESUME_A_FROM_14AA.template.txt').read_text('ascii')
        b=(SOURCE/'RESUME_B_FROM_14AA.template.txt').read_text('ascii')
        arm=(SOURCE/'ARM_B_ONLY.template.txt').read_text('ascii')
        self.assertNotIn('msg "PLAIN capture',a)
        self.assertNotIn('Z31R_B_WAIT',a)
        self.assertNotIn('Z31R_A_WAIT',b)
        self.assertIn('Z31R_A_SAVED',a)
        self.assertIn('Z31R_BOTH_COMPLETE',b)
        self.assertIn('SaveLog "__OUT__\\capture_log_a_snapshot.txt"',a)
        self.assertIn('SaveLog "__OUT__\\capture_log_b_snapshot.txt"',b)
        self.assertIn('bp 0x007D14AA, Z31R_ENVELOPE_CODE20',arm)
        self.assertIn('bpcond 0x007D14AA, "dword:[ebx+8]==0x14"',arm)
        self.assertNotIn('bpc 0x007D14AA',b)
        self.assertIn('do NOT require a breakpoint to exist',b)
        self.assertNotIn('run ',arm)
        self.assertNotIn('savedata ',arm)

    def test_resume_b_never_clears_nonexistent_breakpoint(self):
        b=(SOURCE/'RESUME_B_FROM_14AA.template.txt').read_text('ascii')
        start=b.index('cmp eip,0x007D14AA')
        first_run=b.index('run 0x007D14B8')
        self.assertNotIn('bpc ', b[start:first_run])
        self.assertNotIn('bc ', b[start:first_run])
        self.assertNotIn('bpcond ', b[start:first_run])
        self.assertIn('cmp dword:[ebx+8], __ENV_HEX__', b[start:first_run])
        self.assertIn('jne Z31R_FAIL_FILTER', b[start:first_run])

    def test_local_existing_run_patcher_is_fail_closed(self):
        s=(SOURCE/'Fix-Existing-B.ps1').read_text('utf-8')
        for check in ('Z31R_', 'RESUME_B_FROM_14AA.txt',
                      'bpc 0x007D14AA', 'RESUME_B_FROM_14AA.v13.backup.txt',
                      'script_b_sha256', 'RESUME_B', 'Get-FileHash'):
            self.assertIn(check,s)
        self.assertNotIn('Start-Process',s)
        self.assertNotIn('x32dbg.exe',s)
        self.assertNotIn('run 0x',s)

    def test_all_original_signatures_verified_before_capture(self):
        for stage in ('A','B'):
            s=(SOURCE/f'RESUME_{stage}_FROM_14AA.template.txt').read_text('ascii')
            pre=s.split('cmp eip,0x007D14AA')[0]
            for addr,signature in [('007D14AA',['8B','4B','04']),('007D14B8',['8B','43','08']),
                                   ('007D153D',['8B','4B','04']),('007D154B',['8B','43','28']),
                                   ('007D17E7',['33','C0']),('007D1900',['33','C0'])]:
                a=int(addr,16)
                for i,byte in enumerate(signature):
                    self.assertIn(f'cmp byte:[0x{a+i:08X}], 0x{byte}',pre)

    def test_readonly_preflight_no_run_or_savedata(self):
        s=(SOURCE/'CHECK_READY.template.txt').read_text('ascii')
        self.assertNotIn('run 0x',s)
        self.assertNotIn('savedata ',s)
        self.assertIn('Z31R_READY_OK',s)

    def test_ps5_generator_uses_new_resume_files_and_preserves_unique_paths(self):
        s=(SOURCE/'Prepare-Capture.ps1').read_text('utf8')
        for k in ('NewGuid','New-Item -ItemType Directory','__HALF_N_HEX__',
                  'ConvertTo-Json','-Encoding UTF8','Get-FileHash','ArchiveBin',
                  'RESUME_A_FROM_14AA.txt','RESUME_B_FROM_14AA.txt','ARM_B_ONLY.txt'):
            self.assertIn(k,s)
        self.assertNotIn("Load-Template 'CAPTURE_BOTH.template.txt'",s)
        self.assertNotIn("Write-Host 'CAPTURE_BOTH:'",s)

    def test_no_original_data_or_hardcoded_output_dumps(self):
        a=(SOURCE/'RESUME_A_FROM_14AA.template.txt').read_bytes()
        b=(SOURCE/'RESUME_B_FROM_14AA.template.txt').read_bytes()
        self.assertNotIn(b'mvkview.idp',a+b)
        self.assertNotIn(b'Projects.7z',a+b)
        self.assertNotIn(b'0x43FF4853',a+b)

class TestSyntheticReceipt(unittest.TestCase):
    def test_real_ring_wrap_and_normalized_overlap_pair(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);synth_run(root)
            report=ver.verify(root)
            self.assertTrue(report['capture_files_and_parameters_verified'])
            self.assertEqual(report['result'],'TWO_CAPTURE_FILES_VALID_SAME_END_AND_SAMPLES')
            self.assertTrue(report['shared_original_ring_raw_tail_float32_bitwise_equal'])
            self.assertTrue(report['spectra']['plain']['ring_wrapped'])
            self.assertTrue(report['spectra']['envelope']['ring_wrapped'])
            self.assertFalse(report['original_and_native_bin_same_window_independently_verified'])
            self.assertFalse(report['x32dbg_marker_text_present'])
    def test_split_logs_prove_both_markers_only_when_both_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);synth_run(root)
            (root/'capture_log_a_snapshot.txt').write_text('Z31R_A_COMPLETE\nZ31R_A_SAVED\n')
            self.assertFalse(ver.verify(root)['x32dbg_marker_text_present'])
            (root/'capture_log_b_snapshot.txt').write_text('Z31R_B_COMPLETE\nZ31R_BOTH_COMPLETE\n')
            self.assertTrue(ver.verify(root)['x32dbg_marker_text_present'])

    def test_wrong_end_is_valid_single_capture_but_not_pair(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);synth_run(root,broken_end=True)
            r=ver.verify(root)
            self.assertEqual(r['result'],'TWO_CAPTURE_FILES_VALID_BUT_NOT_SAME_WINDOW')
            self.assertFalse(r['original_source_end_same_between_modes'])
    def test_same_end_changed_samples_not_same_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);synth_run(root,corrupt_normalized=True)
            r=ver.verify(root)
            self.assertEqual(r['result'],'TWO_CAPTURE_FILES_VALID_BUT_NOT_SAME_WINDOW')
            self.assertFalse(r['shared_normalized_raw_tail_float32_bitwise_equal'])
    def test_original_summary_must_be_physical_12_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);synth_run(root)
            f=root/'B'/'summary_triplet.bin';f.write_bytes(b'badbadbadbad')
            with self.assertRaisesRegex(ValueError,'triplet'):
                ver.verify(root)
    def test_truncated_y_refuses_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);synth_run(root)
            f=root/'A'/'display_y.bin';f.write_bytes(f.read_bytes()[:-4])
            with self.assertRaisesRegex(ValueError,'wrong file length'):
                ver.verify(root)
    def test_wrong_channel_claim_bool_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);synth_run(root)
            p=root/'capture_config.json';c=json.loads(p.read_text());c['adc_claim']=True;p.write_text(json.dumps(c))
            with self.assertRaisesRegex(ValueError,'adc_claim'):
                ver.verify(root)
    def test_nonfinite_source_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);synth_run(root)
            p=root/'B'/'before_fft.bin';b=bytearray(p.read_bytes());struct.pack_into('<f',b,16,float('nan'));p.write_bytes(b)
            with self.assertRaisesRegex(ValueError,'nonfinite'):
                ver.verify(root)
    def test_unknown_schema_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);synth_run(root)
            p=root/'capture_config.json';cfg=json.loads(p.read_text());cfg['schema']='BOGUS';p.write_text(json.dumps(cfg))
            with self.assertRaisesRegex(ValueError,'version'):
                ver.verify(root)
    def test_missing_ring_tail_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);synth_run(root)
            (root/'A'/'ring_tail.bin').unlink()
            with self.assertRaisesRegex(ValueError,'incomplete ring wrap tail'):
                ver.verify(root)
    def test_mismatched_f_range_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);synth_run(root)
            (root/'A'/'frange.bin').write_bytes(struct.pack('<f',510.))
            with self.assertRaisesRegex(ValueError,'FRange'):
                ver.verify(root)

    def test_source_verified_storage_float_code_zero_and_wrong_enum_fail_closed(self):
        # Original _Unit115 Create has Float32 code0, byte code2; neither 1 nor 2
        # is a Float32 ring. A passing synthetic test must use actual code0.
        for code in (1,2,3):
            with self.subTest(code=code), tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);synth_run(root)
                s=root/'B'/'storage.bin';data=bytearray(s.read_bytes())
                put32(data,0x0C,code);s.write_bytes(data)
                with self.assertRaisesRegex(ValueError,'storage type/RAW Fs mismatch'):
                    ver.verify(root)

    def test_package_type_guard_matches_original_assembly(self):
        for stage in ('A','B'):
            body=(SOURCE/f'RESUME_{stage}_FROM_14AA.template.txt').read_text('ascii')
            self.assertIn('cmp dword:[$z31r_ctx_storage+0x0C],0x0',body)
            self.assertIn('Z31R_FAIL_STORAGE_TYPE:',body)
            self.assertNotIn('not 1 (float ring)',body)
        source=(SOURCE/'Verify-Capture.py').read_text('utf-8')
        self.assertIn('u32(storage,0x0C)!=0',source)
        self.assertNotIn('u32(storage,0x0C)!=1',source)

if __name__=='__main__':
    unittest.main()
