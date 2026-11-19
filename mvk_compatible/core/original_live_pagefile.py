"""Original Mode2 PageFile selection, independent of the Native TCP owner.

Source: private _Unit128.pas 0084E914 / 0084E988, mvkform.dfm PageFile.
The original collects 10 channel + 43 SPEC + (6+24+6) VALUES flags.
Go legacy JSON frame marks retain 73 flags; trailing 37 are always disabled.
In compatible Mode2 these are an explicit LOCAL-EXPORT selection only.
Native R6.1 writes its complete RAW stream independently; nothing here
queues TMVKThread.SetRate, WriteData or WriteValues to any instrument.
"""
from __future__ import annotations

from dataclasses import dataclass,replace
from .original_pagefile_recording import (
    CHANNEL_COUNT,SPEC_COUNT,VALUE_COUNT,ADC_VALUE_COUNT,
    BAND_VALUE_COUNT,TACH_RESULT_COUNT,OriginalPageFileSelection,
)
from .offline_measurement_flow import OfflineMeasurementFlow
from .original_mode2_live_health import (
    SOURCE_CHANNEL_KINDS,live_transport_health,
)

SOURCE="IDP_0084E914_0084E988_ORIGINAL_MODE2_LOCAL_FILE_SELECTION"
UNKNOWN="—"
assert (CHANNEL_COUNT,SPEC_COUNT,VALUE_COUNT)==(10,43,73)
assert ADC_VALUE_COUNT+BAND_VALUE_COUNT+TACH_RESULT_COUNT==VALUE_COUNT
SOURCE_RESULT_VALUE_COUNT=6
SOURCE_BAND_VALUE_COUNT=24
SOURCE_TACH_VALUE_COUNT=6
SOURCE_VALUE_COUNT=SOURCE_RESULT_VALUE_COUNT+SOURCE_BAND_VALUE_COUNT+SOURCE_TACH_VALUE_COUNT
assert SOURCE_VALUE_COUNT==36 and VALUE_COUNT==73


def _flags(value,length,label):
    try:
        flags=tuple(value)
    except TypeError as exc:
        raise ValueError(f"{label}: expected source boolean checkboxes") from exc
    if len(flags)!=length or any(type(x) is not bool for x in flags):
        raise ValueError(f"{label}: source requires {length} booleans")
    return flags


