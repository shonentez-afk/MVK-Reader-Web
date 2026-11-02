"""Stage111Z29C2: Qt envelope spectra respect deliberate original float-ring choice.

Synthetic only, no original private IDP, no real device, no TCP.
"""
from __future__ import annotations

import numpy as np
import pytest

from .test_desktop_qt import qt_app
from .test_envelope_idr_candidate import fake_profile
from .test_offline_core import fixture_zip


def test_qt_envelope_original_storage_f_range_selected_explicitly_no_false_alarm(tmp_path,qt_app):
    from mvk_compatible.desktop.main_window import MainWindow

    w=MainWindow()
    w.open_archive(fixture_zip(tmp_path))
    w.show()
    w.tabs.setCurrentIndex(2)
    w.set_envelope_profile(fake_profile(i=1.,q=.4))
    w.spec_mode.setCurrentIndex(1)
    w.spec_backend.setCurrentIndex(1) # NumPy only for synthetic UI test
    w.spec_envelope_button.setChecked(True)
    qt_app.processEvents()
    assert w.spec_n.currentText()=="1024"
    assert w.spec_input_domain.currentData()=="calibrated_bin"
    original_sha=w.session.samples(1)[0].tobytes()
    before=w._full_spectrum
    assert before is not None
    before_values=np.asarray(before["amplitude"])
    assert before["input_domain"]=="calibrated_bin"
    w.spec_f_range.setValue(4.)
    w.spec_input_domain.setCurrentIndex(1)
    w.refresh_spec()
    qt_app.processEvents()
    after=w._full_spectrum
    assert after is not None
    assert after["input_domain"]=="original_float_storage"
    assert after["original_storage_read_divided_by_range"]
    assert after["original_source_buffer_provenance_verified"] is False
    assert after["calibrated_native_bin_is_original_storage_verified"] is False
    assert after["pre_fir_read_is_original_runtime_verified"] is False
    assert "ГИПОТЕЗА" in w.spec_hint.text()
    assert "после FIR повторного DC нет" in w.spec_hint.text()
    assert "ДО удаления DC" in w.spec_input_domain.toolTip()
    assert "APP_DERIVED_ENVELOPE_SPECTRUM_IDR_CANDIDATE" in w.spec_hint.text()
    ix=int(np.argmax(before_values))
    assert before_values[ix]>0
    assert after["amplitude"][ix]==pytest.approx(before_values[ix],rel=.005)
    assert w.session.samples(1)[0].tobytes()==original_sha
    w.spec_input_domain.setCurrentIndex(0)
    w.refresh_spec()
    qt_app.processEvents()
    reverted=w._full_spectrum
    assert reverted["input_domain"]=="calibrated_bin"
    assert not reverted["original_storage_read_divided_by_range"]
    assert reverted["amplitude"][ix]==pytest.approx(before_values[ix]*4.,rel=.005)
    w.close()
    qt_app.processEvents()


def test_qt_envelope_original_storage_without_profile_stays_unavailable(tmp_path,qt_app):
    from mvk_compatible.desktop.main_window import MainWindow
    w=MainWindow()
    w.open_archive(fixture_zip(tmp_path))
    w.spec_input_domain.setCurrentIndex(1)
    assert w.spec_input_domain.currentData()=="original_float_storage"
    assert w.envelope_profile is None
    assert not w.spec_envelope_button.isEnabled()
    assert not w.spec_envelope_button.isChecked()
    w.close()
    qt_app.processEvents()
