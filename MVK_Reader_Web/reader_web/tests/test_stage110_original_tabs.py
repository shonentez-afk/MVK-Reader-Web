"""Standalone synthetic QA. Does NOT require the user's industrial archives."""
import csv
import hashlib
import io
import json
import math
import os
import tempfile
import unittest
import zipfile
import sys
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] if Path(__file__).parent.name=='tests' else Path(__file__).parent))

from stage110_original_tabs import (
    app, calculated_for_zip, waveform_for_zip, spectrum_for_zip,
    permitted_archives, require_members, read_values,
)


def make_fixture(folder: Path, *, with_aux=True, wrong_provenance=False,
                 corrupt_bin=False, limited=True) -> Path:
    path = folder/'STAGE110_SYNTHETIC.zip'
    serial = 'MVK00000123'
    names = [f'{serial}-ADC{i}-2026-10-29--13-32-12.bin' for i in range(1,9)]
    metadata = {'instrument_serial': serial, 'source_raw_sha256': '0'*64,
                'channels': [], 'capture_started_utc': '2026-10-29T06:32:12Z'}
    header1=['Время']
    header2=['hh:mm:ss.zzz']
    for i in range(1,9):
        header1 += [f'АЦП {i}']*73
        header2 += [f'Полоса {i} Гц' if k<43 else 'Статус' if k in (43,44,45) else f'Параметр {k}' for k in range(73)]
    def csv_bytes():
        stream=io.StringIO(newline='')
        stream.write('sep=|\r\n')
        writer=csv.writer(stream,delimiter='|',lineterminator='\r\n')
        writer.writerow(header1);writer.writerow(header2)
        for tick in (0,1):
            row=[f'13:32:{tick:02d}.000']
            for channel in range(1,9):
                fields=[format(channel+k/10,'.4g') if k<43 else format(channel+k-49,'.4g') if 49<=k<=72 else str((tick+1)*(channel*100+k)/10000) for k in range(73)]
                fields[43]='0x00000000';fields[44]='0x00000000'
                fields[45]='0x00000400' if channel>=7 else '0x00000000'
                row.extend(fields)
            writer.writerow(row)
        return stream.getvalue().encode('cp1251')
    items = {}
    for i,name in enumerate(names,1):
        signal=(np.sin(2*np.pi*64*np.arange(4096)/65536)*i).astype('<f4')
        data=signal.tobytes()
        digest=hashlib.sha256(data).hexdigest()
        metadata['channels'].append({'adc':i,'bin_sha256':digest})
        if corrupt_bin and i==1:
            data=data[:-4]+b'1234'
        xml=(f'<MainRoot><Channels><Channel><RealDataType>Single</RealDataType>'
             f'<DataLength>{len(data)}</DataLength><DataOffset>0</DataOffset>'
             f'<ChannelFrequency>65536</ChannelFrequency></Channel></Channels></MainRoot>')
        items[name]=data
        items[name+'.tsxml']=xml.encode('utf-8')
    items['VALUES_ALL_ADC_RECONSTRUCTED.csv']=csv_bytes()
    items['TABLE_LAST_AUX_RECONSTRUCTED.csv']=b'sep=|\r\n'
    if with_aux:
        lines=[]
        for tick in (1,2):
            for ch in range(1,9):
                fields={'adc':ch,'update':tick,
                        'third_octave_acceleration_rms':[float(ch)+k/10 for k in range(43)],
                        'band_rms':[float(ch)+k for k in range(24)],
                        'band_peak_equiv':[float(ch)+2*k for k in range(24)],
                        'band_span_equiv':[float(ch)+3*k for k in range(24)],
                        'status_hex': '0x00000400' if ch>=7 else '0x00000000'}
                lines.append(json.dumps(fields))
        items['aux4700.jsonl']=('\n'.join(lines)+'\n').encode()
        items['AUX_PROVENANCE.json']=json.dumps({'source_raw_sha256':'1'*64 if wrong_provenance else '0'*64,
            'aux4700_sha256':hashlib.sha256(items['aux4700.jsonl']).hexdigest()}).encode()
    metadata['output_file_sha256']={name:hashlib.sha256(data).hexdigest() for name,data in items.items()
        if name.endswith(('.bin','.tsxml')) or name in ('VALUES_ALL_ADC_RECONSTRUCTED.csv','TABLE_LAST_AUX_RECONSTRUCTED.csv')}
    items['EXPORT_AUDIT.json']=json.dumps(metadata).encode()
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for name,data in items.items():z.writestr(name,data)
    return path


