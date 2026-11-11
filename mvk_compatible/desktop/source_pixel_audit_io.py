"""Stage111Z31AZ: explicit, LOCAL-ONLY Qt PNG audit export and readback.

The operator chooses an output directory. The command makes one new folder
with ONLY the candidate offscreen TCo2Draw source bitmap + whitelisted JSON.
Never exports original IDP/PAS/DFM, original screenshots or raw FFT/BIN.
No sockets, cloud upload, auto-screenshots or original-process access.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import secrets

import numpy as np
from PySide6.QtGui import QImage

from ..core.spectrum_graph_pixel_audit import (
    make_source_pixel_manifest,
)


def read_png_rgba(filename) -> np.ndarray:
    """Decode local PNG as opaque RGBA for independent pixel QA."""
    path=Path(filename)
    if not path.is_file() or path.suffix.lower() != ".png":
        raise ValueError("An explicit local PNG filename is required")
    if path.stat().st_size > 100_000_000:
        raise ValueError("Unbounded local screenshot file")
    im=QImage(str(path))
    if im.isNull():
        raise ValueError("Qt could not decode local PNG")
    if (im.width()<64 or im.height()<64 or
            im.width()*im.height()>6_000_000):
        raise ValueError("Local PNG pixel dimensions outside audit limit")
    im=im.convertToFormat(QImage.Format_RGBA8888)
    stride=im.bytesPerLine()
    raw=np.frombuffer(
        im.constBits(),dtype=np.uint8,count=im.height()*stride)
    result=raw.reshape(im.height(),stride)[:,:im.width()*4]
    result=result.reshape(im.height(),im.width(),4).copy()
    if not bool(np.all(result[:,:,3]==255)):
        raise ValueError("Transparency makes original bitmap comparison invalid")
    return result


def save_source_graph_pixel_audit(
        destination_directory, *, bitmap, canvas, spectrum,
        view_x, view_y, qt_device_pixel_ratio,
        textout_diagnostics=None) -> Path:
    """Save the candidate to a NEW user-selected folder, never overwrite.

    Caller must explicitly open the research-only local export dialog.
    Bitmap is pristine TCo2Draw canvas WITHOUT the transient XOR cursor,
    so the operator's original crop must be acquired without cursor.
    """
    parent=Path(destination_directory).expanduser()
    if not parent.is_dir():
        raise ValueError("Operator must explicitly choose an existing folder")
    manifest=make_source_pixel_manifest(
        bitmap,canvas,spectrum=spectrum,view_x=view_x,view_y=view_y,
        qt_device_pixel_ratio=qt_device_pixel_ratio,
        textout_diagnostics=textout_diagnostics)
    h,w=bitmap.shape[:2]
    packed=np.ascontiguousarray(bitmap,dtype=np.uint8)
    # Copy the underlying pixels before NumPy releases/mutates storage.
    qt_image=QImage(
        packed.tobytes(),w,h,w*4,QImage.Format_RGBA8888).copy()
    folder=parent/(
        "MVK_SPECTRUM_PIXEL_QA_"+
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_")+
        secrets.token_hex(4))
    folder.mkdir(mode=0o700)
    png=folder/"candidate_source_bitmap.png"
    if not qt_image.save(str(png),"PNG"):
        raise OSError("Cannot save candidate source PNG")
    if not np.array_equal(read_png_rgba(png),packed):
        raise OSError("Qt PNG round-trip altered a source bitmap pixel")
    manifest["candidate_png_filename"]="candidate_source_bitmap.png"
    manifest["original_png_is_not_present"]=True
    manifest["local_export_requires_explicit_operator_action"]=True
    json_path=folder/"candidate_manifest.json"
    # x prevents accidental overwrite even on colliding folder names.
    with json_path.open("x",encoding="utf-8") as out:
        json.dump(manifest,out,ensure_ascii=False,sort_keys=True,indent=2)
        out.write("\n")
    return folder
