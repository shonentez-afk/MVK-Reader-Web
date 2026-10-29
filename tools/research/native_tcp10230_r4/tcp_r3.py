"""Offline TCP/10230 segment reconstruction and verified application-frame recovery.

No network operations. This module never invents missing TCP bytes. Reordering is
resolved by sorting captured sequence ranges per TCP flow. Disjoint ranges are
reported as gaps. Overlaps must agree byte-for-byte or decoding aborts.
"""
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
import struct

from protocol import (ADC, TACH, PARAM, ID, ACK, DENIED, EXPECTED,
                      MAX, Framer, ProtocolError, decode_samples, decode_records)

MARKERS = tuple(struct.pack('<I',m) for m in (ADC,TACH,PARAM))

@dataclass(frozen=True)
class Segment:
    flow: tuple
    sequence: int
    payload: bytes
    packet_index: int
    flags: int = 0


def iter_pcapng_tcp(path):
    """Read Ethernet/IPv4 TCP payloads in little-endian pcapng EPBs.

    Reject unsupported sections, malformed blocks and fragmented/truncated
    packets rather than silently manufacturing bytes.
    """
    with Path(path).open('rb') as fp:
        section_order = None
        index = 0
        while True:
            h = fp.read(8)
            if not h:
                return
            if len(h) != 8:
                raise ValueError('truncated pcapng block header')
            if h[:4] == b'\x0a\x0d\x0d\x0a':
                bom = fp.read(4)
                if len(bom) != 4:
                    raise ValueError('truncated pcapng section header')
                if bom == b'\x4d\x3c\x2b\x1a':
                    order = '<'
                elif bom == b'\x1a\x2b\x3c\x4d':
                    order = '>'
                else:
                    raise ValueError('invalid pcapng byte-order magic')
                length = struct.unpack(order+'I',h[4:])[0]
                if length < 28 or length > 16_000_000 or length % 4:
                    raise ValueError('invalid section header length')
                rest = fp.read(length-12)
                if len(rest)!=length-12 or struct.unpack(order+'I',rest[-4:])[0]!=length:
                    raise ValueError('truncated or corrupt section header')
                section_order = order
                index += 1
                continue
            if section_order is None:
                raise ValueError('pcapng has no section header')
            length = struct.unpack(section_order+'I',h[4:])[0]
            if length < 12 or length > 16_000_000 or length % 4:
                raise ValueError('invalid pcapng block length')
            b = fp.read(length-8)
            if len(b)!=length-8 or struct.unpack(section_order+'I',b[-4:])[0]!=length:
                raise ValueError('truncated or corrupt pcapng block')
            typ = struct.unpack(section_order+'I',h[:4])[0]
            index += 1
            if typ != 6:
                continue
            if len(b)<24:
                raise ValueError('short enhanced packet block')
            cap_len = struct.unpack_from(section_order+'I',b,12)[0]
            if cap_len > len(b)-24:
                raise ValueError('capture packet length outside enhanced packet block')
            pkt = b[20:20+cap_len]
            if len(pkt)<14:
                continue
            eth = struct.unpack_from('!H',pkt,12)[0]
            off = 14
            for _ in range(2):
                if eth in (0x8100,0x88a8,0x9100):
                    if len(pkt) < off+4:
                        raise ValueError('truncated vlan')
                    eth = struct.unpack_from('!H',pkt,off+2)[0]
                    off+=4
            if eth != 0x0800:
                continue
            ip = pkt[off:]
            if len(ip)<20 or ip[0]>>4!=4 or ip[9]!=6:
                continue
            ihl = (ip[0]&15)*4
            if ihl<20 or len(ip)<ihl+20:
                raise ValueError('bad ipv4 header')
            iplen = struct.unpack_from('!H',ip,2)[0]
            if iplen < ihl+20 or len(ip)<iplen:
                raise ValueError('truncated ipv4 packet')
            frag = struct.unpack_from('!H',ip,6)[0]
            if frag & 0x3fff:
                raise ValueError('ipv4 fragmentation not supported for TCP data')
            tcp=ip[ihl:iplen]
            tcp_header=(tcp[12]>>4)*4
            if tcp_header<20 or len(tcp)<tcp_header:
                raise ValueError('bad tcp header')
            src,dst,seq=struct.unpack_from('!HHI',tcp)
            if src != 10230:
                continue
            payload=tcp[tcp_header:]
            if payload:
                flow=(ip[12:16].hex(),src,ip[16:20].hex(),dst)
                yield Segment(flow,seq,payload,index,tcp[13])


def _relative_seq(seq,base):
    delta=(seq-base)&0xffffffff
    return delta-(1<<32) if delta>=0x80000000 else delta

class OverlapMismatch(ProtocolError):
    pass

