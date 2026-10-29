"""Stage111C: synthetic-only QA for unfiltered original GetSignal path."""
import math
import numpy as np
import pytest
from mvk_compatible.core.signal_idr_candidate import (
    unfiltered_getsignal, read_ring_float32)
from mvk_compatible.core.offline_export import OfflineSession
from mvk_compatible.tests.test_offline_core import fixture_zip


def test_ac_delphi_nodc_and_reversed_output():
    x=np.array([2.,4.,6.,8.],dtype='f4')
    out=unfiltered_getsignal(x,65536,no_dc=True)
    np.testing.assert_array_equal(out.chronological,[-3.,-1.,1.,3.])
    np.testing.assert_array_equal(out.getsignal_buffer,[3.,1.,-1.,-3.])
    assert out.removed_mean==out.window_mean==5
    assert out.output_length==4
    assert out.rms_value==pytest.approx(math.sqrt(5),rel=1e-6)


def test_acdc_preserves_input_and_ignores_range_without_envelope():
    x=np.array([2.,4.,6.,8.],dtype='f4')
    out=unfiltered_getsignal(x,65536,no_dc=False,f_range=42.)
    np.testing.assert_array_equal(out.chronological,x)
    np.testing.assert_array_equal(out.getsignal_buffer,x[::-1])
    np.testing.assert_array_equal(x,[2.,4.,6.,8.])
    assert out.rms_value==pytest.approx(math.sqrt(30),rel=1e-6)
    assert out.removed_mean==0 and out.window_mean==5


def test_local_ac_rms_is_not_instrument_dsp():
    x=np.array([10.,12.,14.,16.],dtype='f4')
    assert unfiltered_getsignal(x,1000,no_dc=True).rms_value < unfiltered_getsignal(x,1000,no_dc=False).rms_value
    assert unfiltered_getsignal(x,1000).provenance.startswith('APP_DERIVED')


def test_mean_float32_sequential_and_reversed_f32_result():
    x=np.array([1e6,-1e6,1.25,1.375,1.5,1.625],dtype='f4')
    v=np.float32(0)
    for item in x: v=np.float32(float(v)+float(item))
    r=unfiltered_getsignal(x,65536,no_dc=True)
    assert r.window_mean==float(np.float32(float(v)/len(x)))
    assert r.chronological.dtype==r.getsignal_buffer.dtype==np.float32
    np.testing.assert_array_equal(r.getsignal_buffer,r.chronological[::-1])


def test_refuse_envelope_instead_of_fabricating():
    with pytest.raises(NotImplementedError,match='original coefficient tables'):
        unfiltered_getsignal(np.ones(1024,dtype='f4'),65536,envelope_code=1)


@pytest.mark.parametrize('rate',[0,-1,float('nan'),float('inf')])
def test_bad_sample_rate_rejected(rate):
    with pytest.raises(ValueError):unfiltered_getsignal(np.ones(4,dtype='f4'),rate)


def test_ring_wrap_and_missing_prefix():
    ring=np.array([8,9,2,3,4,5,6,7],dtype='f4')
    x=read_ring_float32(ring,rx_position=10,valid_position=4,output_length=8)
    np.testing.assert_array_equal(x,[0.,0.,4.,5.,6.,7.,8.,9.])
    o=unfiltered_getsignal(x,1000,no_dc=False)
    np.testing.assert_array_equal(o.getsignal_buffer,[9.,8.,7.,6.,5.,4.,0.,0.])


def test_ring_full_wrap():
    ring=np.array([8,9,2,3,4,5,6,7],dtype='f4')
    np.testing.assert_array_equal(read_ring_float32(ring,rx_position=10,
        valid_position=2,output_length=8),[2.,3.,4.,5.,6.,7.,8.,9.])


@pytest.mark.parametrize('rx,valid,length',[(10,0,8),(8,9,4),(8,0,9),(-1,0,3)])
def test_ring_invalid_positions_rejected(rx,valid,length):
    with pytest.raises(ValueError):read_ring_float32(np.zeros(8,dtype='f4'),
        rx_position=rx,valid_position=valid,output_length=length)


def test_ring_reject_non_power_two():
    with pytest.raises(ValueError):read_ring_float32(np.zeros(7,dtype='f4'),
        rx_position=7,valid_position=0,output_length=7)


