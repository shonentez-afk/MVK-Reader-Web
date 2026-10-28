#!/usr/bin/env python3
from pathlib import Path
import sys
s=Path(sys.argv[1] if len(sys.argv)>1 else 'mvkview_reverse/idr_project/Projects/_Unit125.pas').read_text(errors='replace')
checks={
'task_3_5_gate':'00807D01    sub         eax,3',
'stage_1_gate':'00807D0D    cmp         dword ptr [eax+3C],1',
'save_flash':'00807E15    mov         edx,0F0001',
'restart':'00807E30    mov         edx,10F0F',
'set_stage_2':'00807E83    mov         dword ptr [eax+3C],2',
'first_read_type':'00807F78    call        TIdIOHandler.ReadUInt32',
'second_read_length':'00807F84    call        TIdIOHandler.ReadUInt32',
'length_alignment':'00807F8D    and         eax,3',
'length_limit':'00807F94    cmp         ebx,20000',
'length_min':'00807F9C    cmp         ebx,8',
'ok_branch':'00808054    je          0080807B',
'denied_branch':'00808059    je          008080AC',
'task_success_gate':'00808091    sub         eax,3',
'stage_success_gate':'0080809D    cmp         dword ptr [eax+3C],2',
'exit_success':'008080A1    je          00808859',
'denied_exception':'008080E1    call        @RaiseExcept',
'disconnect':'0080885F    call        TIdTCPConnection.Disconnect',
'read_timeout':'00807C34    mov         edx,1388',
'connect_timeout':'00807C24    mov         edx,3E8',
'timeout_exception':'EIdReadTimeout',
'closed_exception':'EIdConnClosedGracefully',
}
for k,n in checks.items():
 print('PASS' if n in s else 'FAIL',k)
assert all(n in s for n in checks.values())
print('PASS 21/21')
