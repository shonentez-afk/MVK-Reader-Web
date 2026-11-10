from __future__ import annotations
import io
import unittest
import zipfile
import numpy as np
from tools.research.verify_stage111z31ae_fir_input import check


class TestMVKFIRRawInput(unittest.TestCase):
    @staticmethod
    def fixtures():
        rng=np.random.default_rng(5523)
        b=rng.uniform(-80,-1,4096).astype('<f4')
        fr=np.frombuffer(bytes.fromhex('5348ff43'),dtype='<f4')[0]
        raw=np.asarray(b[1024:1024+115]/fr,dtype='<f4')
        z=io.BytesIO()
        with zipfile.ZipFile(z,'w') as archive:
            archive.writestr('input_normalized_pre_dc.bin',raw[5:].tobytes())
        return raw.tobytes(),b.tobytes(),z.getvalue()

    def test_unique_match(self):
        a,b,z=self.fixtures()
        r=check(a,b,z,raw_n=115,extra_taps=5,expected_end=1139)
        self.assertEqual(r['status'],'FULL_PHYSICAL_ADC1_AND_PREVIOUS_LOG_BITWISE_PASS')
        self.assertEqual(r['normalized_bin_unique_matches'],[1024])
        self.assertEqual(r['log_overlap_samples_exact'],110)

    def test_false_end_rejected(self):
        a,b,z=self.fixtures()
        self.assertEqual(check(a,b,z,raw_n=115,extra_taps=5,expected_end=1000)['status'],'REJECT')

    def test_modified_work_rejected(self):
        a,b,z=self.fixtures()
        changed=bytearray(a);changed[17]^=1
        self.assertEqual(check(bytes(changed),b,z,raw_n=115,extra_taps=5,expected_end=1139)['status'],'REJECT')

    def test_changed_log_rejected(self):
        a,b,z=self.fixtures()
        data=bytearray(a[20:]);data[1]^=1
        zz=io.BytesIO()
        with zipfile.ZipFile(zz,'w') as archive:
            archive.writestr('input_normalized_pre_dc.bin',data)
        self.assertEqual(check(a,b,zz.getvalue(),raw_n=115,extra_taps=5,expected_end=1139)['status'],'REJECT')

    def test_short_data_raises(self):
        a,b,z=self.fixtures()
        with self.assertRaisesRegex(ValueError,'length'):
            check(a[:-4],b,z,raw_n=115,extra_taps=5,expected_end=1139)

    def test_wrong_f_range_rejected(self):
        a,b,z=self.fixtures()
        self.assertEqual(check(a,b,z,raw_n=115,extra_taps=5,expected_end=1139,
                               frange_bits=0x3f800000)['status'],'REJECT')

    def test_nonfinite_raises(self):
        a,b,z=self.fixtures()
        changed=bytearray(a);changed[:4]=bytes.fromhex('0000c07f')
        with self.assertRaisesRegex(ValueError,'NaN'):
            check(bytes(changed),b,z,raw_n=115,extra_taps=5,expected_end=1139)

    def test_bad_zip_raises(self):
        a,b,z=self.fixtures()
        with self.assertRaises(zipfile.BadZipFile):
            check(a,b,b'fake',raw_n=115,extra_taps=5,expected_end=1139)


if __name__=='__main__':
    unittest.main()