def test_archive_two_orders_and_exact_cursor_agree(tmp_path):
    s=OfflineSession.open(fixture_zip(tmp_path))
    a=s.waveform(2,0,.0625,'ac',points=20000,display_order='chronological')
    b=s.waveform(2,0,.0625,'ac',points=20000,display_order='getsignal_buffer')
    assert a['source']==b['source']=='MVK_ADC_CALIBRATED_BIN'
    assert b['time_axis_kind']=='GETSIGNAL_RETURN_BUFFER_POSITION_NOT_ARCHIVE_TIME'
    assert a['rms_m_s2']==b['rms_m_s2']
    assert len(a['amplitude'])==len(b['amplitude'])==4096
    np.testing.assert_array_equal(a['amplitude'],b['amplitude'][::-1])
    time=31/65536
    ca=s.exact_sample(2,time,0,.0625,'ac','chronological')
    cb=s.exact_sample(2,time,0,.0625,'ac','getsignal_buffer')
    assert ca['index']==31 and cb['index']==4096-1-31
    assert ca['display_index']==cb['display_index']==31
    assert ca['original_sample_time_s']==time
    assert cb['original_sample_time_s']==(4096-1-31)/65536
    assert ca['candidate_ac'] and cb['candidate_ac']
    assert ca['value_m_s2']==pytest.approx(a['amplitude'][31])
    assert cb['value_m_s2']==pytest.approx(b['amplitude'][31])


def test_archive_acdc_rms_and_provenance(tmp_path):
    s=OfflineSession.open(fixture_zip(tmp_path))
    ac=s.waveform(1,0,.0625,'ac',points=8000)
    dc=s.waveform(1,0,.0625,'acdc',points=8000)
    assert ac['local_processing']=='GETSIGNAL_NO_ENVELOPE_IDR_CANDIDATE'
    assert ac['original_plot_coordinate_parity_verified'] is False
    assert dc['removed_mean_m_s2']==0
    expected=float(np.float32(np.sqrt(np.mean(np.asarray(dc['amplitude'],dtype='f8')**2))))
    assert dc['rms_m_s2']==pytest.approx(expected,rel=1e-5)
    assert 'GetSignal' in ac['processing_note']


def test_offline_window_must_not_pad_short_bin(tmp_path):
    s=OfflineSession.open(fixture_zip(tmp_path))
    with pytest.raises(ValueError):s.waveform(1,.0625,.001,'ac')
    with pytest.raises(ValueError):s.exact_sample(1,.0625,0,.0625,'ac')
    with pytest.raises(ValueError):s.waveform(1,0,.0625,'ac',display_order='invalid')

def test_synthetic_calibrated_bin_with_dc_offset_does_not_change_dsp(tmp_path):
    import zipfile, json, hashlib
    file=fixture_zip(tmp_path)
    with zipfile.ZipFile(file) as z:
        items={name:z.read(name) for name in z.namelist()}
    name=next(s for s in items if s.endswith('.bin') and '-ADC1-' in s)
    samples=np.frombuffer(items[name],dtype='<f4').copy()
    samples+=np.float32(6.)
    items[name]=samples.tobytes()
    audit=json.loads(items['EXPORT_AUDIT.json'])
    digest=hashlib.sha256(items[name]).hexdigest()
    audit['output_file_sha256'][name]=digest
    audit['channels'][0]['bin_sha256']=digest
    items['EXPORT_AUDIT.json']=json.dumps(audit).encode('utf-8')
    with zipfile.ZipFile(file,'w',zipfile.ZIP_DEFLATED) as z:
        for n,v in items.items():z.writestr(n,v)
    session=OfflineSession.open(file)
    dc=session.waveform(1,0,.0625,'acdc',points=10000)
    ac=session.waveform(1,0,.0625,'ac',points=10000)
    assert dc['mean_m_s2']>5.99
    assert dc['removed_mean_m_s2']==0
    assert ac['removed_mean_m_s2']>5.99
    assert abs(float(np.mean(ac['amplitude'])))<.003
    assert dc['source']==ac['source']=='MVK_ADC_CALIBRATED_BIN'
    assert session.calculations()['source']=='MVK_DSP'
