import hashlib
import sys

import numpy as np

from ..core import bundled_offline_fir as fir


def test_no_sidecar_and_bad_bundle_fails_closed(tmp_path, monkeypatch):
    raw = np.ones((10, 512), dtype="<f4").tobytes()
    monkeypatch.setattr(fir, "_PACKAGED_SHA256", hashlib.sha256(raw).hexdigest())
    bundle = tmp_path / "bundle"
    (bundle / "mvk_fir").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "offline_fir.bin").write_bytes(raw)
    assert fir.load_frozen_offline_fir() is None
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    resource = bundle / "mvk_fir" / fir._PACKAGED_NAME
    assert fir.load_frozen_offline_fir() is None
    resource.write_bytes(bytes(len(raw)))
    assert fir.load_frozen_offline_fir() is None
    resource.write_bytes(raw)
    loaded = fir.load_frozen_offline_fir()
    assert loaded.banks.tobytes() == raw
    assert not loaded.banks.flags.writeable
    assert loaded.provenance == "BUNDLED_VERIFIED_OFFLINE_FIR"
