"""Source PageStart optional private TImage backgrounds; no assets bundled.

The operator's own mvkform.dfm contains imBackL, imBackR and imLogo
TPicture.Data properties. This strict reader extracts exactly those three
Picture.Data blobs in memory WHEN EXPLICITLY PROVIDED a local original DFM.
It does not require access to the original EXE, install original assets,
execute Delphi, read a device, or publish data in a GitHub artifact.

The original image bytes and their hashes must stay private.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

SOURCE="SOURCE_DERIVED_DFM_PAGESTART_PRIVATE_IMAGE_LOADER_STAGE111Z31CL"
_ALLOWED=("imBackL","imBackR","imLogo")
_MAX_DFM_BYTES=12*1024*1024
_MAX_PICTURE_BYTES=8*1024*1024
_PNG_SIGNATURE=b"\x89PNG\r\n\x1a\n"


@dataclass(frozen=True)
class PrivateDfmPicture:
    name: str
    format: str
    bytes: bytes

    @property
    def source_is_private(self):
        return True


def source_picture_from_dfm(dfm:bytes,name:str)->PrivateDfmPicture:
    """Bounded source TPicture stream extractor, never an arbitrary DFM parser.

    The BMP or PNG header begins after Delphi's picture-class stream
    header, e.g. 0x07+'TBitmap'+length or 0x09+'TPngImage'. The returned
    bytes are in memory only and must NOT be committed to the public repo.
    """
    if name not in _ALLOWED:
        raise ValueError("Only the three original source PageStart pictures")
    if (not isinstance(dfm,bytes) or not 1<=len(dfm)<=_MAX_DFM_BYTES):
        raise ValueError("Bounded operator-provided text DFM bytes required")
    text=dfm.decode("latin1")
    marker=re.search(r"(?m)^\s*object\s+"+re.escape(name)+
                     r":\s*TImage\s*$",text)
    if marker is None:
        raise ValueError("Original DFM missing source TImage: "+name)
    # Picture.Data belongs to this object; never search a sibling TImage
    # after a missing property or silently borrow another picture.
    remainder=text[marker.end():]
    object_end=re.search(r"(?m)^\s{8}end\s*$",remainder)
    if object_end is None:
        raise ValueError("Unterminated source TImage object")
    image_block=remainder[:object_end.start()]
    payload=re.search(
        r"Picture\.Data\s*=\s*\{([0-9a-fA-F\s]+)\}",image_block)
    if payload is None:
        raise ValueError("Source TImage does not contain text Picture.Data")
    compact=re.sub(r"\s+","",payload.group(1))
    if (not compact or len(compact)%2!=0
            or len(compact)>2*_MAX_PICTURE_BYTES):
        raise ValueError("Oversized or malformed source picture")
    stream=bytes.fromhex(compact)
    # Refuse arbitrary code or file formats. A valid Qt decoder also
    # validates actual bitmap dimensions and pixel payload separately.
    png=stream.find(_PNG_SIGNATURE,0,40)
    bmp=stream.find(b"BM",0,40)
    if png>=0 and (bmp<0 or png<bmp):
        header=png;image_type="PNG"
    elif bmp>=0:
        header=bmp;image_type="BMP"
    else:
        raise ValueError("Unsupported source Delphi picture serialization")
    image=stream[header:]
    if (len(image)<32 or len(image)>_MAX_PICTURE_BYTES):
        raise ValueError("Invalid source image byte size")
    return PrivateDfmPicture(name,image_type,image)


def source_start_pictures_from_dfm(dfm:bytes)->dict[str,PrivateDfmPicture]:
    """Three source pictures or fail-closed; no partial replacement."""
    return {name:source_picture_from_dfm(dfm,name) for name in _ALLOWED}
