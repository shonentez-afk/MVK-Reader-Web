#!/usr/bin/env python3
from pathlib import Path
p=Path('mvkview_reverse/idr_project/Projects')
s=(p/'_Unit125.pas').read_text(errors='replace')
t=(p/'_Unit128.pas').read_text(errors='replace')
checks=[
'0080887A    dd          007D2600;EIdConnClosedGracefully',
'00808882    dd          007EC3E4;EIdReadTimeout',
'0080888A    dd          007ECB4C;EIdConnectTimeout',
'errDisconnected','errNotResponding','errCannotConnect','errTransferError',
'008092BD    cmp         dword ptr [ebx+3C],2',
'008092C1    je          008092F0',
'008092C3    mov         byte ptr [ebx+400CC],1',
'008092D2    call        @UStrAsg',
'008080E1    call        @RaiseExcept',
'00807E83    mov         dword ptr [eax+3C],2',
'008080A1    je          00808859']
checks_ui=['0084A7E6    call        TThread.WaitFor','0084A7F4    call        TWindowMan.HideWait','0084A80B    call        008493FC','0084A819    cmp         byte ptr [eax+400CC],0','0084A868    call        TWindowMan.SpawnError','0084A876    call        TObject.Free','0084A880    mov         dword ptr [eax+0BE0],edx']
assert all(x in s for x in checks) and all(x in t for x in checks_ui)
print('PASS 21/21 compact static checks')
