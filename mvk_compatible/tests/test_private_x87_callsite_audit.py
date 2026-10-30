"""Stage111X source-control-flow audit with ONLY synthetic IDR segments."""
from __future__ import annotations
import json
import struct
import pytest
from mvk_compatible.private_original_cw_idr_audit import (
    MAGIC, FPU_INIT_VA, GET_8087_CW_VA, SET_8087_CW_VA,
    FPU_INIT_SIGNATURE, SET_8087_SIGNATURE, GET_8087_SIGNATURE,
    CHANNEL_FRANGE_DEFAULT_VA, DEFAULT_FRANGE_SIGNATURE, TARGET_FPU_WORD_VA,
)
from mvk_compatible.private_x87_callsite_audit import (
    DIRECT_CALLS, PARSER_LOAD_VA, PARSER_SAVE_VA, PARSER_RESTORE_VA,
    PARSER_TEMP_CW_VA, _relative_e8, audit_private_x87_calls, main,
)


def synthetic_x87_idp(path):
    descriptors = [('.text',0x00401000,0x004BE000,0x60000020),
                   ('.itext',0x008BF000,0x3000,0x60000020),
                   ('.data',0x008C2000,0x3000,0xC0000040)]
    segments=[bytearray(size) for _,_,size,_ in descriptors]
    def put(va,content):
        for i,(_,base,size,_) in enumerate(descriptors):
            if base<=va and va+len(content)<=base+size:
                segments[i][va-base:va-base+len(content)]=content
                return
        raise ValueError('Bad synthetic fixture target')
    for va,raw in ((FPU_INIT_VA,FPU_INIT_SIGNATURE),
                   (GET_8087_CW_VA,GET_8087_SIGNATURE),
                   (SET_8087_CW_VA,SET_8087_SIGNATURE),
                   (CHANNEL_FRANGE_DEFAULT_VA,DEFAULT_FRANGE_SIGNATURE),
                   (TARGET_FPU_WORD_VA,struct.pack('<H',0x1332)),
                   (PARSER_TEMP_CW_VA,struct.pack('<H',0x133F)),
                   (PARSER_SAVE_VA,bytes.fromhex('9B D9 7D F4')),
                   (PARSER_LOAD_VA,b'\xD9\x2D'+struct.pack('<I',PARSER_TEMP_CW_VA)),
                   (PARSER_RESTORE_VA,bytes.fromhex('D9 6D F4')),
                   (0x0041BD82,bytes.fromhex('8B C3')),
                   (0x0041BDD8,bytes.fromhex('8B C3')),
                   (0x00448288,bytes.fromhex('66 B8 C0 FF'))):
        put(va,raw)
    for target,sites in DIRECT_CALLS.items():
        for site in sites:
            put(site,_relative_e8(site,target))
    header=bytearray(0x3c);header[:len(MAGIC)]=MAGIC
    struct.pack_into('<I',header,0x38,len(descriptors))
    for name,base,size,flags in descriptors:
        header+=struct.pack('<IIII',base,size,flags,len(name))+name.encode('ascii')
    path.write_bytes(bytes(header)+b''.join(segments))
    return path


@pytest.fixture(scope='module')
def original_free_synthetic(tmp_path_factory):
    return synthetic_x87_idp(tmp_path_factory.mktemp('x87_private_mock')/'mock.idp')


def mutate_va(source,target,va,new_bytes):
    data=bytearray(source.read_bytes());pos=0x3c
    descriptors=[]
    for _ in range(3):
        base,size,_,name_len=struct.unpack_from('<IIII',data,pos)
        descriptors.append((base,size))
        pos+=16+name_len
    offset=pos
    for base,size in descriptors:
        if base<=va and va+len(new_bytes)<=base+size:
            start=offset+va-base
            data[start:start+len(new_bytes)]=new_bytes
            target.write_bytes(data)
            return target
        offset+=size
    raise ValueError('Invalid synthetic patch')


def test_source_static_control_flow_aggregates_only(original_free_synthetic,capsys):
    data=audit_private_x87_calls(original_free_synthetic)
    assert data['original_static_initial_cw_hex']=='0x1332'
    assert data['parser_temporary_cw_hex']=='0x133F'
    assert data['parser_temp_exception_mask']=='0x3F'
    assert data['parser_temp_prec_mode']=='64_bit'
    assert data['source_direct_set8087cw_callsites']==3
    assert data['source_direct_get8087cw_callsites']==4
    assert data['source_direct_fpuinit_callsites']==5
    assert data['source_two_external_callback_wrappers_save_and_restore_cw']
    assert data['source_exception_mask_helper_preserves_pc_rc_bits']
    assert data['source_numeric_parser_saves_and_restores_cw']
    assert data['original_live_process_fpu_cw_at_graph_verified'] is False
    assert data['all_indirect_calls_and_arbitrary_fpu_state_writers_excluded'] is False
    assert data['private_original_bytes_or_paths_in_report'] is False
    assert main([str(original_free_synthetic)])==0
    written=capsys.readouterr().out
    assert json.loads(written)==data
    assert str(original_free_synthetic) not in written


@pytest.mark.parametrize('va,replacement',[
    (0x0041BD84,b'\x90'),
    (0x0041BDD8,b'\x90'),
    (0x00448288,b'\x90'),
    (PARSER_LOAD_VA,b'\x90'),
    (PARSER_SAVE_VA,b'\x90'),
    (PARSER_RESTORE_VA,b'\x90'),
    (PARSER_TEMP_CW_VA,b'\x32'),
])
def test_changed_cw_mutator_or_restoration_fails_closed(
        original_free_synthetic,tmp_path,va,replacement):
    target=mutate_va(original_free_synthetic,tmp_path/'modified.idp',va,replacement)
    with pytest.raises(ValueError):
        audit_private_x87_calls(target)


def test_unreviewed_direct_e8_candidate_does_not_get_certified(
        original_free_synthetic,tmp_path):
    extra_site=0x0041BDE8
    target=SET_8087_CW_VA
    fake=mutate_va(original_free_synthetic,tmp_path/'extra.idp',extra_site,
                   _relative_e8(extra_site,target))
    with pytest.raises(ValueError,match='Unreviewed'):
        audit_private_x87_calls(fake)


def test_all_known_direct_calls_are_deterministic():
    for target,sites in DIRECT_CALLS.items():
        for site in sites:
            encoded=_relative_e8(site,target)
            assert encoded[0]==0xE8
            assert site+5+struct.unpack('<i',encoded[1:])[0]==target
