"""Stage111Z31BA: safe global IDR source inventory on synthetic fixtures.

Does not load operator-private original files and does not execute Windows code.
"""
import json
from pathlib import Path

import pytest

from tools.research.inventory_original_idr_export import (
    read_dfm_structure, read_class_method_addresses, build_index, main,
)


SYNTH_MAIN = """object mvkform: Tmvkform
  Left = 0
  ClientWidth = 1008
  object Pages: TPageControl
    object PageStart: TTabSheet
      object bTaskView: TButton
        Left = 9
        OnClick = bTaskViewClick
      end
    end
    object PageSpectrum: TTabSheet
      object pbSpectrum: TPaintBox
        Width = 767
        OnPaint = pbSpectrumPaint
      end
    end
  end
end
"""
SYNTH_EDITOR = """object mvkeditform: Tmvkeditform
  OnCreate = FormCreate
  object bOk: TButton
    OnClick = bOkClick
  end
end
"""
SYNTH_UNIT128 = """unit _Unit128;
interface
type
  Tmvkform = class(TForm)
  published
    procedure bTaskViewClick(Sender:TObject);//00848E84
    procedure pbSpectrumPaint(Sender:TObject);//0084C910
    procedure mSpecVScale1Click(Sender:TObject);//0084C5AC
  end;
  Tmvkeditform = class(TForm)
  published
    procedure FormCreate(Sender:TObject);//00840630
    procedure bOkClick(Sender:TObject);//00840318
  end;
implementation
end.
"""


def _projects(tmp_path):
    root = tmp_path / "Projects"
    root.mkdir()
    (root / "mvkform.dfm").write_text(SYNTH_MAIN, encoding="latin1")
    (root / "mvkeditform.dfm").write_text(SYNTH_EDITOR, encoding="latin1")
    (root / "_Unit128.pas").write_text(SYNTH_UNIT128, encoding="latin1")
    for n in range(9):
        (root / f"_Unit{n}.pas").write_text(
            "unit OriginalUnit;\ninterface\nimplementation\nend.",
            encoding="latin1")
    (root / "mvkview.dpr").write_text("program mvkview; begin end.")
    return root


def test_source_controls_and_event_names_are_not_duplicated(tmp_path):
    path = tmp_path / "mvkform.dfm"
    path.write_text(SYNTH_MAIN, encoding="latin1")
    nodes=read_dfm_structure(path)
    assert len(nodes)==6
    assert next(n for n in nodes if n["name"]=="pbSpectrum")["page"]=="PageSpectrum"
    assert next(n for n in nodes if n["name"]=="bTaskView")["page"]=="PageStart"
    assert nodes[-1]["geometry"]["Width"]==767


def test_main_form_handler_addresses_derive_from_declared_original_methods(tmp_path):
    f=tmp_path / "_Unit128.pas"
    f.write_text(SYNTH_UNIT128, encoding="latin1")
    va=read_class_method_addresses(f,"Tmvkform")
    assert va["bTaskViewClick"]=="00848E84"
    assert va["pbSpectrumPaint"]=="0084C910"
    assert "mSpecVScale1Click" in va
    assert read_class_method_addresses(f,"TNonexistent")=={}


def test_private_inventory_is_metadata_only_not_original_pas_or_dfm(tmp_path):
    root=_projects(tmp_path)
    idp=tmp_path/"mvkview.idp"
    idp.write_bytes(b"IDR proj v.3"+b"\x00"*64)
    index=build_index(root,idp)
    assert index["dfm_file_count"]==2
    assert index["forms"]["Tmvkform"]["component_count"]==6
    assert index["forms"]["Tmvkform"]["distinct_dfm_handlers"]==2
    assert index["forms"]["Tmvkform"]["resolved_dfm_handlers"]==2
    assert index["forms"]["Tmvkform"]["pages"]=={
        "PageStart":1,"PageSpectrum":1}
    assert index["forms"]["Tmvkform"]["declared_methods_without_direct_dfm_binding"]==[
        "mSpecVScale1Click"]
    assert not index["original_executable_behavior_verified"]
    assert not index["private_source_or_resource_bytes_included"]
    assert "OriginalUnit;" not in json.dumps(index)
    out=tmp_path/"inventory.json"
    assert main(["--projects",str(root),"--idp",str(idp),
                 "--output",str(out)])==0
    assert out.is_file()
    with pytest.raises(SystemExit):
        main(["--projects",str(root),"--idp",str(idp),
              "--output",str(out)])


def test_invalid_idp_and_incomplete_source_fail_closed(tmp_path):
    root=_projects(tmp_path)
    idp=tmp_path/"bad.idp"
    idp.write_bytes(b"NotIDR!")
    with pytest.raises(ValueError):
        build_index(root,idp)
    (root/"mvkview.dpr").unlink()
    with pytest.raises(ValueError):
        build_index(root)
