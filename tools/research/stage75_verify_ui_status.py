#!/usr/bin/env python3
from pathlib import Path
import sys
base=Path(sys.argv[1]) if len(sys.argv)>1 else Path('mvkview_reverse/idr_project/Projects')
u=(base/'_Unit128.pas').read_text(errors='replace')
t=(base/'_Unit125.pas').read_text(errors='replace')
ui=['008493FC    push','00849405    call        TControl.SetText','00849418    call        TFont.SetColor','0084942A    call        TControl.SetVisible','00849437    call        TJvTimer.SetEnabled','00849452    inc         ebx','00849453    cmp         ebx,32','0084945A    call        TControl.SetVisible','00849467    call        TJvTimer.SetEnabled','00849471    mov         dword ptr [eax+0C],ebx','00849596    call        TFont.SetColor','0084A7E6    call        TThread.WaitFor','0084A802    mov         edx,dword ptr [eax+400C8]','0084A80B    call        008493FC','0084A819    cmp         byte ptr [eax+400CC],0','0084A868    call        TWindowMan.SpawnError']
thread=['008092BD    cmp         dword ptr [ebx+3C],2','008092C1    je          008092F0','008092C3    mov         byte ptr [ebx+400CC],1']
for anchor in ui:assert anchor in u,anchor
for anchor in thread:assert anchor in t,anchor
print('PASS 19/19 static anchors')
