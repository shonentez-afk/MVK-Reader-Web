#!/usr/bin/env python3
from pathlib import Path
import sys
s=Path(sys.argv[1] if len(sys.argv)>1 else "mvkview_reverse/idr_project/Projects/_Unit128.pas").read_text(errors="replace")
checks={
"alarm list initialization":"008443FC    mov         dword ptr [ebx+esi*4+1084]",
"alarm table":"Tmvkform.tabAlarmResult:TStringGrid",
"row count":"0084770E    call        TMvkCellList.GetMaxCells",
"row label":"0084774E    call        TMvkCellList.GetTitle",
"channel list":"00847768    mov         eax,dword ptr [esi+ebx*4+1084]",
"value display":"00847772    call        TMvkCellList.GetValueText",
"write grid":"00847783    call        TStringGrid.SetCells",
"eight channels":"00847789    cmp         ebx,8",
"all results grid":"Tmvkform.tabAllResult:TStringGrid",
"ADC value list":"Tmvkform.ResultAdcCellList:?",
}
for name,needle in checks.items():
 ok=needle in s
 print("PASS" if ok else "FAIL",name)
 if not ok:sys.exit(1)
print("PASS 10/10")
