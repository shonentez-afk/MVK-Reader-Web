"""Evidence-backed v0.3 regression: six Delphi menus were lost in v0.2.

No live original MVKView, screen access, Frida or instrumentation is used.
"""
from __future__ import annotations
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from capture_agent.config import CaptureConfig
from capture_agent.events import meaningful_win_event
from capture_agent.session import CaptureSession
from test_capture_agent import FakeWindows


class FakePopupBackend(FakeWindows):
    def __init__(self):
        super().__init__()
        self.popup_open = False
        self.captured_hwnds = []

    def snapshot(self, pid, hwnd, limit, uia):
        out = super().snapshot(pid, hwnd, limit, uia)
        out['toplevel_windows'] = [
            {'hwnd': 5678, 'class_name': 'Tmvkform', 'name': 'MVKView 1.0.47',
             'rect': [0, 0, 1280, 680], 'visible': True},
        ]
        if self.popup_open:
            out['toplevel_windows'].extend([
                {'hwnd': 9090, 'class_name': '#32768', 'name': '',
                 'rect': [17, 127, 267, 518], 'visible': True},
                {'hwnd': 9091, 'class_name': 'SysShadow', 'name': '',
                 'rect': [17, 127, 270, 521], 'visible': True},
                {'hwnd': 9092, 'class_name': 'TApplication', 'name': '',
                 'rect': [0, 0, 0, 0], 'visible': True},
            ])
        return out

    def screenshot(self, pid, hwnd, path):
        if hwnd not in (5678, 9090):
            raise AssertionError(f'Invalid visual evidence window: {hwnd}')
        self.check_target(pid, 5678)
        self.captured_hwnds.append(hwnd)
        Path(path).write_bytes(f'SYNTHETIC SCREEN {len(self.captured_hwnds)} HWND={hwnd}'.encode())
        return {'width': 369 if hwnd == 9090 else 1280, 'height': 580 if hwnd == 9090 else 680}


class PopupRegressionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.backend = FakePopupBackend()
        cfg = replace(CaptureConfig.defaults(), output_dir=Path(self.tmp.name), poll_seconds=60)
        self.session = CaptureSession(cfg, self.backend, self.backend.target)
        self.session.start()
        self.addCleanup(self.session.stop)

    def test_poll_saves_popup_even_when_normal_poll_has_no_screenshot(self):
        self.backend.popup_open = True
        result = self.session.snapshot(reason='poll', screenshot=False, only_if_changed=True)
        self.assertTrue(result['changed'])
        self.assertIn('screenshot', result)
        self.assertEqual(self.backend.captured_hwnds, [5678, 5678, 9090])
        events = [json.loads(line) for line in (self.session.store.path/'timeline.jsonl').read_text().splitlines()]
        item = events[-1]
        self.assertEqual(item['kind'], 'snapshot')
        extras = item['payload']['additional_process_windows']
        self.assertEqual(len(extras), 1)
        self.assertEqual(extras[0]['hwnd'], 9090)
        self.assertEqual(extras[0]['class_name'], '#32768')
        # The delayed WinEvent snapshot must not duplicate the earlier poll.
        again = self.session.snapshot(reason='win_event', screenshot=True, only_if_changed=True)
        self.assertFalse(again['changed'])
        self.assertEqual(self.backend.captured_hwnds, [5678, 5678, 9090])

    def test_no_ghost_sys_shadow_and_no_extra_capture_without_popup(self):
        self.backend.version += 1
        result = self.session.snapshot(reason='poll', screenshot=False, only_if_changed=True)
        self.assertTrue(result['changed'])
        self.assertIsNone(result['screenshot'])
        self.assertEqual(self.backend.captured_hwnds, [5678])

    def test_known_win32_caption_attached_to_event(self):
        observed = self.session._annotate_win_event({'event':'OBJECT_INVOKED', 'hwnd':42})
        self.assertEqual(observed['control_name'], 'PageSpectrum')
        # Never infer labels for unseen HWNDs.
        self.assertNotIn('control_name', self.session._annotate_win_event({'hwnd':9090}))

    def test_cursor_location_noise_is_discarded_without_losing_useful_events(self):
        self.assertFalse(meaningful_win_event(0x800B, -9))
        self.assertTrue(meaningful_win_event(0x800B, -4))
        self.assertTrue(meaningful_win_event(0x8013, -4))
        self.assertTrue(meaningful_win_event(0x8002, 0))
        self.assertFalse(meaningful_win_event(0xFFFF, -4))


if __name__ == '__main__':
    unittest.main()