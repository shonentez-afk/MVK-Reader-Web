"""Synthetic offline acceptance. No MVKView, x32dbg, hardware, or private data."""
from __future__ import annotations
import hashlib
import io
import json
from pathlib import Path
import struct
import tempfile
import time
import unittest
import zipfile
from capture_agent.config import CaptureConfig, CaptureError, MemoryWatch
from capture_agent.debugger_import import import_debugger_log
from capture_agent.mcp import handle, serve, TOOLS
from capture_agent.memory import interpret
from capture_agent.session import CaptureService
from capture_agent.store import EvidenceStore, sha256_file


class FakeWindows:
    def __init__(self):
        self.version = 1
        self.alive = True
        self.target = {"pid": 1234, "hwnd": 5678, "class_name": "Tmvkform",
                       "name": "MVKView 1.0.47", "executable": "C:/MVK/mvkview.exe"}
        self.shots = 0

    def targets(self):
        return [self.target] if self.alive else []

    def check_target(self, pid, hwnd):
        if not self.alive or (pid, hwnd) != (1234, 5678):
            raise CaptureError("Target window was lost")

    def snapshot(self, pid, hwnd, limit, uia):
        self.check_target(pid, hwnd)
        return {"target_pid": pid, "target_hwnd": hwnd, "root": {
            "class_name": "Tmvkform", "name": "MVKView 1.0.47"},
            "child_controls": [{"hwnd": 42, "name": "PageSpectrum",
                                "version": self.version}], "truncated": False,
            "uia": bool(uia)}

    def screenshot(self, pid, hwnd, path):
        self.check_target(pid, hwnd)
        self.shots += 1
        Path(path).write_bytes(b"SYNTHETIC PNG DATA" + bytes([self.shots]))
        return {"width": 640, "height": 480}


