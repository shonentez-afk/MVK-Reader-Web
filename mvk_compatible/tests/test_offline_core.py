"""Stage111 pure offline regression: synthetic data only; no network or device."""
import csv, hashlib, io, json, math, subprocess, sys, zipfile
from pathlib import Path
import numpy as np
import pytest
from mvk_compatible.core.offline_export import OfflineSession, reduce_minmax


def fixture_zip(tmp, *, aux=True, bad_bin=False, tamper_values=False,
                tamper_aux=False, sensor_alert=False,sample_count=4096):
    serial='MVK00000123'
    stamp='2026-10-29--13-32-12'
    files={}
    audit={'instrument_serial':serial,'capture_started_utc':'2026-10-29T06:32:12Z',
           'source_raw_sha256':'0'*64,'channels':[]}
    heads=['Время']; names=['hh:mm:ss.zzz']
    for ch in range(1,9):
        heads.extend([f'АЦП {ch}']*73)
        names.extend([f'Полоса {j} Гц' if j<43 else 'Статус' if j in (43,44,45)
                      else f'Параметр {j}' for j in range(73)])
    stream=io.StringIO(newline='')
    stream.write('sep=|\r\n')
    writer=csv.writer(stream,delimiter='|',lineterminator='\r\n')
    writer.writerow(heads);writer.writerow(names)
    for tick in range(2):
        row=[f'13:32:{tick:02d}.000']
        for ch in range(1,9):
            fields=[format(ch+j/10,'.4g') if j<43 else
                    format(ch+j-49,'.4g') if j>=49 else
                    str((tick+1)*(ch*100+j)/10000) for j in range(73)]
            fields[43]='0x00000000';fields[44]='0x00000000'
            fields[45]='0x00000400' if ch>=7 or (sensor_alert and ch==1) else '0x00000000'
            row.extend(fields)
        writer.writerow(row)
    files['VALUES_ALL_ADC_RECONSTRUCTED.csv']=stream.getvalue().encode('cp1251')
    files['TABLE_LAST_AUX_RECONSTRUCTED.csv']=b'sep=|\r\n'
    for ch in range(1,9):
        name=f'{serial}-ADC{ch}-{stamp}.bin'
        b=(np.sin(2*np.pi*64*np.arange(sample_count)/65536)*ch).astype('<f4').tobytes()
        files[name]=b
        audit['channels'].append({'adc':ch,'bin_sha256':hashlib.sha256(b).hexdigest()})
        xml=f'<MainRoot><Channels><Channel><RealDataType>Single</RealDataType><DataLength>{len(b)}</DataLength><DataOffset>0</DataOffset><ChannelFrequency>65536</ChannelFrequency></Channel></Channels></MainRoot>'
        files[name+'.tsxml']=xml.encode()
    if aux:
        lines=[]
        for tick in (1,2):
            for ch in range(1,9):
                lines.append(json.dumps({'update':tick,'adc':ch,
                   'third_octave_acceleration_rms':[float(ch)+j/10 for j in range(43)],
                   'band_rms':[float(ch)+j for j in range(24)],
                   'band_peak_equiv':[float(ch)+2*j for j in range(24)],
                   'band_span_equiv':[float(ch)+3*j for j in range(24)],
                   'status_hex':'0x00000400' if ch>=7 or (sensor_alert and ch==1) else '0x00000000'}))
        files['aux4700.jsonl']=('\n'.join(lines)+'\n').encode()
        files['AUX_PROVENANCE.json']=json.dumps({'source_raw_sha256':'0'*64,
            'aux4700_sha256':hashlib.sha256(files['aux4700.jsonl']).hexdigest()}).encode()
    audit['output_file_sha256']={k:hashlib.sha256(v).hexdigest() for k,v in files.items()
        if k.endswith(('.bin','.tsxml')) or k in ('VALUES_ALL_ADC_RECONSTRUCTED.csv','TABLE_LAST_AUX_RECONSTRUCTED.csv')}
    files['EXPORT_AUDIT.json']=json.dumps(audit).encode()
    if bad_bin:
        name=f'{serial}-ADC1-{stamp}.bin'
        files[name]=b'----'+files[name][4:]
    if tamper_values:files['VALUES_ALL_ADC_RECONSTRUCTED.csv']+=b'corrupt'
    if tamper_aux:files['aux4700.jsonl']+=b'{}\n'
    file=tmp/'synthetic.zip'
    with zipfile.ZipFile(file,'w',zipfile.ZIP_DEFLATED) as z:
        for k,v in files.items():z.writestr(k,v)
    return file


@pytest.fixture
def session(tmp_path):
    return OfflineSession.open(fixture_zip(tmp_path))


def test_eight_channels_and_offline_verification(session):
    result=session.verify()
    assert result['no_device_connection']
    assert result['fft_original_parity_verified'] is False
    assert result['updates']==2
    assert len(result['channels'])==8
    assert result['channels'][0]['samples']==4096
    assert result['channels'][6]['health']=='ALERT'


