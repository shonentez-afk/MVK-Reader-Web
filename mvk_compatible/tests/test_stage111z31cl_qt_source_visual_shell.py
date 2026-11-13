"""Stage111Z31CL source-skin visual QA at actual Windows Qt DPI150.

These verify the REAL, ordinary PageStart/Adc/Spectrum screens, not a
new hand-drawn screenshot or research-only modal. Font/icons without the
private DFM remain clearly labelled Qt candidates.
"""
from hashlib import sha256
import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import QBuffer,QByteArray,QIODevice,Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QLabel,QWidget,QToolButton

from .test_desktop_qt import qt_app
from .test_offline_core import fixture_zip
from .test_stage111z31cc_qt_graph_layout_cursor import settle
from ..core.original_ui_form_contract import (
    ORIGINAL_ROOT_PAGES,ORIGINAL_SPECTRUM_CONTROLS,
    ORIGINAL_WAVE_CONTROLS,
)


def test_source_first_window_has_no_second_qt_chrome_and_real_dfm_start(
        qt_app):
    from ..desktop.main_window import MainWindow
    w=MainWindow();w.show();settle(qt_app)
    try:
        skin=w.original_visual_skin
        snap=skin.snapshot()
        assert snap["root_pages"]==7
        assert snap["root_page_names"]==[
            p.object_name for p in ORIGINAL_ROOT_PAGES]
        assert not snap["technical"]
        assert not snap["menu_visible"]
        assert not snap["statusbar_visible"]
        assert not snap["root_tabs_expand"]
        assert snap["root_tab_height"]==44
        assert snap["visible_source_tabs"]==["PageStart"]
        assert not w.note.isVisible()
        assert w.original_root_tabs.currentIndex()==0
        assert w.task_subpages.tabBar().isHidden()
        assert w.tabs.tabBar().isHidden()
        assert w.task_subpages.widget(0).findChild(
            QLabel,"taskHomeHeading").isHidden()
        assert w.task_subpages.widget(0).findChild(
            QLabel,"taskSessionSummary").isHidden()
        assert w.calc_source.isHidden() or not w.calc_source.isVisible()
        assert all(not w.original_root_tabs.tabIcon(i).isNull()
                   for i in range(7))
        host=w.original_start_controller.host
        assert host.objectName()=="SourcePageStartLauncher"
        assert host.property("sourceBackgroundOriginalDfmGeometry")
        assert not host.property("sourceContainsPublishedVendorImageData")
        assert host.logo.objectName()=="imLogo"
        assert host.logo.geometry().getRect()==(3,568,432,120)
        assert host.y()<=5
        assert host.width()>=840
        assert host.height()>=494
        for name,button in w.original_start_controller.buttons.items():
            x,y,ww,hh=button.property("originalDfmLogicalRect")
            assert button.geometry().getRect()==(x,y,ww,hh)
        assert w.original_start_controller.buttons[
            "bTaskConfigCalib"].isHidden()
        assert not w._live_active
    finally:
        w.close();settle(qt_app)


def test_source_wave_spectrum_main_graphs_keep_original_visible_rects_and_dsp(
        qt_app,tmp_path):
    from ..desktop.main_window import MainWindow
    src=fixture_zip(tmp_path,sample_count=8192)
    digest=sha256(src.read_bytes()).hexdigest()
    w=MainWindow();w.show();settle(qt_app)
    try:
        w.open_archive(src)
        settle(qt_app)
        # Original operator capture with loaded measurement exposes
        # Tasks, Time signal, Spectrum; the remaining 4 DFM forms are
        # mounted, not always shown as another engineering tab strip.
        assert w.original_visual_skin.snapshot()["visible_source_tabs"]==[
            "PageStart","PageAdc","PageSpectrum"]
        assert w.original_root_tabs.count()==7
        fft=w._full_spectrum["amplitude"].copy()
        for page,canvas,controls,plot in (
            (3,w.wave_source_canvas,ORIGINAL_WAVE_CONTROLS,w.wave_plot),
            (4,w.spec_source_canvas,ORIGINAL_SPECTRUM_CONTROLS,w.spec_plot)):
            w.original_root_tabs.setCurrentIndex(page)
            settle(qt_app)
            assert not w.menuBar().isVisible()
            assert not w.statusBar().isVisible()
            assert canvas.isVisible()
            assert canvas.width()>=170
            assert plot.isVisible()
            for name,kind,x,y,width,height in controls:
                # QLabel names and Qt presenter model names differ
                # from source Delphi DFM identities by design. The
                # source canvas registers the authoritative DFM binding
                # on EVERY actual widget (including the real readouts).
                matched=[child for child in canvas.findChildren(QWidget)
                         if child.property("originalDfmControlName")==name]
                assert len(matched)==1, (page,name)
                mapped=matched[0]
                assert mapped.property("originalDfmLogicalRect")==(
                    x,y,width,height)
                assert mapped.geometry().height()==height
                if isinstance(mapped,QLabel):
                    # Original source lbAdcHint/lbMean/lbSpecHint/lbSpecMean
                    # are readouts, NOT TButtons with an ImageName/icon.
                    assert bool(mapped.text())
                    assert mapped.alignment() & Qt.AlignHCenter
                else:
                    assert mapped.property("sourceDfmImageCandidate") is True
                    assert not mapped.property("sourceOriginalBitmapProvided")
                    assert not mapped.icon().isNull()
                    if isinstance(mapped,QToolButton):
                        assert mapped.toolButtonStyle()==Qt.ToolButtonTextBesideIcon
            assert not w.source_view_state.snapshot()["device_command_issued"]
        import numpy as np
        np.testing.assert_array_equal(w._full_spectrum["amplitude"],fft)
        assert sha256(src.read_bytes()).hexdigest()==digest
    finally:
        w.close();settle(qt_app)


