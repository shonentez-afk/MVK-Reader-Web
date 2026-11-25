"""Optional authorized, verified offline FIR resource in a frozen build."""
import hashlib
from pathlib import Path
import sys
import numpy as np
from .envelope_idr_candidate import EnvelopeProfile

_PACKAGED_SHA256 = "c77da997615095a0241e47e3099597db8d58a005af52aa6a2a2abfcb488b7645"
_PACKAGED_NAME = "offline_fir.bin"
_PROVENANCE = "BUNDLED_VERIFIED_OFFLINE_FIR"

def load_frozen_offline_fir():
    """Return the pinned bank only from the frozen app's resource location."""
    if not getattr(sys, "frozen", False) or not getattr(sys, "_MEIPASS", None):
        return None
    path = Path(sys._MEIPASS) / "mvk_fir" / _PACKAGED_NAME
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size != 20480:
            return None
        with path.open("rb") as handle:
            raw = handle.read(20481)
        if len(raw) != 20480 or hashlib.sha256(raw).hexdigest() != _PACKAGED_SHA256:
            return None
        return EnvelopeProfile(np.frombuffer(raw, dtype="<f4").reshape(10, 512),
                               provenance=_PROVENANCE)
    except (OSError, ValueError):
        return None
