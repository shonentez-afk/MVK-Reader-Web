"""Offline regression for the user's real v0.3 all-black Delphi popup PNGs.

Tests use synthetic PIL images / injected Windows API stubs. They do not test
live Windows physical coordinates or attach to the original MVKView.
"""
from __future__ import annotations
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase, mock
import tempfile
import time

from PIL import Image, ImageDraw
from capture_agent.config import CaptureConfig, CaptureError
from capture_agent.windows import WindowsBackend
from capture_agent.session import CaptureSession
from test_capture_agent import FakeWindows


def menu_image():
    im = Image.new('RGB', (369, 580), 'white')
    ImageDraw.Draw(im).rectangle((9, 9, 250, 290), outline='black', width=4)
    return im


class PopupBlackImageRegressionTests(TestCase):
    def backend(self):
        b = WindowsBackend.__new__(WindowsBackend)
        b.targets = lambda: [{"pid": 1234, "hwnd": 5678, "minimized": False}]
        b.u = SimpleNamespace(IsWindow=lambda x: True,
                              IsWindowVisible=lambda x: True)
        b.pid_for_hwnd = lambda hwnd: 1234
        b._class = lambda hwnd: '#32768' if int(hwnd) == 9090 else 'Tmvkform'
        return b

    def test_all_black_popup_triggers_bounded_foreground_verified_fallback(self):
        b=self.backend()
        grabber=mock.Mock()
        grabber.grab.side_effect=[Image.new('RGB', (369,580), 'black')]
        b._grab_verified_popup=mock.Mock(return_value=menu_image())
        with tempfile.TemporaryDirectory() as tmp, mock.patch('PIL.ImageGrab.grab', new=grabber.grab):
            path=Path(tmp)/'popup.png'
            metadata=b.screenshot(1234,9090,path)
            self.assertTrue(path.is_file())
            self.assertEqual(metadata['capture_method'],'bounded_visible_menu_foreground_verified')
            self.assertFalse(b._image_is_solid(Image.open(path)))
            b._grab_verified_popup.assert_called_once()

    def test_black_popup_cannot_pass_as_a_valid_screenshot_on_fallback_failure(self):
        b=self.backend()
        b._grab_verified_popup=mock.Mock(side_effect=CaptureError('Popup is occluded'))
        with tempfile.TemporaryDirectory() as tmp, mock.patch('PIL.ImageGrab.grab', return_value=Image.new('RGB',(369,580),'black')):
            path=Path(tmp)/'popup.png'
            with self.assertRaisesRegex(CaptureError,'occluded'):
                b.screenshot(1234,9090,path)
            self.assertFalse(path.exists())

    def test_regular_window_preserves_old_window_bound_screenshot(self):
        b=self.backend()
        b._grab_verified_popup=mock.Mock(side_effect=AssertionError('must not fallback'))
        with tempfile.TemporaryDirectory() as tmp, mock.patch('PIL.ImageGrab.grab', return_value=Image.new('RGB',(1920,986),'white')):
            meta=b.screenshot(1234,5678,Path(tmp)/'main.png')
            self.assertEqual(meta['capture_method'],'window')
            b._grab_verified_popup.assert_not_called()

    def test_popup_region_requires_foreground_target_and_all_three_hit_points(self):
        b=self.backend()
        b._physical_window_rect=lambda hwnd: (24,190,393,770)
        b.wt=SimpleNamespace(POINT=lambda x,y:(x,y))
        b.u=SimpleNamespace(IsWindowVisible=lambda hwnd:True,
            GetForegroundWindow=lambda:5678,
            WindowFromPoint=lambda point:9090,
            GetAncestor=lambda hwnd, type:9090)
        grabber=mock.Mock()
        grabber.grab.return_value=menu_image()
        im=b._grab_verified_popup(1234,9090,grabber)
        self.assertFalse(b._image_is_solid(im))
        grabber.grab.assert_called_once_with(bbox=(24,190,393,770),all_screens=True,
                                             include_layered_windows=True)
        b.pid_for_hwnd=lambda hwnd:4321 if hwnd==5678 else 1234
        with self.assertRaisesRegex(CaptureError, 'not foreground'):
            b._grab_verified_popup(1234,9090,grabber)
        b.pid_for_hwnd=lambda hwnd:1234 if hwnd in (5678,9090) else 4321
        b.u.WindowFromPoint=lambda point: 9999
        with self.assertRaisesRegex(CaptureError, 'another application'):
            b._grab_verified_popup(1234,9090,grabber)

    def test_popup_region_rejects_oversized_or_ambiguous_bounds(self):
        b=self.backend()
        b._physical_window_rect=lambda hwnd:(0,0,1500,2000)
        b.wt=SimpleNamespace(POINT=lambda x,y:(x,y))
        b.u=SimpleNamespace(IsWindowVisible=lambda hwnd:True,
            GetForegroundWindow=lambda:5678,
            WindowFromPoint=lambda point:9090,GetAncestor=lambda hwnd,t:9090)
        with self.assertRaisesRegex(CaptureError, 'strict size limits'):
            b._grab_verified_popup(1234,9090,mock.Mock())


