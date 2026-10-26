"""Read-only MVK TCP/10230 capture. OFFLINE unless explicit --live --allow-connect."""
import argparse, hashlib, json, socket, struct, time
from collections import Counter
from pathlib import Path
H=33064

def parse_header(b):
    if len(b)!=H or b[24:32]!=b"VAST_MVK": raise ValueError("Invalid VAST_MVK header")
    return [{"adc":i+1,"sensitivity":struct.unpack_from("<f",b,812+i*512)[0],
             "gain":struct.unpack_from("<f",b,836+i*512)[0]} for i in range(8)]

class Audit:
    def __init__(self):
        self.buffer=bytearray();self.header=None;self.frames=Counter()
        self.unknown=Counter();self.counters={};self.gaps=Counter()
        self.status=Counter();self.descriptors={};self.changes=[]
    def feed(self,data):
        self.buffer.extend(data)
        if self.header is None:
            if len(self.buffer)<H:return
            self.header=parse_header(self.buffer[:H]);del self.buffer[:H]
        while len(self.buffer)>=8:
            magic,n=struct.unpack_from("<II",self.buffer)
            if n<8 or n>100000:raise ValueError("Bad frame length")
            if len(self.buffer)<n:return
            f=bytes(self.buffer[:n]);del self.buffer[:n]
            self.frames[str(n)]+=1
            if (magic,n) not in ((0xff800adc,1052),(0xff8001ac,284),
                (0xff800c0d,44),(0xff800c0d,76),
                (0xff800c0d,160),(0xff800c0d,4700)):
                self.unknown[hex(magic)+":"+str(n)]+=1
            if (magic,n)==(0xff800adc,1052):
                ch=struct.unpack_from("<I",f,20)[0];cnt=struct.unpack_from("<I",f,12)[0]
                if ch in self.counters and (cnt-self.counters[ch])%(2**32)!=256:
                    self.gaps[str(ch)]+=1
                self.counters[ch]=cnt
            if (magic,n)==(0xff800c0d,4700):
                for i in range(8):
                    flag=struct.unpack_from("<I",f,28+i*584+580)[0]
                    self.status[str(i+1)+":"+hex(flag)]+=1
            if (magic,n)==(0xff800c0d,160):
                tag=struct.unpack_from("<I",f,28)[0];idx=tag-0x00402130
                if 0<=idx<4096 and idx%512==0:
                    ch=idx//512+1
                    ds=tuple(struct.unpack_from("<I",f,j)[0] for j in (36,52,68,84))
                    if ch in self.descriptors and ds!=self.descriptors[ch]:
                        self.changes.append({"adc":ch,"before":self.descriptors[ch],"after":ds})
                    self.descriptors[ch]=ds
    def result(self):
        return {"header_complete":self.header is not None,"calibration":self.header,
                "frames":dict(self.frames),"unknown":dict(self.unknown),
                "adc_gaps":dict(self.gaps),"statuses":dict(self.status),
                "aux160_descriptors":self.descriptors,"descriptor_changes":self.changes,
                "partial_tail_bytes":len(self.buffer)}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    mode=p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--offline");mode.add_argument("--live",action="store_true")
    p.add_argument("--allow-connect",action="store_true");p.add_argument("--host")
    p.add_argument("--seconds",type=int,default=15);p.add_argument("--output")
    a=p.parse_args();d=Audit();sha=hashlib.sha256()
    if a.offline:
        with open(a.offline,"rb") as f:
            while True:
                b=f.read(65536)
                if not b:break
                sha.update(b);d.feed(b)
        result=d.result();result["sha256"]=sha.hexdigest()
    else:
        if not a.allow_connect or not a.host or not a.output:
            p.error("Explicit --allow-connect --host and --output required")
        if not 1<=a.seconds<=120:p.error("seconds range 1..120")
        dest=Path(a.output);dest.mkdir(parents=True,exist_ok=False)
        start=time.monotonic()
        try:
            with socket.create_connection((a.host,10230),timeout=5) as sock, (dest/"capture.raw").open("wb") as raw, (dest/"recv_times.csv").open("w") as times:
                sock.settimeout(1);times.write("elapsed_seconds,bytes_received\n")
                while time.monotonic()-start<a.seconds:
                    try:b=sock.recv(65536)
                    except socket.timeout:continue
                    if not b:break
                    raw.write(b);sha.update(b);d.feed(b)
                    times.write("{:.6f},{}\n".format(time.monotonic()-start,len(b)))
        finally:
            result=d.result();result["sha256"]=sha.hexdigest()
            (dest/"summary.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result,indent=2))

if __name__=="__main__":main()
