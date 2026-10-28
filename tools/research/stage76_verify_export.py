#!/usr/bin/env python3
from pathlib import Path
import sys
s=Path(sys.argv[1] if len(sys.argv)>1 else 'mvkview_reverse/idr_project/Projects/_Unit125.pas').read_text(errors='replace')
checks={
'data stage init':'008061CD    mov         dword ptr [ebx+40],2',
'values stage init':'008061D4    mov         dword ptr [ebx+44],2',
'BIN open':'008095ED    call        TFileStream.Create',
'BIN filename':"809A94;'.bin'",
'BIN timestamp':"809A5C;'yyyy-mm-dd--hh-nn-ss'",
'BIN handles':'008095F8    mov         dword ptr [edx+ecx*4+40060],eax',
'BIN stop':'0080980A    mov         dword ptr [eax+40],2',
'VALUES enable':'00809829    cmp         byte ptr [eax+400CF],0',
'VALUES prefix':"809B68;'VALUES-'",
'CSV suffix':"809B84;'.csv'",
'VALUES open':'008098DB    call        TFileStream.Create',
'VALUES handle':'008098E3    mov         dword ptr [edx+40088],eax',
'VALUES header':'00809909    call        00806334',
'VALUES active':'00809977    mov         dword ptr [eax+44],1',
'VALUES clock':'00809986    fstp        qword ptr [eax+404E8]',
'VALUES close':'008099A8    call        TObject.Free',
'VALUES stop':'008099C8    mov         dword ptr [eax+44],2',
'extra file':"809B4C;'ok.txt'"
}
for name,needle in checks.items():
 ok=needle in s
 print('PASS' if ok else 'FAIL',name)
assert all(x in s for x in checks.values())
print('PASS 18/18')
