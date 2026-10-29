"""Stage111B: IDR reconstruction synthetic QA, NOT original executable parity."""
import math
import numpy as np
import pytest
from mvk_compatible.core.fft_idr_candidate import (
 mean_center_float32,idr_hann_rms,fft_idr_float32_real,idr_power_spectrum)

def test_delphi_centered_signal_preserves_input():
 x=(10+np.sin(2*np.pi*8*np.arange(1024)/1024)).astype('f4')
 saved=x.copy();y,mean=mean_center_float32(x)
 np.testing.assert_array_equal(x,saved)
 assert 9.99<mean<10.01 and abs(float(np.mean(y)))<.01

def test_running_mean_f32_not_pairwise():
 x=np.array([100000.,-99999.,.1001,.2002,.3003,-.7]*33,dtype='f4')
 acc=np.float32(0)
 for v in x: acc=np.float32(float(acc)+float(v))
 centered,mean=mean_center_float32(x)
 assert mean==float(np.float32(float(acc)/len(x)))
 assert centered.dtype==np.float32

@pytest.mark.parametrize('n',[256,1024,8192,262144])
def test_hann_rms_lookup_energy(n):
 w=idr_hann_rms(n)
 assert len(w)==n and w.dtype==np.float32
 assert np.mean(w.astype(np.float64)**2)==pytest.approx(1,rel=1e-6)
 assert w[0]==0 and w[n//2]==pytest.approx(2/math.sqrt(1.5),rel=1e-6)

@pytest.mark.parametrize('n',[16,256,1024,4096])
def test_idr_positive_angle_fft_against_numpy(n):
 x=(.35*np.sin(2*np.pi*3*np.arange(n)/n)+.17*np.cos(2*np.pi*7*np.arange(n)/n)+.05).astype('f4')
 re,im=fft_idr_float32_real(x)
 z=np.fft.fft(x.astype('f8')).conjugate()
 np.testing.assert_allclose(re,z.real,rtol=1e-3,atol=2e-3)
 np.testing.assert_allclose(im,z.imag,rtol=1e-3,atol=2e-3)
 assert re.dtype==np.float32 and im.dtype==np.float32

def test_constant_offset_removed_before_hann():
 n=4096;t=np.arange(n)
 signal=(40+.9*np.sin(2*np.pi*32*t/n)).astype('f4')
 p,mean=idr_power_spectrum(signal)
 p2,_=idr_power_spectrum(signal-40)
 assert mean>39.9 and p[32]>1e5
 assert p[0]<1e-3
 assert abs(float(p[32]/p2[32])-1)<.005
 assert len(p)==n//2

def test_idr_and_numpy_are_two_derived_candidates():
 n=8192;t=np.arange(n)
 signal=(2.5+np.sin(2*np.pi*63*t/n)+.013*np.sin(2*np.pi*247*t/n)).astype('f4')
 a,ma=idr_power_spectrum(signal,'idr_float32')
 b,mb=idr_power_spectrum(signal,'numpy')
 assert ma==mb and np.all(np.isfinite(a))
 np.testing.assert_allclose(a[63],b[63],rtol=.005)
 np.testing.assert_allclose(a[247],b[247],rtol=.005)

@pytest.mark.parametrize('backend',['numpy','idr_float32'])
def test_reject_non_power_nan_and_unknown_backend(backend):
 with pytest.raises(ValueError):idr_power_spectrum(np.zeros(123,dtype='f4'),backend)
 with pytest.raises(ValueError):idr_power_spectrum(np.full(1024,np.nan,dtype='f4'),backend)
 with pytest.raises(ValueError):idr_power_spectrum(np.zeros(1024,dtype='f4'),'invalid')

def test_cached_lookup_table_not_mutable_from_call():
 w=idr_hann_rms(1024);w[10]=55.
 assert idr_hann_rms(1024)[10]!=55.

def test_stage111b_offline_session_backend_report(tmp_path):
 # Synthetic-only fixture from existing Stage111 suite.
 from mvk_compatible.core import OfflineSession
 from mvk_compatible.tests.test_offline_core import fixture_zip
 s=OfflineSession.open(fixture_zip(tmp_path))
 a=s.spectrum(1,4096,1,0,1024,3000,backend='idr_float32')
 b=s.spectrum(1,4096,1,0,1024,3000,backend='numpy')
 assert a['detrended_before_fft'] is True
 assert a['fft_backend']=='idr_float32' and b['fft_backend']=='numpy'
 assert a['original_delphi_numerical_parity'] is False
 assert len(a['frequency_hz'])==len(b['frequency_hz'])
 report=s.compare_fft_backends(1,4096,1,0)
 assert report['source']=='APP_DERIVED_BACKEND_COMPARISON'
 assert report['original_delphi_parity_verified'] is False
 assert report['relative_difference_at_reference_peak']<.01