class OrderedTcp:
    """Two-pass offline reconstruction; uses original arrival order only for diagnostics.

    `reassemble()` yields ('data',bytes) and ('gap',number_of_bytes) events.
    It retains up to 64 KiB for overlap verification; any farther-back
    retransmission without verifiable content is rejected (fail-closed).
    """
    WINDOW=65536
    def __init__(self, segments, conflict_policy='reject'):
        if conflict_policy not in ('reject','preserve_assembled'):
            raise ValueError('invalid overlap conflict policy')
        self.conflict_policy=conflict_policy
        self.conflicts=[]
        self.segments=list(segments)
        self.stats=Counter()
        self.stats['captured_segments']=len(self.segments)
        self.anchor=self.segments[0].sequence if self.segments else 0
        self._arrival_diagnostics()

    def _arrival_diagnostics(self):
        end=None
        for s in self.segments:
            pos=_relative_seq(s.sequence,self.anchor)
            if end is None: end=pos
            if pos>end:self.stats['arrival_forward_jumps']+=1
            elif pos<end:self.stats['arrival_late_or_repeat']+=1
            end=max(end,pos+len(s.payload))

    def reassemble(self):
        if not self.segments:
            return
        seqs=sorted(self.segments,key=lambda s:(_relative_seq(s.sequence,self.anchor),-len(s.payload)))
        expected=None
        history=bytearray()
        for s in seqs:
            pos=_relative_seq(s.sequence,self.anchor)
            data=s.payload
            if expected is None:expected=pos
            if pos>expected:
                gap=pos-expected
                self.stats['missing_ranges']+=1
                self.stats['missing_bytes']+=gap
                yield ('gap',gap)
                history=bytearray()
                expected=pos
            if pos<expected:
                overlap=min(expected-pos,len(data))
                start=pos-(expected-len(history))
                if start<0:
                    self.stats['overlap_unverifiable']+=1
                    raise OverlapMismatch('retransmission too old to verify')
                if data[:overlap] != history[start:start+overlap]:
                    self.stats['overlap_conflicts']+=1
                    bad=[i for i in range(overlap) if data[i]!=history[start+i]]
                    self.stats['overlap_conflicting_bytes']+=len(bad)
                    self.conflicts.append({'relative_start':pos+bad[0],
                                           'relative_end':pos+bad[-1]+1,
                                           'conflicting_bytes':len(bad),
                                           'capture_packet_number':s.packet_index})
                    if self.conflict_policy=='reject':
                        raise OverlapMismatch('overlap differs at seq %d; first different offset %d'%(pos,bad[0]))
                    # Explicit forensic policy: preserve already assembled bytes;
                    # never claim the conflict-free TCP byte stream is proven.

                self.stats['overlap_segments']+=1
                self.stats['overlap_bytes']+=overlap
                data=data[overlap:]
            if data:
                expected+=len(data)
                history.extend(data)
                if len(history)>self.WINDOW:
                    del history[:len(history)-self.WINDOW]
                self.stats['accepted_bytes']+=len(data)
                yield ('data',data)

class AppCaptureDecoder:
    """Application framer + explicit quarantine/resync after known transport gaps.

    Resync accepts only an actual, fully validated ADC/tach/structured frame.
    It never silently considers the bytes preceding that frame to be valid.
    """
    def __init__(self):
        self.framer=Framer()
        self.seeking=False
        self.scan=bytearray()
        self.stats=Counter()

    def discontinuity(self,missing):
        self.stats['tcp_gaps']+=1
        self.stats['tcp_missing_bytes']+=missing
        if self.seeking:
            self.stats['quarantined_bytes']+=len(self.scan)
            self.scan.clear()
        else:
            self.stats['quarantined_bytes']+=len(self.framer.tail)
        self.framer=Framer()
        self.seeking=True

    @staticmethod
    def _plausible_frame(data,offset):
        if len(data)-offset<8:return None
        kind,n=struct.unpack_from('<II',data,offset)
        if kind in EXPECTED and n not in EXPECTED[kind]:return False
        if kind==PARAM and n<32:return False
        if n<8 or n%4 or n>MAX:return False
        if kind not in (ADC,TACH,PARAM):return False
        if len(data)-offset<n:return None
        raw=bytes(data[offset:offset+n])
        from protocol import Frame
        frame=Frame(kind,n,raw)
        try:
            if kind==PARAM:decode_records(frame)
            else:decode_samples(frame)
        except ProtocolError:
            return False
        return n

    def feed(self,data):
        if not self.seeking:
            try:
                return self.framer.feed(data)
            except ProtocolError:
                self.stats['invalid_aligned_headers']+=1
                self.seeking=True
                self.scan=bytearray(self.framer.tail)
                self.framer=Framer()
                return self._seek_frames()
        self.scan.extend(data)
        return self._seek_frames()

    def _seek_frames(self):
        while True:
            positions=[self.scan.find(m) for m in MARKERS]
            positions=[p for p in positions if p>=0]
            if not positions:
                n=max(0,len(self.scan)-3)
                self.stats['quarantined_bytes']+=n
                if n:del self.scan[:n]
                return []
            pos=min(positions)
            if pos:
                self.stats['quarantined_bytes']+=pos
                del self.scan[:pos]
            length=self._plausible_frame(self.scan,0)
            if length is None:
                return []
            if length is False:
                self.stats['quarantined_bytes']+=1
                del self.scan[0]
                continue
            # Full valid anchor. Do not synthesize preceding or missing bytes.
            self.seeking=False
            self.stats['resync_anchors']+=1
            data=bytes(self.scan)
            self.scan.clear()
            return self.framer.feed(data)

    def finish(self):
        if self.seeking:
            self.stats['quarantined_bytes']+=len(self.scan)
            self.scan.clear()
            return
        if self.framer.tail:
            self.stats['trailing_incomplete_bytes']+=len(self.framer.tail)
            self.framer=Framer()
