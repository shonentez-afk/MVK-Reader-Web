"""Stage111Z31CL source PageStart bitmaps are always PRIVATE local inputs.

No original mvkform.dfm, ilPages, BMP, logo, IDP or binary data is
stored in this test or repo. The fixtures contain only fake header bytes.
"""
import pytest

from ..core.original_pagestart_private_pictures import (
    SOURCE,source_picture_from_dfm,source_start_pictures_from_dfm,
)

_PNG=b"\x89PNG\r\n\x1a\n"+b"FAKE_OFFLINE_TEST_IMAGE_DATA____"*2
_BMP=b"BM"+b"\x00"*60


def _dfm(*,use_png=False):
    lines=["object mvkform: Tmvkform"]
    for name in ("imBackL","imBackR","imLogo"):
        data=(b"\x09TPngImage"+_PNG if use_png else
              b"\x07TBitmap"+len(_BMP).to_bytes(4,"little")+_BMP)
        lines.extend((
            "        object "+name+": TImage",
            "          Picture.Data = {",
            "            "+data.hex().upper(),
            "          }",
            "        end",
        ))
    lines.append("end")
    return ("\n".join(lines)+"\n").encode("ascii")


@pytest.mark.parametrize("format,use_png",(("BMP",False),("PNG",True)))
def test_only_explicit_private_image_headers_are_extracted(format,use_png):
    source=_dfm(use_png=use_png)
    result=source_start_pictures_from_dfm(source)
    assert tuple(result)==("imBackL","imBackR","imLogo")
    assert all(x.format==format for x in result.values())
    assert all(x.bytes.startswith(_PNG[:8] if use_png else b"BM")
               for x in result.values())
    assert all(x.source_is_private for x in result.values())
    assert source_picture_from_dfm(source,"imLogo").name=="imLogo"
    assert not hasattr(result["imLogo"],"url")
    assert SOURCE.startswith("SOURCE_DERIVED_DFM_PAGESTART")


@pytest.mark.parametrize("name",("imBackL","imBackR","imLogo"))
def test_source_image_missing_is_rejected_not_replaced_from_sibling(name):
    source=_dfm()
    source=source.replace(b"object "+name.encode()+b": TImage",
                          b"object someOther: TImage")
    with pytest.raises(ValueError):
        source_picture_from_dfm(source,name)
    with pytest.raises(ValueError):
        source_start_pictures_from_dfm(source)


@pytest.mark.parametrize("input",(
    b"",b"not DFM",b"x"*(12*1024*1024+1),None,"utf8"))
def test_private_picture_loader_rejects_invalid_bounded_source(input):
    with pytest.raises(ValueError):
        source_picture_from_dfm(input,"imLogo")


def test_private_picture_parser_will_not_read_other_delphi_properties():
    with pytest.raises(ValueError):
        source_picture_from_dfm(_dfm(),"anyOtherImage")
    incomplete=_dfm().replace(b"Picture.Data = {",b"Picture.Data = [",1)
    with pytest.raises(ValueError):
        source_start_pictures_from_dfm(incomplete)
