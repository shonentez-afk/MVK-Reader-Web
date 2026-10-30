"""Synthetic private-ref comparison: no real original values included."""
import json
import math
import pytest
from mvk_compatible.graph_vscale_reference_compare import compare_private_reference, main


def test_local_reference_match_and_mismatch_report_aggregates_only(tmp_path,capsys):
    original=[{'mode':1,'f_range':1.1,'original_graph_default_vscale':2.},
              {'mode':2,'f_range':.31,'original_graph_default_vscale':5.},
              {'mode':3,'f_range':.31,'original_graph_default_vscale':60.}]
    r=compare_private_reference(original,tolerance_relative=1e-4)
    assert r['compared_count']==3
    assert r['matched_count']==2
    assert r['nonmatching_count']==1
    assert r['max_relative_error'] == pytest.approx(1/6)
    assert not r['original_runtime_reference_authenticated']
    assert not r['original_delphi_x87_parity_verified']
    assert r['no_raw_original_values_in_report']
    assert '60.0' not in str(r)
    private=tmp_path/'PRIVATE_LOCAL_ONLY.json'
    private.write_text(json.dumps(original),encoding='utf-8')
    assert main([str(private)])==0
    actual=json.loads(capsys.readouterr().out)
    assert actual['matched_count']==2
    assert str(private) not in str(actual)
    assert '60.0' not in str(actual)


@pytest.mark.parametrize('records',[[],[{}],[{'mode':2,'f_range':1.,'original_graph_default_vscale':False}],
    [{'mode':2,'f_range':1.,'original_graph_default_vscale':-2.}],
    [{'mode':2,'f_range':1.,'original_graph_default_vscale':float('nan')}],
    [{'mode':True,'f_range':1.,'original_graph_default_vscale':2.}],
    [{'mode':2,'f_range':0.,'original_graph_default_vscale':2.}],
])
def test_private_source_invalid_input_rejected(records):
    with pytest.raises(ValueError):compare_private_reference(records)


def test_no_private_values_are_reported_when_count_only():
    obs=compare_private_reference([{'mode':1,'f_range':1.,'original_graph_default_vscale':1.}])
    assert set(obs).isdisjoint({'f_range','original_graph_default_vscale','mode'})
    assert obs['max_relative_error']==0
