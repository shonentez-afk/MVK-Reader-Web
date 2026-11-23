
"""Real Qt menus matching original user 2026-10-21 screenshot text."""
import pytest
pytest.importorskip("PySide6")
from ..desktop.main_window import MainWindow
from .test_desktop_qt import qt_app


def test_original_spectrum_popup_six_rows_no_research_sizes(qt_app):
    w=MainWindow()
    w.show()
    qt_app.processEvents()
    try:
        w._sync_spec_lines_presentation(fs=65536)
        assert [a.text() for a in w.spec_lines_menu.actions()]==[
            "1/4 Гц/лин","1/2 Гц/лин","1 Гц/лин","2 Гц/лин","4 Гц/лин","8 Гц/лин"]
        assert [a.data() for a in w.spec_lines_menu.actions()]==[
            262144,131072,65536,32768,16384,8192]
        assert [a.text() for a in w.spec_type_menu.actions()]==[
            "Логарифмич.","Линейный ВУ","Линейный ВС","Линейный ВП"]
        assert [a.text() for a in w.spec_hscale_menu.actions()]==[
            f"{n} Гц" for n in (25600,12800,6400,3200,1600,800,400,200,100,50)]
        assert len(w.original_envelope_menu.actions())==32
        assert w.spec_save_button.text()=="Сохранить"
        assert w.spec_copy_button.text()=="Копировать"
        assert w.spec_n.findData(1024)>=0 and w.spec_n.findData(4096)>=0
        assert not any(a.data() in (1024,4096) for a in w.spec_lines_menu.actions())
    finally:
        w.close()
        qt_app.processEvents()
