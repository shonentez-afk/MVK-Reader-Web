"""Stage111Z31CQ: native Qt PRIVATE DFM opt-in and blue screenshot gate.

Only fake PNGs generated in core tests. Original vendor icons, screenshot,
operator's personal DFM and paths are NEVER uploaded to CI artifacts.
"""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path

import pytest
pytest.importorskip("PySide6")

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from .test_desktop_qt import qt_app
from .test_stage111z31cc_qt_graph_layout_cursor import settle
from .test_stage111z31cq_private_imagelist_core import synthetic_task_dfm
from ..desktop.main_window import MainWindow

EXPECTED = ("bTaskConnect", "bTaskView", "bTaskConfigCh", "bTaskConfigIP")


def _assert_bg_blue(host):
    pixel = host.grab().toImage().pixelColor(host.width() // 2,
                                            min(host.height() - 1, 380))
    assert pixel.blue() >= pixel.red() + 20, (
        pixel.red(), pixel.green(), pixel.blue())


def test_private_icons_are_real_loaded_qt_widgets_but_amber_background_refused(
        qt_app, tmp_path):
    raw = synthetic_task_dfm(background=(255, 235, 195, 255))
    file = tmp_path / "synthetic_icons_and_amber_background.dfm"
    file.write_bytes(raw)
    digest = sha256(raw).hexdigest()
    win = MainWindow()
    win.resize(1280, 780)
    win.show()
    settle(qt_app)
    try:
        host = win.original_start_controller.host
        assert not host.original_pictures_loaded_privately
        assert not host.private_task_icons
        assert not host.private_blue_backgrounds_compatible
        assert host.load_private_original_dfm(file) == (
            "imBackL", "imBackR", "imLogo")
        assert host.original_pictures_loaded_privately
        assert set(host.private_task_icons) == {
            "Gears", "Open", "EditGear", "EditNet", "BWHand"}
        assert not host.private_blue_backgrounds_compatible
        assert not host.property(
            "sourcePrivateDfmPaletteAcceptedForBackground")
        assert host.property("sourceOriginalIconCollectionLoaded")
        assert host.logo.property("originalAssetLoadedPrivately")
        installed = win.original_start_controller.apply_private_icons()
        assert set(installed) == set(EXPECTED)
        win.original_visual_skin._source_icons()
        assert not win.original_root_tabs.tabIcon(0).isNull()
        assert "локального DFM" in win.original_root_tabs.tabToolTip(0)
        for name in EXPECTED:
            button = win.original_start_controller.buttons[name]
            assert button.property("sourceOriginalCommandBitmapProvided")
            assert not button.property("sourceTaskCommandImageCandidate")
            assert button.property("sourceIconLoadedOnlyInMemory")
            assert not button.icon().isNull()
            assert button.property("sourceSafeCoreRoutePreserved")
        _assert_bg_blue(host)
        assert win.original_visual_skin.snapshot()[
            "start_private_icons_loaded"] is True
        assert win.original_visual_skin.snapshot()[
            "start_private_background_palette_accepted"] is False
        assert win.session is None
        assert sha256(file.read_bytes()).hexdigest() == digest
        assert not win._live_active
        # The original private binary bytes are not recorded in a screenshot.
        # Only an independently generated fake PNG variant is used.
    finally:
        win.close()
        settle(qt_app)


def test_compatible_blue_dfm_background_is_allowed_but_never_claims_pixel_parity(
        qt_app, tmp_path):
    file = tmp_path / "synthetic_blue_reference.dfm"
    file.write_bytes(synthetic_task_dfm(
        background=(190, 238, 255, 255)))
    win = MainWindow()
    win.show()
    settle(qt_app)
    try:
        host = win.original_start_controller.host
        host.load_private_original_dfm(file)
        assert host.private_blue_backgrounds_compatible
        assert host.property(
            "sourcePrivateDfmPaletteAcceptedForBackground")
        assert not host.property(
            "sourceOperatorScreenshotPixelParityVerified")
        assert not host.property("sourceOriginalBitmapParityVerified")
        _assert_bg_blue(host)
    finally:
        win.close()
        settle(qt_app)


def test_default_operator_idle_source_cyan_has_original_gradient_boundaries(
        qt_app):
    win = MainWindow()
    win.resize(1280, 780)
    win.show()
    settle(qt_app)
    try:
        host = win.original_start_controller.host
        image = host.grab().toImage()
        # Original DFM PageStart places the fallback logo at y=max(0,
        # height-120). On GitHub's compact native DPI150 viewport, y=400
        # overlaps the footer image and samples its ochre/red pixels.
        # y=310 is clear of controls (last directory field ends at y=300)
        # and stays above the responsive footer even at height=494.
        y = min(host.height() - 1, 310)
        x0 = max(1, int(host.width() * .06))
        x1 = min(host.width() - 260, int(host.width() * .73))
        c0 = image.pixelColor(x0, y)
        c1 = image.pixelColor(x1, y)
        assert c0.blue() > c0.red()
        assert c1.blue() > c1.red() + 22
        assert c1.red() < c0.red()
        assert host.property("sourceBlueReferenceCandidate")
        assert host.property("sourceOperatorScreenshotPixelParityVerified") is False
    finally:
        win.close()
        settle(qt_app)
