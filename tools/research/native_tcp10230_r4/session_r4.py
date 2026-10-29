"""Native MVK 10230 receive-only session model; offline replay, no socket/API writes.

Original IDR evidence: _Unit125.pas TMVKThread.Execute 0x00807A98, 0x00807CAD,
0x00808019, 0x008085FA-0x008087B6. This tracks observed evidence, not
unseen device commands or firmware state. The R3 protocol module is separate.
"""
from collections import Counter
from dataclasses import dataclass
from enum import Enum
import struct

from protocol import (ADC, TACH, PARAM, ID, ACK, DENIED, RegisterImage,
                      ProtocolError, decode_records, decode_samples, calculated)

class Mode(Enum):
    READ_CONFIGURATION = 'task0'
    STREAM = 'task2'

class Phase(Enum):
    NEW = 'new'
    WAITING = 'waiting_for_register_data'
    ACTIVE = 'active'
    SNAPSHOT_DONE = 'snapshot_done'
    FAILED = 'failed'
    CLOSED = 'closed'

@dataclass(frozen=True)
class SessionEvent:
    event: str
    detail: dict

class NativeSession:
    """One connection epoch, no automatic reconnect and no outgoing commands.

    This model corresponds to the receive paths for TMVKThread.Task 0 and 2.
    Other task IDs are intentionally not implemented. Open-ended captures may
    start after the original identification/configuration exchange.
    """
    def __init__(self, mode=Mode.STREAM, expected_rate=None, capture_midstream=False):
        if not isinstance(mode, Mode): raise ValueError('mode must be Mode')
        self.mode=mode
        self.expected_rate=expected_rate
        self.capture_midstream=bool(capture_midstream)
        self.phase=Phase.NEW
        self.registers=RegisterImage()
        self.events=Counter()
        self.frame_types=Counter()
        self.sample_counts=Counter()
        self.identity_observed=False
        self.full_snapshot_observed=False
        self.initialization_observed=False
        self.last_calculated=None
        self.calculation_updates=0
        self.truncated_end_bytes=0
        self.warnings=[]
        self.last_failure=None

    def begin(self):
        if self.phase!=Phase.NEW:
            raise RuntimeError('begin requires a new session')
        self.phase=Phase.WAITING
        self.events['connect_or_capture_start']+=1
        if self.capture_midstream:
            self.warnings.append('capture begins at unknown phase; no inferred handshake')
        return SessionEvent('started',{'midstream':self.capture_midstream})

    def _failure(self,reason):
        self.last_failure=str(reason)
        self.phase=Phase.FAILED
        self.registers=RegisterImage()
        self.last_calculated=None
        self.events['fail_closed']+=1

    def transport_break(self, reason):
        if self.phase in (Phase.CLOSED,Phase.FAILED):return
        self._failure('transport break: '+str(reason))

    def _validated_aux4700(self,frame,blocks):
        if frame.length != 4700:return False
        if len(blocks)!=8:
            raise ProtocolError('4700-byte frame must contain eight records')
        for channel,block in enumerate(blocks):
            if block.address!=0x2000+channel*0x200 or block.words!=0x122:
                raise ProtocolError('unexpected 4700-byte channel record')
        return True

    def ingest(self,frame,validate_samples=True):
        if self.phase not in (Phase.WAITING,Phase.ACTIVE):
            raise RuntimeError('cannot ingest in phase '+self.phase.value)
        self.frame_types[f'0x{frame.kind:08X}/{frame.length}']+=1
        try:
            if frame.kind==ID:
                if frame.length<8:raise ProtocolError('invalid identity frame')
                self.identity_observed=True
                self.events['identity_frames']+=1
                return SessionEvent('identity',{'length':frame.length})
            if frame.kind==ACK:
                if frame.length!=8:raise ProtocolError('unexpected ACK payload')
                self.events['ack_without_issuing_commands']+=1
                return SessionEvent('ack_observed',{'command_executed_by_this_module':False})
            if frame.kind==DENIED:
                if frame.length!=8:raise ProtocolError('unexpected denial payload')
                raise ProtocolError('remote operation denied')
            if frame.kind in (ADC,TACH):
                if validate_samples:
                    x=decode_samples(frame,expected_rate=self.expected_rate)
                    channel=x.channel
                    number=len(x.values)
                else:
                    # Record only a frame header, not sample-data quality.
                    expected_length=1052 if frame.kind==ADC else 284
                    if frame.length!=expected_length:raise ProtocolError('sample length mismatch')
                    _,_,_,channel,rate=struct.unpack_from('<5I',frame.raw,8)
                    if (frame.kind==ADC and channel>=8) or (frame.kind==TACH and channel not in (8,9)):
                        raise ProtocolError('unexpected ADC/tach channel')
                    if self.expected_rate is not None and rate!=self.expected_rate:
                        raise ProtocolError('sample rate differs from session')
                    number=256 if frame.kind==ADC else 64
                self.sample_counts[channel]+=number
                self.events['adc_frames' if frame.kind==ADC else 'tach_frames']+=1
                return None
            if frame.kind!=PARAM:raise ProtocolError('unexpected frame type')
            blocks=decode_records(frame)
            if not blocks:
                self.events['empty_structured']+=1
                return None
            is_aux=self._validated_aux4700(frame,blocks)
            # All decoding and structural validation above must pass before a
            # single register is changed (fail closed on malformed packets).
            for block in blocks:self.registers.put(block)
            self.events['structured_frames']+=1
            self.events['register_blocks']+=len(blocks)
            if len(blocks)==1 and blocks[0].address==0 and blocks[0].words==0x4000:
                self.full_snapshot_observed=True
                self.events['full_register_snapshots']+=1
            if not self.initialization_observed:
                self.initialization_observed=True
                self.events['ready_on_first_valid_register_block']+=1
                if self.mode==Mode.READ_CONFIGURATION:
                    # IDR stage0 -> stage1 -> stage2 and stops after block.
                    self.phase=Phase.SNAPSHOT_DONE
                    return SessionEvent('configuration_read_complete',
                                        {'full_register_snapshot':self.full_snapshot_observed})
                self.phase=Phase.ACTIVE
            if is_aux:
                self.last_calculated=tuple(calculated(self.registers,ch) for ch in range(8))
                self.calculation_updates+=1
                self.events['aux4700_updates']+=1
                return SessionEvent('calculated',{'channels':8,'update':self.calculation_updates})
            if any(b.address==0x3100 for b in blocks):
                self.events['values_row_trigger']+=1
                return SessionEvent('values_tick',{'host_time_required':True})
            return SessionEvent('registers_updated',{'blocks':len(blocks)})
        except (ProtocolError,ValueError) as ex:
            self._failure(str(ex))
            raise

    def end(self,unfinished_bytes=0):
        if unfinished_bytes<0:raise ValueError('invalid unfinished bytes')
        self.truncated_end_bytes=unfinished_bytes
        if unfinished_bytes:
            self.warnings.append('recording ends with incomplete application frame')
            self.events['unfinished_app_frame']+=1
        if self.phase not in (Phase.FAILED,Phase.CLOSED):
            self.phase=Phase.CLOSED
            self.events['close']+=1
        return self.summary()

    def summary(self):
        return {
            'mode':self.mode.value,'phase':self.phase.value,
            'capture_midstream':self.capture_midstream,
            'identity_observed':self.identity_observed,
            'full_snapshot_observed':self.full_snapshot_observed,
            'initialization_observed':self.initialization_observed,
            'calculation_updates':self.calculation_updates,
            'event_counts':dict(self.events),
            'sample_counts_by_channel':dict(self.sample_counts),
            'frame_counts':dict(self.frame_types),
            'truncated_end_bytes':self.truncated_end_bytes,
            'warnings':list(self.warnings),
            'failure':self.last_failure,
        }
