import numpy as np
from fastapi.testclient import TestClient
from signal_bridge import api
from fastapi import FastAPI
app=FastAPI();app.include_router(api.router)
client=TestClient(app)
def test_wave_navigation(monkeypatch):
    monkeypatch.setattr(api,'load_adc',lambda adc:np.arange(65536*5,dtype=np.float32))
    r=client.get('/api/signal/adc/1/waveform',params={'start_s':2,'seconds':1,'points':256})
    assert r.status_code==200
    a=r.json();assert a['start_s']==2 and a['total_s']==5
    assert a['time_s'][0]==2 and a['values'][0]==131072

def test_invalid_short_spectrum(monkeypatch):
    monkeypatch.setattr(api,'load_adc',lambda adc:np.arange(65536*5,dtype=np.float32))
    r=client.get('/api/signal/adc/1/spectrum',params={'start_s':1,'duration_s':0.2,'nperseg':65536})
    assert r.status_code==422

def test_default_end(monkeypatch):
    monkeypatch.setattr(api,'load_adc',lambda adc:np.arange(65536*5,dtype=np.float32))
    r=client.get('/api/signal/adc/1/waveform',params={'seconds':1})
    assert r.status_code==200 and r.json()['start_s']==4
