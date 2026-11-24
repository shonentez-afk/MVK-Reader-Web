"""Independent source-local TACH state and SHA-bound admission replay.

No Float32 interpretation of TACH. Original 00806030 compares to the
previous last BYTE, sets a DWORD, and preserves the last byte on tick reset.
A later PARAM may overwrite either local word, without mutating RAW.
"""
from hashlib import sha256
from pathlib import Path
import json
import re
import struct

SCHEMA="MVK_SOURCE_LOCAL_TACH_LATCH_V1"
GATE_NAME="SOURCE_LOCAL_TACH_GATE.jsonl"
TACH_TYPE=0xFF8001AC
RATES={512,2048,8192,32768,65536}


class TachLatch:
    def __init__(self):
        self.last=[0,0]
        self.values=[0,0]
        self.mask=[0,0]

    def sample(self,tach,payload):
        if payload:
            if any(value!=self.last[tach] for value in payload):
                self.values[tach]=1
                self.mask[tach]=3
            self.last[tach]=payload[-1]

    def block(self,addr,words):
        for ch in range(2):
            for i in range(2):
                if addr<=0x30fe+ch*0x100+i<addr+words:
                    self.mask[ch]&=~(1<<i)

    def tick(self):
        self.values=[0,0]
        self.mask=[3,3]

    def projection(self,data,valid):
        out=[]
        for ch in range(2):
            addr=0x30fe+ch*0x100
            raw=bytearray(4)
            known=True
            for i in range(2):
                if self.mask[ch]&(1<<i):
                    raw[2*i]=self.values[ch] if i==0 else 0
                elif valid[addr+i]:
                    raw[2*i:2*i+2]=data[2*(addr+i):2*(addr+i+1)]
                else:
                    known=False
            out.append((self.mask[ch],raw.hex() if known else None))
        return tuple(out)


class TachGateReader:
    def __init__(self,path,*,expected_sha256,expected_records,expected_frames):
        self.path=Path(path)
        if (self.path.is_symlink() or not self.path.is_file() or
                self.path.stat().st_size>1500000000 or
                not isinstance(expected_sha256,str) or
                not re.fullmatch(r"[0-9a-f]{64}",expected_sha256) or
                type(expected_records) is not int or
                not 0<=expected_records<=min(expected_frames,4000000)):
            raise ValueError("Source local TACH: invalid gate evidence")
        self.sha=expected_sha256
        self.count=expected_records
        self.digest=sha256()
        self.records=0
        self.state=TachLatch()
        self.file=None

    def __enter__(self):
        self.file=self.path.open("rb")
        return self

    def __exit__(self,*args):
        self.file.close()

    def consume(self,frame_index,frame):
        if len(frame)<28 or len(frame)%4:
            raise ValueError("Source local TACH: malformed frame")
        if len(frame)==28:
            return
        ch,rate=struct.unpack_from("<II",frame,20)
        if ch not in (8,9) or rate not in RATES:
            raise ValueError("Source local TACH: invalid channel/rate")
        line=self.file.readline(2049)
        if not line or len(line)>2048 or self.records>=self.count:
            raise ValueError("Source local TACH: missing/oversized gate record")
        self.digest.update(line)
        self.records+=1
        row=json.loads(line)
        if not isinstance(row,dict):
            raise ValueError("Source local TACH: invalid gate record")
        selected=row.get("selected_rate_hz")
        frozen=row.get("freeze_update")
        if type(selected) is not int or selected not in RATES or type(frozen) is not bool:
            raise ValueError("Source local TACH: invalid admission state")
        accepted=not frozen and selected==rate
        expected=dict(schema=SCHEMA,frame_index_one_based=frame_index,
            frame_sha256=sha256(frame).hexdigest(),channel=ch+1,
            selected_rate_hz=selected,freeze_update=frozen,
            source_receive_gate_accepted=accepted)
        if row!=expected or type(row.get("source_receive_gate_accepted")) is not bool:
            raise ValueError("Source local TACH: RAW/gate mismatch")
        if accepted:
            self.state.sample(ch-8,frame[28:])

    def finish(self):
        if (self.file.read(1) or self.records!=self.count or
                self.digest.hexdigest()!=self.sha):
            raise ValueError("Source local TACH: gate SHA/count mismatch")