def test_original_aux_dsp_not_fft(session):
    d=session.calculations(0)
    assert d['source']=='MVK_DSP'
    assert d['precision']=='unrounded AUX4700'
    ch=d['channels'][2]
    assert len(ch['third_octave'])==43
    assert len(ch['parameters_24'])==24
    assert ch['third_octave'][2]['rms_m_s2']==3.2
    assert ch['parameters_24'][1]['value']==4.
    assert ch['parameters_peak_24'][1]['value']==5.
    assert ch['parameters_peak_peak_24'][1]['value']==6.
    assert d['channels'][6]['sensor_status']=='0x00000400'


def test_missing_aux_is_missing_peak_not_fake(tmp_path):
    d=OfflineSession.open(fixture_zip(tmp_path,aux=False)).calculations()
    assert d['source']=='MVK_DSP'
    assert d['precision']=='rounded VALUES CSV'
    assert d['peak_metrics_available'] is False
    assert d['channels'][0]['parameters_peak_24'] is None


def test_bin_gain_not_reapplied(session):
    signal,fs,_,_=session.samples(4)
    assert fs==65536
    assert signal[100]==pytest.approx(4*math.sin(2*math.pi*64*100/fs),rel=3e-7)


def test_waveform_and_exact_sample(session):
    wave=session.waveform(2,0,.0625,'acdc',points=128)
    assert wave['source']=='MVK_ADC_CALIBRATED_BIN'
    assert np.all(np.diff(wave['time_s'])>=0)
    assert max(wave['amplitude'])==pytest.approx(2,abs=1e-6)
    point=session.exact_sample(2,17/65536,0,.0625,'acdc')
    assert point['index']==17
    assert point['raw_bin_m_s2']==pytest.approx(2*math.sin(2*math.pi*64*17/65536))


def test_ac_is_labelled_candidate(session):
    p=session.exact_sample(1,.01,0,.0625,'ac')
    assert p['candidate_ac']
    assert p['value_m_s2']==pytest.approx(p['raw_bin_m_s2']-p['window_mean_m_s2'])


@pytest.mark.parametrize('mode',[0,1,2,3])
def test_four_fft_modes_local_candidacy(session,mode):
    d=session.spectrum(1,4096,mode,0,max_hz=1024)
    assert d['source']=='APP_DERIVED_FFT_MVKVIEW_CANDIDATE'
    assert 'НЕ' in d['warning'] or 'не доказано' in d['warning']
    assert d['df_hz']==16
    i=int(np.argmax(d['amplitude']))
    assert d['frequency_hz'][i]==pytest.approx(64)
    exact=session.exact_fft_bin(1,64,4096,mode,0)
    assert exact['bin']==4
    assert exact['frequency_hz']==64
    assert exact['value']==pytest.approx(d['amplitude'][i])


@pytest.mark.parametrize('option', ['bin','values','aux'])
def test_corruption_fail_closed(tmp_path,option):
    path=fixture_zip(tmp_path,bad_bin=option=='bin',tamper_values=option=='values',tamper_aux=option=='aux')
    if option=='values':
        with pytest.raises(ValueError,match='сумм'):OfflineSession.open(path)
    else:
        s=OfflineSession.open(path)
        with pytest.raises(ValueError,match='сумм'):
            s.samples(1) if option=='bin' else s.calculations()


def test_cursor_out_of_window_rejected(session):
    with pytest.raises(ValueError):session.exact_sample(1,4,0,.0625)
    with pytest.raises(ValueError):session.exact_fft_bin(1,32768,4096)


def test_minmax_times_not_bucket_centers():
    t,v=reduce_minmax(np.array([2.,-8.,9.,3.,-4.,6.,5.,0.]),8.,100,4)
    assert t==[101/8,102/8,104/8,105/8]
    assert v==[-8.,9.,-4.,6.]


def test_no_socket_or_fastapi_dependencies():
    import mvk_compatible.core.offline_export as m
    text=Path(m.__file__).read_text(encoding='utf-8')
    for term in ('import fastapi','from fastapi','import socket','from PySide6','uvicorn'):
        assert term not in text


def test_headless_verify_cli(tmp_path):
    file=fixture_zip(tmp_path)
    p=subprocess.run([sys.executable,'-m','mvk_compatible','--verify',str(file)],
                     text=True,capture_output=True,timeout=30)
    assert p.returncode==0,p.stderr
    d=json.loads(p.stdout)
    assert d['status']=='verified_offline_export'
    assert d['dsp_source']=='MVK_DSP'
    assert len(d['channels'])==8


def test_reject_link_file(tmp_path):
    file=fixture_zip(tmp_path)
    link=tmp_path/'linked.zip'
    try:link.symlink_to(file)
    except OSError:pytest.skip('no symlink support')
    with pytest.raises(ValueError):OfflineSession.open(link)


def test_invalid_fft_sizes_are_rejected(session):
    for n in (0,1000,4097,524288):
        with pytest.raises(ValueError):session.spectrum(1,n)