class ConfigurationTests(unittest.TestCase):
    def test_default_is_nonintrusive(self):
        cfg = CaptureConfig.defaults()
        self.assertFalse(cfg.memory_read)
        self.assertFalse(cfg.save_raw_memory)
        self.assertFalse(cfg.ui_automation)
        self.assertEqual(cfg.watches, ())

    def test_memory_watch_rejects_invalid_and_oversize(self):
        valid = {"name": "power", "address": "0x007D17E7", "size": 4, "encoding": "f32"}
        w = MemoryWatch.parse(valid)
        self.assertEqual(w.address, 0x007D17E7)
        for broken in [dict(valid, address="0x20"), dict(valid, size=2),
                       dict(valid, size=1048577), dict(valid, encoding="str"),
                       dict(valid, name="bad/path"), dict(valid, address="0xFFFFFFFF")]:
            with self.subTest(broken=broken), self.assertRaises(CaptureError):
                MemoryWatch.parse(broken)

    def test_config_requires_optin_for_memory(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "config.json"
            p.write_text(json.dumps({"memory_read": False, "watches": [
                {"name": "x", "address": "0x00F00000", "size": 4, "encoding": "u32"}]}))
            with self.assertRaises(CaptureError):
                CaptureConfig.load(p)
            p.write_text(json.dumps({"memory_read": True, "save_raw_memory": True,
                "watches": [{"name": "x", "address": "0x00F00000", "size": 4, "encoding": "u32"}]}))
            self.assertTrue(CaptureConfig.load(p).save_raw_memory)

    def test_float_decode_little_endian_not_llm_guess(self):
        watch = MemoryWatch.parse({"name":"signal", "address":"0x00800000",
                                   "size":16,"encoding":"f32_array"})
        bits = struct.pack("<4f", 0.5, -1.5, 100.0, 0.0)
        result = interpret(watch, bits)
        self.assertEqual(result["count"], 4)
        self.assertEqual(result["min_finite"], -1.5)
        self.assertEqual(result["sha256"], hashlib.sha256(bits).hexdigest())


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.backend = FakeWindows()
        self.s = CaptureService(backend=self.backend)
        self.cfg = self.base / "config.json"
        self.cfg.write_text(json.dumps({"output_dir": str(self.base / "captures"),
                                        "poll_seconds": 0.25, "screenshot": True}))

    def start(self):
        return self.s.start(acknowledge_local_capture=True, config_path=str(self.cfg))

    def test_explicit_consent_required_and_no_target_fallback(self):
        with self.assertRaises(CaptureError):
            self.s.start(config_path=str(self.cfg))
        self.assertEqual(self.s.status()["status"], "idle")
        self.backend.alive = False
        with self.assertRaises(CaptureError):
            self.start()
        self.assertEqual(self.s.status()["status"], "idle")

    def test_actual_record_and_export_with_sha(self):
        start = self.start()
        self.assertEqual(start["status"], "capturing")
        self.assertEqual(start["snapshots"], 1)
        initial = self.s.session.snapshot(reason="duplicate", only_if_changed=True)
        self.assertFalse(initial["changed"])
        self.backend.version += 1
        snap = self.s.snapshot()
        self.assertTrue(snap["changed"])
        self.assertTrue(snap["screenshot"]["path"].startswith("screenshots/"))
        self.assertEqual(self.s.stop()["status"], "stopped")
        artifact = self.s.export()
        z = Path(artifact["zip"])
        self.assertTrue(z.is_file())
        self.assertEqual(artifact["sha256"], sha256_file(z))
        with zipfile.ZipFile(z) as content:
            manifest = json.loads(content.read("evidence_manifest.json"))
            self.assertEqual(manifest["schema"], "mvk.capture.export.v1")
            self.assertTrue(all(hashlib.sha256(content.read(x["path"])).hexdigest() == x["sha256"]
                                for x in manifest["files"]))
        with self.assertRaises(CaptureError):
            self.s.export()

    def test_debugger_import_does_not_expose_unknown_fields(self):
        self.start()
        trace = self.base / "debug.jsonl"
        trace.write_text(json.dumps({"eip":"0x007D14AA","ebx":"0x02A40E58",
                                     "secret":"should not be exported", "pid":1234})+"\n")
        parsed = self.s.import_debugger(str(trace))
        self.assertEqual(parsed["imported_events"], 1)
        self.s.stop()
        data = (self.s.session.store.path / "timeline.jsonl").read_text()
        self.assertIn("007D14AA", data)
        self.assertNotIn("should not be exported", data)
        self.assertIn(hashlib.sha256(trace.read_bytes()).hexdigest(), data)

    def test_memory_never_included_by_default(self):
        self.start()
        reply = self.s.snapshot(include_memory=True)
        self.assertEqual(reply["memory_watches"], 0)
        self.s.stop()
        self.assertEqual(list((self.s.session.store.path / "memory").glob("*.bin")), [])

    def test_exited_target_stops_capture_without_retargeting(self):
        self.start()
        self.backend.alive = False
        time.sleep(0.6)
        self.assertEqual(self.s.status()["status"], "failed")
        self.assertIn("Target window was lost", self.s.status()["last_error"])
        self.s.stop()

    def test_mcp_stdio_and_start_acknowledgement(self):
        self.assertEqual(handle(self.s, {"jsonrpc":"2.0","id":1,"method":"ping"})["result"], {})
        names = {x["name"] for x in handle(self.s, {"id":2,"method":"tools/list"})["result"]["tools"]}
        self.assertIn("mvk_capture_snapshot", names)
        rejected = handle(self.s, {"id":3,"method":"tools/call","params":{"name":"mvk_capture_start","arguments":{"acknowledge_local_capture":False}}})
        self.assertTrue(rejected["result"]["isError"])
        ok = handle(self.s, {"id":4,"method":"tools/call","params":{"name":"mvk_capture_start","arguments":{"acknowledge_local_capture":True,"config_path":str(self.cfg)}}})
        self.assertFalse(ok["result"]["isError"])
        self.assertEqual(ok["result"]["structuredContent"]["status"], "capturing")
        self.s.stop()
        inp = io.StringIO('{"jsonrpc":"2.0","id":7,"method":"tools/list"}\n')
        out = io.StringIO()
        serve(self.s, inp, out)
        self.assertIn("mvk_capture_discover", out.getvalue())


if __name__ == "__main__":
    unittest.main()