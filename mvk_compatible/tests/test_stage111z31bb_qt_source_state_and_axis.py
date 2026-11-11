"""Stage111Z31BB: original all-page state, fixed full-25600 Hz source axis.

All input Power/Y generated synthetically from the existing trusted test
fixture; original process, private BIN/IDP, x32dbg and device never used.
"""
import numpy as np
import pytest

pytest.importorskip("PySide6")
from .test_desktop_qt import qt_app
from .test_stage111z31a_x32dbg_visual_reference import create_reference_fixture
from mvk_compatible.core.original_offline_view_state import PAGES,DEFAULT_HZ


def test_all_seven_original_pages_and_channel_state_mirror_portable_core(qt_app):
    from mvk_compatible.desktop.main_window import MainWindow
    w=MainWindow()
    w.show()
    qt_app.processEvents()
    assert w.source_view_state.page=="PageStart"
    assert w.original_root_tabs.count()==len(PAGES)==7
    for i,page in enumerate(PAGES):
        w.original_root_tabs.setCurrentIndex(i)
        qt_app.processEvents()
        assert w.source_view_state.page==page
        assert w.original_root_tabs.tabData(i)==page
        assert not w.source_view_state.snapshot()["device_command_issued"]
    w.original_root_tabs.setCurrentIndex(0)
    for i in (0,2,5,7):
        w.adc.setCurrentIndex(i)
        qt_app.processEvents()
        assert w.source_view_state.channel==i+1
    w.close()
    qt_app.processEvents()


def test_code20_log0_original_axis_25600_but_original_series_12800(qt_app,tmp_path):
    from mvk_compatible.desktop.main_window import MainWindow
    w=MainWindow()
    w.show()
    manifest,_,_,_=create_reference_fixture(
        tmp_path/"code20_like",mode=0,n=1024,fs=32768)
    w.show_original_spectrum_reference(manifest)
    qt_app.processEvents()
    assert w._spec_display_contract["grapher_axis_end_frequency_hz"]==12800
    assert w._spec_visible_max_hz==DEFAULT_HZ==25600
    assert w._spec_original_hscale_selected==25600
    assert w.spec_hscale_button.text()=="25600 Гц"
    assert w._spec_hscale_actions[0].isChecked()
    assert not w.spec_hscroll.isVisible()
    vb=w.spec_plot.getViewBox()
    lo,hi=vb.viewRange()[0]
    assert abs(lo)<1e-4 and abs(hi-25600)<1e-4
    items=w.spec_plot.listDataItems()
    assert len(items)==1
    x,y=items[0].getData()
    assert len(x)==len(y)==400
    assert x[-1]==12768
    assert hi > 2*x[-1]-100
    assert w.source_view_state.page=="PageSpectrum"
    assert w.source_view_state.snapshot()["hscale_hz"]==25600
    before=np.asarray(w._full_spectrum["amplitude"],dtype="<f4").view(
        "<u4").copy()

    # Actual native source menu choices do not touch FFT/Power arrays.
    w._select_original_hscale(12800)
    qt_app.processEvents()
    assert w.spec_hscale_button.text()=="12800 Гц"
    assert w._spec_hscale_actions[1].isChecked()
    assert w.source_view_state.snapshot()["hscale_hz"]==12800
    assert w.spec_hscroll.isVisible()
    lo,hi=vb.viewRange()[0]
    assert abs(hi-lo-12800)<1e-4
    w.spec_hscroll.setValue(1000)
    qt_app.processEvents()
    assert w.source_view_state.hscroll_position==1000
    lo,hi=vb.viewRange()[0]
    assert abs(lo-1000)<1e-3 and abs(hi-lo-12800)<1e-3
    np.testing.assert_array_equal(
        np.asarray(w._full_spectrum["amplitude"],dtype="<f4").view("<u4"),
        before)
    w._select_original_hscale(25600)
    qt_app.processEvents()
    assert w.source_view_state.hscroll_position==0
    assert not w.spec_hscroll.isVisible()
    w.close()
    qt_app.processEvents()


@pytest.mark.parametrize("mode", [1,2,3])
def test_other_spectrum_tags_are_view_only_and_original_source_axis(
        qt_app,tmp_path,mode):
    from mvk_compatible.desktop.main_window import MainWindow
    w=MainWindow()
    w.show()
    manifest,_,_,_=create_reference_fixture(
        tmp_path/f"tag_{mode}",mode=mode,n=1024,fs=32768)
    w.show_original_spectrum_reference(manifest)
    qt_app.processEvents()
    assert w._spec_visible_max_hz==DEFAULT_HZ
    assert w._spec_original_hscale_selected==25600
    assert w.source_view_state.spectrum_mode==mode
    assert w.source_view_state.vscale_tag==3
    assert w._full_spectrum["mode"]==mode
    assert not w.spec_copy_button.isEnabled()
    w.close()
    qt_app.processEvents()
