"""Stage111P private GDI model comparison: only synthetic arrays in repository."""
import json
import numpy as np
import pytest
from mvk_compatible.gdi_xor_reference_compare import compare_private_xor_frames,main
from mvk_compatible.core.tqgrapher_gdi_xor_idr_candidate import OriginalGdiXorCursorModel


def canvas():
    return {'source':'APP_DERIVED_TQGRAPHER_CANVAS_GEOMETRY_IDR_CANDIDATE',
            'pixel_left':2,'pixel_right':12,'pixel_top':3,'pixel_bottom':10}


def cursor():
    return {'source':'APP_DERIVED_TQGRAPHER_CROSSHAIR_IDR_CANDIDATE',
            'drawn':True,'vertical_line':{'start_xy':[6,3],'end_xy':[6,10]},
            'horizontal_lines':[{'series':0,'start_xy':[2,7],'end_xy':[12,7]}]}


def synthetic():
    before=np.random.default_rng(1).integers(0,256,(15,20,3),dtype='uint8')
    after,_=OriginalGdiXorCursorModel(canvas()).update(6,before,cursor())
    return before,after


def test_pixel_error_metadata_and_never_original_arrays():
    original,after=synthetic()
    match=compare_private_xor_frames(
        original,after,canvas=canvas(),crosshair=cursor(),mouse_x=6)
    assert match['pixel_mismatch_count']==0
    assert match['match_source_raster_model']
    assert not match['original_delphi_pixel_parity_verified']
    wrong=after.copy()
    wrong[2,1,0]^=1
    mismatch=compare_private_xor_frames(
        original,wrong,canvas=canvas(),crosshair=cursor(),mouse_x=6)
    assert mismatch['pixel_mismatch_count']==1
    assert mismatch['per_channel_mismatches']['R']==1
    assert not mismatch['match_source_raster_model']
    assert 'array' not in json.dumps(mismatch)


def test_private_cli_handles_synthetic_and_mismatch(tmp_path,capsys):
    before,after=synthetic()
    a,b=tmp_path/'before.npy',tmp_path/'after.npy'
    np.save(a,before);np.save(b,after)
    c,d=tmp_path/'canvas.json',tmp_path/'crosshair.json'
    c.write_text(json.dumps(canvas()),encoding='utf8')
    d.write_text(json.dumps(cursor()),encoding='utf8')
    args=['--before',str(a),'--after',str(b),'--canvas',str(c),
          '--crosshair',str(d),'--mouse-x','6','--confirm-identical-canvas']
    assert main(args)==0
    output=json.loads(capsys.readouterr().out)
    assert output['match_source_raster_model']
    assert not output['original_delphi_pixel_parity_verified']
    assert len(output['local_before_sha256'])==64
    after[4,8,1]^=1;np.save(b,after)
    assert main(args)==1
    bad=json.loads(capsys.readouterr().out)
    assert bad['pixel_mismatch_count']==1


def test_private_cli_rejects_symlink_and_pickle(tmp_path):
    before,after=synthetic()
    a,b=tmp_path/'before.npy',tmp_path/'after.npy'
    np.save(a,before);np.save(b,after)
    link=tmp_path/'link.npy';link.symlink_to(a)
    with pytest.raises(SystemExit) as e:
        main(['--before',str(link),'--after',str(b),
              '--canvas','none','--crosshair','none','--mouse-x','6'])
    assert e.value.code==2
    with pytest.raises(ValueError):
        compare_private_xor_frames(np.zeros((10,10,3),'float64'),after,
                                   canvas=canvas(),crosshair=cursor(),mouse_x=6)