class PopupFailureEvidenceTests(TestCase):
    def test_capture_failure_records_reason_and_no_false_png_claim(self):
        import json
        from dataclasses import replace
        from test_capture_popup_v03 import FakePopupBackend
        class FailingPopupBackend(FakePopupBackend):
            def screenshot(self, pid, hwnd, path):
                if hwnd == 9090:
                    raise CaptureError("Popup is occluded or Windows capture is black")
                return super().screenshot(pid, hwnd, path)
        class NoOpObserver:
            def __init__(self,pid,q):pass
            def start(self):pass
            def stop(self):pass
        with tempfile.TemporaryDirectory() as tmp:
            b=FailingPopupBackend()
            cfg=replace(CaptureConfig.defaults(),output_dir=Path(tmp),poll_seconds=60)
            s=CaptureSession(cfg,b,b.target,observer_factory=NoOpObserver)
            s.start()
            try:
                b.popup_open=True
                s.snapshot(reason="poll",screenshot=False,only_if_changed=True)
                lines=(s.store.path/'timeline.jsonl').read_text().splitlines()
                last=json.loads(lines[-1])['payload']
                self.assertEqual(last['popup_capture_failures'][0]['hwnd'],9090)
                self.assertIn('capture is black',last['popup_capture_failures'][0]['reason'])
                self.assertNotIn('additional_process_windows',last)
            finally:
                s.stop()


class SettledCaptureRegressionTests(TestCase):
    def test_page_show_schedules_stable_frame_even_after_poll(self):
        class Backend(FakeWindows):
            def snapshot(self, pid, hwnd, limit, uia):
                v=super().snapshot(pid,hwnd,limit,uia)
                v['child_controls'].append({"hwnd":72,"name":"Спектр",
                                            "class_name":"TTabSheet","visible":True})
                return v
        with tempfile.TemporaryDirectory() as tmp:
            cfg=CaptureConfig.defaults()
            from dataclasses import replace
            cfg=replace(cfg,output_dir=Path(tmp),poll_seconds=60)
            b=Backend()
            class NoOpObserver:
                def __init__(self,pid,q):pass
                def start(self):pass
                def stop(self):pass
            s=CaptureSession(cfg,b,b.target,observer_factory=NoOpObserver)
            s.start()
            try:
                s.incoming.put({'event':'OBJECT_SHOW','hwnd':72,'object_id':0,'child_id':0})
                deadline=time.monotonic()+2.0
                while time.monotonic()<deadline:
                    if s.store.meta['snapshots']>=2:
                        break
                    time.sleep(.04)
                self.assertGreaterEqual(s.store.meta['snapshots'],2)
                items=[__import__('json').loads(q) for q in
                       (s.store.path/'timeline.jsonl').read_text().splitlines()]
                self.assertTrue(any(x['kind']=='snapshot' and
                    x['payload']['reason']=='page_settled' and
                    'screenshot' in x['payload'] for x in items))
            finally:
                s.stop()

if __name__=='__main__':
    import unittest
    unittest.main()