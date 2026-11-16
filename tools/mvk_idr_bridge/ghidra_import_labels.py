#@category MVK_IDR
# Ghidra Jython 2 compatible script. Imports reconstructed IDR labels only.
# Changes LABELS IN CURRENT GHIDRA PROJECT, never the target executable.
# Does NOT create functions, patch bytes, or run the program.
from ghidra.program.model.symbol import SourceType
import csv
import re

path=askFile('Choose ghidra_labels.csv from MVK IDR Bridge','Open CSV')
created=0
skipped=0
symtab=currentProgram.getSymbolTable()
with open(path.getAbsolutePath(),'rb') as f:
    records=csv.DictReader(f)
    for r in records:
        try:
            address=toAddr(r['address'].strip())
            if not currentProgram.getMemory().contains(address):
                skipped+=1
                continue
            raw=r['name'].strip()
            # Sanitize Delphi names that are invalid as Ghidra symbols.
            name=re.sub('[^A-Za-z0-9_]', '_', raw)
            if not name or not re.match('[A-Za-z_]',name[0]):name='IDR_'+name
            if len(name)>100:name=name[:85]+'_'+r['address']
            duplicate=False
            for symbol in symtab.getSymbols(address):
                if symbol.getName()==name:
                    duplicate=True
                    break
            if duplicate:
                skipped+=1
                continue
            symtab.createLabel(address,name,SourceType.IMPORTED)
            created+=1
        except Exception:
            skipped+=1
print('MVK IDR labels imported:',created,' skipped:',skipped)