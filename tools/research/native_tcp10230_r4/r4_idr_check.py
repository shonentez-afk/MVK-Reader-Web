#!/usr/bin/env python3
"""Address-tethered static assertions from original private IDR `_Unit125.pas`.
Does not reproduce or publish the original reverse-engineered source.
"""
import json,re,argparse
from pathlib import Path

ANCHORS={
  'port_10230':('00807C12',r'mov\s+dx,27F6'),
  'connect_timeout_1000ms':('00807C24',r'mov\s+edx,3E8'),
  'read_timeout_5000ms':('00807C34',r'mov\s+edx,1388'),
  'connect_method':('00807CA7',r'TIdTCPClientCustom.Connect'),
  'enter_receive_loop_no_write_before_first_read':('00807CE0',r'jmp\s+0080884C'),
  'first_read_uint32':('00807F78',r'TIdIOHandler.ReadUInt32'),
  'max_application_frame_0x20000':('00807F94',r'cmp\s+ebx,20000'),
  'success_response_type':('0080804F',r'sub\s+eax,10FF0'),
  'denial_response_type_0x10fff':('00808056',r'sub\s+eax,0F'),
  'first_param_stage_one':('00808617',r'mov\s+dword ptr \[eax\+3C\],1'),
  'task0_finishes_after_param':('00808786',r'mov\s+dword ptr \[eax\+3C\],2'),
  'stream_task2_only':('00808724',r'cmp\s+dword ptr \[eax\+54\],2'),
  'id_entry':('00808060',r'test\s+ebx,ebx'),
  'sample_rate_guard':('00808232',r'TMVKThread.MvkSampleRate'),
  'structured_low16_address':('00808464',r'and\s+eax,0FFFF'),
  'structured_high16_words':('0080846F',r'shr\s+eax,10'),
  'structured_register_window':('008084EB',r'cmp\s+eax,4000'),
  'register_copy':('0080856D',r'TIdIOHandler.ReadStream'),
  'parameter_values_trigger':('008085A5',r'cmp\s+dword ptr \[ebp-30\],3100'),
  'client_disconnect':('0080885F',r'TIdTCPConnection.Disconnect'),
  'connection_closed_exception':('0080887A',r'EIdConnClosedGracefully'),
  'read_timeout_exception':('00808882',r'EIdReadTimeout'),
  'connection_timeout_exception':('0080888A',r'EIdConnectTimeout'),
  'error_suppression_in_stage2':('008092BD',r'cmp\s+dword ptr \[ebx\+3C\],2'),
  'rate_queue_address_0x000e':('0080936B',r'mov\s+ecx,0E'),
  'rate_queue_register_count_1':('00809370',r'mov\s+edx,1'),
  'rate_wire_frame_tag':('0080938E',r'mov\s+edx,0FF800C0D'),
  'rate_wire_descriptor':('008093EC',r'shl\s+edx,10'),
  'values_initialization_stage2':('008061D4',r'WriteValuesStage'),
  'bin_initialization_stage2':('008061CD',r'WriteDataStage'),
  'bin_write_buffer':('008082D9',r'mov\s+ecx,dword ptr \[ebp-28\]'),
  'values_header':('00809909',r'call\s+00806334'),
}

def verify(path):
    raw=Path(path).read_bytes().decode('latin-1')
    checked={}
    for label,(address,pattern) in ANCHORS.items():
        line=next((s for s in raw.splitlines() if re.search(r'^\s*>?'+address+r'\s+',s)),None)
        checked[label]=bool(line and re.search(pattern,line))
    return {'total':len(checked),'passed':sum(checked.values()),'failed':[key for key,good in checked.items() if not good], 'checks':checked}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('original_unit125');a=p.parse_args()
    result=verify(a.original_unit125)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    raise SystemExit(bool(result['failed']))