class Stage110ThreeTabTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder=Path(self.temp.name)
        self.path=make_fixture(self.folder)
        self.env=patch.dict(os.environ,{'MVK_STAGE110_SESSIONS_DIR':self.temp.name})
        self.env.start();self.addCleanup(self.env.stop)
        self.client=TestClient(app)

    def test_sessions_and_offline_read_only(self):
        response=self.client.get('/api/stage110/sessions')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['mode'],'OFFLINE_READ_ONLY')
        self.assertEqual(len(response.json()['sessions']),1)
        self.assertEqual(self.client.post('/api/stage110/sessions').status_code,405)
        self.assertEqual(self.client.get('/').status_code,200)
        self.assertIn('Расчётные данные',self.client.get('/').text)

    def test_all_channels_native_rms_peak_span_status(self):
        r=self.client.get('/api/stage110/sessions/STAGE110_SYNTHETIC/calculated?tick=0')
        self.assertEqual(r.status_code,200,r.text)
        d=r.json()
        self.assertEqual(len(d['channels']),8)
        self.assertTrue(d['peak_metrics_available'])
        self.assertEqual(d['updates'],2)
        self.assertEqual(len(d['channels'][0]['third_octave']),43)
        self.assertEqual(len(d['channels'][0]['parameters_24']),24)
        self.assertEqual(d['channels'][2]['parameters_24'][1]['value'],4.)
        self.assertEqual(d['channels'][2]['parameters_peak_24'][1]['value'],5.)
        self.assertEqual(d['channels'][6]['sensor_status'],'0x00000400')
        self.assertEqual(d['channels'][6]['health'],'ALERT')
        self.assertIn('HOST_CLOCK',d['time_kind'])
        self.assertEqual(d['source'],'MVK_DSP')

    def test_rounded_values_do_not_imply_fake_peak(self):
        make_fixture(self.folder,with_aux=False)
        d=calculated_for_zip(self.path)
        self.assertFalse(d['peak_metrics_available'])
        self.assertIsNone(d['channels'][0]['parameters_peak_24'])
        self.assertEqual(d['precision'],'rounded VALUES CSV')

    def test_forged_aux_provenance_fail_closed(self):
        make_fixture(self.folder,wrong_provenance=True)
        r=self.client.get('/api/stage110/sessions/STAGE110_SYNTHETIC/calculated')
        self.assertEqual(r.status_code,422)
        self.assertIn('другому RAW',r.text)

    def test_waveform_ac_and_acdc(self):
        a=waveform_for_zip(self.path,2,0,0.0625,'acdc',1000)
        b=waveform_for_zip(self.path,2,0,0.0625,'ac',1000)
        self.assertEqual(a['window_samples'],4096)
        self.assertEqual(a['sample_rate_hz'],65536)
        self.assertEqual(len(a['amplitude']),len(a['time_s']))
        self.assertEqual(a['source'],'MVK_ADC_CALIBRATED_BIN')
        self.assertAlmostEqual(a['rms_m_s2'],b['rms_m_s2'],delta=.01)
        self.assertLess(abs(b['mean_m_s2']),0.01)
        self.assertGreater(max(a['amplitude']),1.9)

    def test_bin_sha256_corruption_is_rejected(self):
        make_fixture(self.folder,corrupt_bin=True)
        r=self.client.get('/api/stage110/sessions/STAGE110_SYNTHETIC/waveform?channel=1&seconds=0.04')
        self.assertEqual(r.status_code,422)
        self.assertIn('контрольная сумма',r.text)

    def test_four_local_fft_modes_not_dsp(self):
        for mode in range(4):
            d=spectrum_for_zip(self.path,1,4096,mode,max_hz=1000,max_points=1000)
            self.assertEqual(d['mode'],mode)
            self.assertEqual(d['df_hz'],16)
            self.assertIn('APP_DERIVED',d['source'])
            self.assertGreater(max(d['amplitude']),-181)
            index=int(np.argmax(d['amplitude']))
            self.assertLess(abs(d['frequency_hz'][index]-64),.1)
        self.assertEqual(spectrum_for_zip(self.path,1,4096,0)['mode_name'],'Логарифмич.')

    def test_no_spectrum_window_outside_data(self):
        r=self.client.get('/api/stage110/sessions/STAGE110_SYNTHETIC/spectrum?channel=2&n_fft=8192')
        self.assertEqual(r.status_code,422)
        self.assertIn('Не хватает данных',r.text)
        r=self.client.get('/api/stage110/sessions/STAGE110_SYNTHETIC/spectrum?n_fft=1234')
        self.assertEqual(r.status_code,422)

    def test_path_bypass_and_empty_session(self):
        self.assertEqual(self.client.get('/api/stage110/sessions/..%2F..%2Fetc/calculated').status_code,404)
        self.assertEqual(self.client.get('/api/stage110/sessions/unlisted/calculated').status_code,404)
        self.assertEqual(self.client.get('/api/stage110/sessions/STAGE110_SYNTHETIC/calculated?tick=9').status_code,422)

    def test_protected_original_files_not_exposed(self):
        html_path=Path(__file__).with_name('stage110_original_tabs.html')
        if not html_path.is_file():html_path=Path(__file__).parents[1]/'static'/'stage110_original_tabs.html'
        html=html_path.read_text(encoding='utf-8')
        code_path=Path(__file__).with_name('stage110_original_tabs.py')
        if not code_path.is_file():code_path=Path(__file__).parents[1]/'stage110_original_tabs.py'
        code=code_path.read_text(encoding='utf-8')
        self.assertNotIn('socket.connect',code)
        self.assertNotIn('TCP/502',code)
        self.assertNotIn('Modbus.write',code)
        self.assertNotIn('10.13.42.',html)
        self.assertIn('Графический FFT',html)


if __name__=='__main__':unittest.main()