def test_f12_technical_view_keeps_original_client_reachable(qt_app):
    from ..desktop.main_window import MainWindow
    w=MainWindow();w.show();settle(qt_app)
    try:
        skin=w.original_visual_skin
        assert skin.toggle_action.shortcut().toString()=="F12"
        assert any(a.shortcut().toString()=="Ctrl+O"
                   for a in w.actions())
        assert not w.menuBar().isVisible()
        skin.toggle_action.setChecked(True)
        settle(qt_app)
        assert skin.snapshot()["technical"]
        assert skin.snapshot()["visible_source_tabs"]==[
            p.object_name for p in ORIGINAL_ROOT_PAGES]
        assert w.menuBar().isVisible()
        assert w.statusBar().isVisible()
        assert w.note.isVisible()
        assert w.original_shell.view_panel.height()==64
        assert not w.wave_advanced_button.isHidden()
        assert not w.spec_advanced_button.isHidden()
        assert all(not x.isHidden() for x in
                   w.original_start_controller.technical_widgets)
        skin.toggle_action.setChecked(False)
        settle(qt_app)
        assert not skin.snapshot()["technical"]
        assert skin.snapshot()["visible_source_tabs"]==["PageStart"]
        assert not w.menuBar().isVisible()
        assert not w.statusBar().isVisible()
        assert w.original_shell.view_panel.height()==48
        assert all(x.isHidden() for x in
                   w.original_start_controller.technical_widgets)
    finally:
        w.close();settle(qt_app)


def test_operator_private_dfm_loads_only_into_memory_and_never_rewrites(
        qt_app,tmp_path):
    from ..desktop.main_window import MainWindow
    # Generate three TEST-TIME PNGs only, no original asset in repository.
    img=QImage(16,16,QImage.Format_ARGB32)
    img.fill(0xFFFAE8C2)
    array=QByteArray()
    buffer=QBuffer(array)
    assert buffer.open(QIODevice.WriteOnly)
    assert img.save(buffer,"PNG")
    buffer.close()
    picture=b"\x09TPngImage"+bytes(array)
    lines=["object mvkform: Tmvkform"]
    for name in ("imBackL","imBackR","imLogo"):
        lines.extend(("        object "+name+": TImage",
                      "          Picture.Data = {",
                      "             "+picture.hex().upper(),
                      "          }","        end"))
    lines.append("end")
    path=tmp_path/"private_from_operator_only.dfm"
    path.write_text("\n".join(lines),encoding="ascii")
    original_hash=sha256(path.read_bytes()).hexdigest()
    w=MainWindow();w.show();settle(qt_app)
    try:
        host=w.original_start_controller.host
        assert not host.original_pictures_loaded_privately
        loaded=host.load_private_original_dfm(path)
        assert loaded==("imBackL","imBackR","imLogo")
        assert host.original_pictures_loaded_privately
        assert not host.logo.pixmap().isNull()
        assert host.logo.property("originalAssetLoadedPrivately")
        assert not host.property("sourceOriginalBitmapParityVerified")
        assert sha256(path.read_bytes()).hexdigest()==original_hash
        assert not w._live_active
    finally:
        w.close();settle(qt_app)
