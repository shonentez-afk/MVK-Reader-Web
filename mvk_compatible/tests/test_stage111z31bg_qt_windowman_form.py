"""Stage111Z31BG: genuine Qt third form + modeless local errors.

Synthetic text only; no original Win32, instrument or GUI automation.
"""
import pytest
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QLabel, QPushButton
from .test_desktop_qt import qt_app

from mvk_compatible.desktop.original_windowman_form import (
    OriginalWindowManForm,
)


def test_original_windowman_three_form_geometry_and_modal_codes(qt_app):
    from mvk_compatible.desktop.main_window import MainWindow
    w=MainWindow()
    w.show()
    qt_app.processEvents()
    try:
        assert w.original_window_man is not None
        dialog=w.original_window_man.create_query(
            "Остаться в автономном режиме?","Вопрос",
            yes=True,no=True,cancel=True)
        try:
            dialog.show()
            qt_app.processEvents()
            assert dialog.objectName()=="WindowManForm"
            assert dialog.size().width()==436
            assert dialog.size().height()==186
            assert dialog.findChild(QLabel,"Lbl").geometry().getRect()==(
                111,24,304,65)
            assert dialog.findChild(QPushButton,"img").geometry().getRect()==(
                16,16,80,80)
            assert dialog.original_button_result_map()=={
                "bYes":6,"bNo":7,"bCancel":2,"bOk":1}
            assert dialog.bYes.isVisible()
            assert dialog.bNo.isVisible()
            assert dialog.bCancel.isVisible()
            assert not dialog.bOk.isVisible()
            assert dialog.property("deviceCommandAllowed") is False
            dialog.bNo.click()
            assert dialog.result()==7
        finally:
            dialog.close()
    finally:
        w.close()
        qt_app.processEvents()


def test_error_information_and_wait_do_not_unlock_original_device(qt_app):
    from mvk_compatible.desktop.main_window import MainWindow
    w=MainWindow()
    w.show()
    qt_app.processEvents()
    try:
        manager=w.original_window_man
        error=manager.spawn_error("Локальный файл отклонён")
        qt_app.processEvents()
        assert error.isVisible()
        assert error.Lbl.text()=="Локальный файл отклонён"
        assert error.bOk.isVisible()
        assert not error.bYes.isVisible()
        assert not error.bNo.isVisible()
        assert not error.bCancel.isVisible()
        assert error.property("originalSourceMessageMode")=="error"
        error.bOk.click()
        assert error.result()==1

        info=manager.spawn_information("Только локальный просмотр")
        qt_app.processEvents()
        assert info.isVisible()
        assert info.property("originalSourceMessageMode")=="information"
        info.bOk.click()
        assert info.result()==1

        wait=manager.show_wait("Ожидание проверки")
        qt_app.processEvents()
        assert wait.isVisible()
        assert wait.objectName()=="WindowManForm"
        assert not any(btn.isVisible() for btn in (
            wait.bYes,wait.bNo,wait.bCancel,wait.bOk))
        assert wait.size().height()==124  # 2/3 logical candidate
        assert wait.img.property("originalSourceImageIndex")==1
        assert wait.property("deviceCommandAllowed") is False
        manager.hide_wait()
        qt_app.processEvents()
        assert not wait.isVisible()
    finally:
        w.close()
        qt_app.processEvents()


def test_source_window_form_does_not_hardcode_original_dfm_design_time_text(qt_app):
    original=OriginalWindowManForm()
    try:
        assert original.Lbl.text()==""
        assert original.windowTitle() != (
            "Большой Брат смотрит на тебя!")
        assert original.img.property("originalSourceImageUnavailable") is True
    finally:
        original.close()