@dataclass(frozen=True)
class OriginalLiveFilePlan:
    """User's local export preferences; never modifies Native's raw writer."""
    channels:tuple[bool,...]=(True,)*8+(False,False)
    spec:tuple[bool,...]=(True,)*SPEC_COUNT
    # 36 original flags padded to legacy 73 for existing Go IPC.
    values:tuple[bool,...]=(True,)*30+(False,)*(VALUE_COUNT-30)
    session_id:str|None=None

    def __post_init__(self):
        _flags(self.channels,CHANNEL_COUNT,"cbFileChannels")
        _flags(self.spec,SPEC_COUNT,"cbFileSpec")
        _flags(self.values,VALUE_COUNT,"cbFileValues")
        if any(self.values[SOURCE_VALUE_COUNT:]):
            raise ValueError("Non-original source VALUES flags 36..72 cannot be enabled")
        if self.session_id is not None and (
                not isinstance(self.session_id,str) or
                not 1<=len(self.session_id)<=160 or
                any(c in self.session_id for c in ("/","\\","\x00"))):
            raise ValueError("Source capture session identity is invalid")

    def set_checked(self,group:str,index:int,checked:bool):
        if group not in ("channels","spec","values"):
            raise ValueError("Unknown source PageFile checkbox bank")
        if type(index) is not int or type(checked) is not bool:
            raise ValueError("Source checkbox index and state must be strict")
        source=getattr(self,group)
        if not 0<=index<(SOURCE_VALUE_COUNT if group=="values" else len(source)):
            raise ValueError("Source PageFile checkbox index out of range")
        result=list(source)
        result[index]=checked
        return replace(self,**{group:tuple(result)})

    def bind_status(self,status:dict):
        """Reject mixing sequential captures in the one source Mode2 view."""
        if not isinstance(status,dict):
            raise ValueError("Original Live PageFile needs checked Native status")
        identity=status.get("session_id")
        if identity is None:
            # Legacy synthetic transport tests have no ID; not proof of
            # a specific real session, so never invent an identity.
            if self.session_id is not None:
                raise ValueError("Bound Native run lost its identity")
            return self
        if not isinstance(identity,str) or not 1<=len(identity)<=160:
            raise ValueError("Untrusted Native run identity")
        if self.session_id is not None and self.session_id!=identity:
            raise ValueError("A different Native run cannot inherit PageFile flags")
        return replace(self,session_id=identity)

    def selected(self,group):
        if group not in ("channels","spec","values"):
            raise ValueError("Original PageFile selection group missing")
        flags=getattr(self,group)
        if group=="values":flags=flags[:SOURCE_VALUE_COUNT]
        return tuple(i for i,v in enumerate(flags) if v)

    def receipt(self):
        return {
            "source":SOURCE,
            "source_channel_flag_count":10,
            "source_adc_count":8,
            "source_tach_count":2,
            "source_spec_flag_count":43,
            "source_value_flag_count":SOURCE_VALUE_COUNT,
            "go_legacy_frame_mark_value_flag_count":VALUE_COUNT,
            "non_original_legacy_bits_disabled":not any(self.values[SOURCE_VALUE_COUNT:]),
            "selected_adc_indices":[i+1 for i in self.selected("channels") if i<8],
            "selected_tach_indices":[i-7 for i in self.selected("channels") if i>=8],
            "selected_spec_indices":list(self.selected("spec")),
            "selected_value_indices":list(self.selected("values")),
            "has_native_session_identity":self.session_id is not None,
            "selection_controls_native_r6_raw_capture":False,
            "original_thread_write_data_flag_modified":False,
            "original_thread_write_values_flag_modified":False,
            "device_commands_sent":False,
        }

    def apply_to_verified_flow(self,flow:OfflineMeasurementFlow):
        """Keep checked channels/rows only if NEW offline source proves them.

        This method is called from the actual Native archiveReady Qt event
        after OpenSession SHA validation, not on an unrelated file picker.
        TACH output is unavailable in the checked Native ZIP, so it is
        recorded as unsupported instead of fabricated as two BIN files.
        """
        if not isinstance(flow,OfflineMeasurementFlow):
            raise ValueError("Authenticated export flow is required")
        flow.source_record()
        available=OriginalPageFileSelection.for_flow(flow)
        selected=OriginalPageFileSelection(
            channels=tuple(
                requested and present for requested,present in zip(
                    self.channels,available.channels)),
            spec=tuple(
                requested and present for requested,present in zip(
                    self.spec,available.spec)),
            # Source 6 advanced ResultADC cells are not the offline 24 RMS.
            # Original source 24 BAND maps only to offline 24 VALUES.
            values=tuple(
                self.values[SOURCE_RESULT_VALUE_COUNT+i] and available.values[i]
                for i in range(ADC_VALUE_COUNT)
            )+(False,)*(VALUE_COUNT-ADC_VALUE_COUNT),
        ).validate(flow)
        unavailable_adc=tuple(
            i+1 for i in range(8)
            if self.channels[i] and not available.channels[i])
        unsupported_tach=tuple(
            i-7 for i in range(8,10)
            if self.channels[i] and not available.channels[i])
        unsupported_advanced=tuple(i+1 for i in range(6) if self.values[i])
        unavailable_tach_values=tuple(i+1 for i in range(6) if self.values[30+i])
        return selected,{
            "source":SOURCE,
            "verified_source_bin_rechecked":True,
            "applied_selected_adc":selected.report()["selected_adcs"],
            "applied_selected_native_tach":selected.report()["selected_tachs"],
            "unavailable_adc":list(unavailable_adc),
            "unsupported_original_tach_channels":list(unsupported_tach),
            "unsupported_tach_value_indices":list(unavailable_tach_values),
            "unsupported_original_advanced_result_indices":list(unsupported_advanced),
            "source_live_to_offline_mapping":"ORIGINAL_BAND24_TO_OFFLINE_RMS24_ONLY",
            "native_full_raw_preserved":True,
            "hardware_write_commands_sent":False,
            "same_run_byte_parity_verified":False,
        }


def live_pagefile_channel_rows(status:dict|None):
    """Ten observed source channel rows; counters never become DSP values."""
    if status is None:
        return tuple((f"АЦП {i}" if i<=8 else f"Тахометр {i-8}")
                     +" · ожидание данных" for i in range(1,11))
    health=live_transport_health(status)
    channels=status.get("channels")
    if channels is None:
        return live_pagefile_channel_rows(None)
    if health.channels_observed!=10:
        raise ValueError("Native source status must prove ten ordered channels")
    result=[]
    for n,ch in enumerate(channels,1):
        name=(f"АЦП {n}" if n<=8 else f"Тахометр {n-8}")
        samples=ch.get("samples")
        # Synthetic transport-only receipts may authenticate the 8+2
        # channel ordering WITHOUT providing per-channel RAW counters.
        # Missing is UNKNOWN, never an implicit zero or failed TCP.
        # Real Go status validated by validate_live_status supplies both.
        if samples is not None and (
                type(samples) is not int or samples<0):
            raise ValueError("Unverified Native source sample count")
        rates=ch.get("sample_rates_hz")
        if rates is None:
            rates=[]
        elif (not isinstance(rates,list) or len(rates)>5 or
                any(type(r) is not int or r<=0 or r>1_000_000
                    for r in rates)):
            raise ValueError("Unverified Native source Fs")
        if health.stream_silent:
            label="нет новых пакетов"
        elif ch["sequence_discontinuities"] or ch["nonfinite_samples"]:
            label="ошибка потока"
        elif samples is None:
            label="счётчик ещё не получен"
        elif samples==0:
            label="нет отсчётов"
        else:
            label="поток получен"
        if n>8:
            label+="; TACH RAW не подтверждён"
        frequency=(str(rates[0])+" Гц" if len(rates)==1 else UNKNOWN)
        amount=UNKNOWN if samples is None else str(samples)
        result.append(
            f"{name} · {amount} отсчётов · {frequency} · {label}")
    return tuple(result)
