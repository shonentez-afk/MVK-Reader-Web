from datetime import datetime,timezone

import pytest
from ..core.direct_bin_session import DirectBinSession
from .test_stage111z16_direct_bin_tsxml import _make_pair
from ..core.original_mode2_source_files import build_original_tsxml_compatible


def _mixed_pair(root,adc=4):
    p,x,_=_make_pair(root,adc=adc)
    xml,_=build_original_tsxml_compatible(
        channel=adc,binary_basename=p.name,size_bytes=p.stat().st_size,rate_hz=65536,
        local_time=datetime(2026,11,1,13,0,tzinfo=timezone.utc),
        device_label='MVK00000043',channel_label=f'ADC{adc}',adc_units='м/с2',adc_gain=8)
    x.write_bytes(xml)
    upgraded=p.with_suffix('.BiN')
    sidecar=upgraded.with_name(upgraded.name+'.TsXmL')
    p.rename(upgraded)
    x.rename(sidecar)
    return upgraded,sidecar


def test_accept_relative_mixed_case_extensions_and_original_stem(tmp_path):
    p,x=_mixed_pair(tmp_path,4)
    sibling,_=_mixed_pair(tmp_path,6)
    for chosen in (p,x,sibling):
        s=DirectBinSession.open(chosen)
        assert s.available_channels==(4,6)
        assert s.path.name in (p.name,sibling.name)
        assert s.samples(s.primary_channel)[0].size>0
        assert s.mode1_adc_range(s.primary_channel)==8
    assert DirectBinSession.open(x).primary_channel==4


def test_identical_original_sidecars_safe_only_in_operator_recovery(tmp_path):
    p,x=_mixed_pair(tmp_path)
    side2=p.with_suffix('.TSXML')
    side2.write_bytes(x.read_bytes())
    with pytest.raises(ValueError,match='ровно одна'):
        DirectBinSession.open(p)
    for chosen in (p,x,side2):
        s=DirectBinSession.open(chosen,allow_partial_group=True)
        if chosen!=p:
            assert s.channel_files[0].tsxml_path==chosen
    side2.write_bytes(side2.read_bytes()+b' ')
    with pytest.raises(ValueError,match='конфликт'):
        DirectBinSession.open(p,allow_partial_group=True)


def test_same_casefold_suffix_twins_do_not_auto_choose(tmp_path):
    p,x=_mixed_pair(tmp_path)
    other=p.with_suffix('.bin')
    if other.exists():
        pytest.skip('case-insensitive filesystem')
    other.write_bytes(p.read_bytes())
    with pytest.raises(ValueError,match='конфликт регистра'):
        DirectBinSession.open(x,allow_partial_group=True)
    with pytest.raises(ValueError,match='конфликт регистра'):
        DirectBinSession.open(p)


def test_case_tolerance_never_relaxes_declared_stem(tmp_path):
    p,x=_mixed_pair(tmp_path)
    # Same size, same channel metadata, but a different declared stem.
    text=x.read_bytes().replace(p.stem.encode(),(p.stem+'-other').encode())
    if text==x.read_bytes():
        text=x.read_bytes().replace(p.stem.encode('utf-16-le'),(p.stem+'-other').encode('utf-16-le'))
    assert text!=x.read_bytes()
    x.write_bytes(text)
    with pytest.raises(ValueError,match='DataFileName'):
        DirectBinSession.open(x,allow_partial_group=True)


def test_operator_drag_local_only_retains_current_archive_on_rejection(tmp_path,monkeypatch):
    pytest.importorskip('PySide6')
    from PySide6.QtCore import QMimeData,QPoint,QPointF,QUrl,Qt
    from PySide6.QtGui import QDragEnterEvent,QDropEvent
    from PySide6.QtWidgets import QApplication,QMessageBox
    from ..desktop.archive_entry import ArchiveEntryWindow
    app=QApplication.instance() or QApplication([])
    a,_=_mixed_pair(tmp_path,4)
    b,_=_mixed_pair(tmp_path,6)
    alerts=[]
    monkeypatch.setattr(QMessageBox,'critical',lambda *args:alerts.append(args[-1]))
    win=ArchiveEntryWindow()
    win.show()
    try:
        urls=QMimeData()
        urls.setUrls([QUrl.fromLocalFile(str(a))])
        ev=QDragEnterEvent(QPoint(10,10),Qt.CopyAction,urls,Qt.LeftButton,Qt.NoModifier)
        win.dragEnterEvent(ev)
        assert ev.isAccepted()
        drop=QDropEvent(QPointF(10,10),Qt.CopyAction,urls,Qt.LeftButton,Qt.NoModifier)
        win.dropEvent(drop)
        app.processEvents()
        assert drop.isAccepted() and win.session.primary_channel==4
        assert win.original_root_tabs.currentIndex()==3
        saved=win.session
        for u in ([QUrl('https://example.invalid/a.bin')],
                  [QUrl.fromLocalFile(str(a)),QUrl.fromLocalFile(str(b))]):
            urls.setUrls(u)
            win.dropEvent(drop)
            assert not drop.isAccepted() and win.session is saved
        urls.setUrls([QUrl.fromLocalFile(str(tmp_path/'missing.BIN'))])
        win.dropEvent(drop)
        assert alerts and 'Предыдущая запись осталась открытой' in alerts[-1]
        assert win.session is saved
        win._live_active=True
        urls.setUrls([QUrl.fromLocalFile(str(b))])
        win.dropEvent(drop)
        assert not drop.isAccepted() and win.session is saved
        win._live_active=False
    finally:
        win.close()


def test_packaged_launcher_routes_archive_arg_and_preserves_fir_check(monkeypatch):
    pytest.importorskip('PySide6')
    from .. import windows_launcher
    from ..core import bundled_offline_fir
    from ..desktop import archive_entry
    marker=object()
    received=[]
    monkeypatch.setattr(bundled_offline_fir,'load_frozen_offline_fir',lambda:marker)
    monkeypatch.setattr(archive_entry,'run_archive_desktop',lambda paths,profile:received.append((paths,profile)) or 0)
    assert windows_launcher.main(['--verify-offline-fir'])==0 and received==[]
    assert windows_launcher.main(['C:/Мои измерения/сигнал.TsXmL'])==0
    assert received==[(('C:/Мои измерения/сигнал.TsXmL',),marker)]
