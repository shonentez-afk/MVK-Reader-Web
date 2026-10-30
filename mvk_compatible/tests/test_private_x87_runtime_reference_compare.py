"""Stage111X: synthetic-only bit patterns, NEVER real Delphi observations."""
from __future__ import annotations
import json
import struct
import pytest
from mvk_compatible.private_x87_runtime_reference_compare import (
    SOURCE,SCHEMA,compare_private_x87_runtime_snapshot,main,
)


def bits(value):
    return '0x%08X'%struct.unpack('<I',struct.pack('<f',float(value)))[0]


def synthetic_golden():
    return {'schema':SCHEMA,'records':[
        {'mode':1,'f_range_bits':bits(1.1),
         'graph_default_vscale_bits':bits(2.),'runtime_cw':'0x1372'},
        {'mode':3,'f_range_bits':bits(10.),
         'graph_default_vscale_bits':bits(2000.),'runtime_cw':'0x1332'},
        {'mode':2,'f_range_bits':bits(.31),
         'graph_default_vscale_bits':bits(5.),'runtime_cw':'0x1272'},
    ]}


def test_aggregates_only_and_pcregistration(tmp_path,capsys):
    data=synthetic_golden()
    expected=compare_private_x87_runtime_snapshot(data)
    assert expected['source']==SOURCE
    assert expected['records_count']==3
    assert expected['python_candidate_bitwise_matching_count']==2
    assert expected['python_candidate_bitwise_nonmatching_count']==1
    assert expected['python_candidate_max_positive_float32_ulp_distance']>0
    assert expected['extended_log10_boundary_flagged_count']>=1
    assert expected['extended_log10_boundary_nonmatching_count']==1
    assert expected['runtime_cw_pc_group_counts']=={'24_bit':0,'53_bit':1,'64_bit':2}
    assert expected['runtime_cw_rc_group_counts']['nearest']==3
    assert expected['runtime_cw_matches_static_1332_ignoring_reserved_bit6_count']==2
    assert not expected['operator_provided_runtime_values_independently_authenticated']
    assert not expected['original_delphi_bitwise_parity_accepted']
    assert not expected['original_private_values_cw_or_paths_in_report']
    secret=tmp_path/'PRIVATE_BITS_DO_NOT_UPLOAD.json'
    secret.write_text(json.dumps(data),encoding='utf-8')
    assert main([str(secret)])==0
    output=capsys.readouterr().out
    assert json.loads(output)==expected
    assert str(secret) not in output
    assert '0x1372' not in output
    assert '0x1332' not in output
    assert bits(2000.) not in output


@pytest.mark.parametrize('row_change',[
    {'runtime_cw':'0xFFFFF'},{'runtime_cw':'0x0132'},
    {'f_range_bits':'abc'}, {'f_range_bits':bits(float('nan'))},
    {'graph_default_vscale_bits':bits(0.)},
    {'mode':4},{'mode':True},{'extra':'unsafe'},
])
def test_invalid_or_fabricated_private_bits_fail_closed(row_change):
    doc=synthetic_golden()
    doc['records'][0].update(row_change)
    with pytest.raises(ValueError):compare_private_x87_runtime_snapshot(doc)


def test_rejects_wrong_schema_or_empty_records():
    for doc in ({'schema':SCHEMA,'records':[]},
                {'schema':'wrong','records':synthetic_golden()['records']},
                {'schema':SCHEMA,'records':None},
                {'schema':SCHEMA,'records':synthetic_golden()['records'],'path':'oops'}):
        with pytest.raises(ValueError):compare_private_x87_runtime_snapshot(doc)


def test_path_symlink_and_json_error_do_not_echo_private_file(tmp_path,capsys):
    wrong=tmp_path/'PRIVATE_FAIL.json'
    wrong.write_text('{hidden}',encoding='utf-8')
    with pytest.raises(SystemExit) as e:main([str(wrong)])
    assert e.value.code==2
    assert str(wrong) not in capsys.readouterr().err
    shortcut=tmp_path/'link.json'
    try:shortcut.symlink_to(wrong)
    except OSError:pytest.skip('Platform cannot create symlink')
    with pytest.raises(SystemExit):main([str(shortcut)])
