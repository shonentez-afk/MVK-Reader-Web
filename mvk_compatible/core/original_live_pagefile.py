"""Original Mode2 PageFile selection, independent of the Native TCP owner.

Source: private _Unit128.pas 0084E914 / 0084E988, mvkform.dfm PageFile.
The original collects 10 channel + 43 SPEC + (24+43+6) VALUES flags.
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
    values:tuple[bool,...]=(
        (True,)*(ADC_VALUE_COUNT+BAND_VALUE_COUNT)
        +(False,)*TACH_RESULT_COUNT)
    session_id:str|None=None

    def __post_init__(self):
        _flags(self.channels,CHANNEL_COUNT,"cbFileChannels")
        _flags(self.spec,SPEC_COUNT,"cbFileSpec")
        _flags(self.values,VALUE_COUNT,"cbFileValues")
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
        if not 0<=index<len(source):
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
        return tuple(i for i,v in enumerate(getattr(self,group)) if v)

    def receipt(self):
        return {
            "source":SOURCE,
            "source_channel_flag_count":10,
            "source_adc_count":8,
            "source_tach_count":2,
            "source_spec_flag_count":43,
            "source_value_flag_count":73,
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
            values=tuple(
                requested and present for requested,present in zip(
                    self.values,available.values)),
        ).validate(flow)
        unavailable_adc=tuple(
            i+1 for i in range(8)
            if self.channels[i] and not available.channels[i])
        unsupported_tach=tuple(
            i-7 for i in range(8,10) if self.channels[i])
        unavailable_tach_values=tuple(
            i-(ADC_VALUE_COUNT+BAND_VALUE_COUNT)+1
            for i in range(ADC_VALUE_COUNT+BAND_VALUE_COUNT,VALUE_COUNT)
            if self.values[i])
        return selected,{
            "source":SOURCE,
            "verified_source_bin_rechecked":True,
            "applied_selected_adc":selected.report()["selected_adcs"],
            "unavailable_adc":list(unavailable_adc),
            "unsupported_original_tach_channels":list(unsupported_tach),
            "unsupported_tach_value_indices":list(unavailable_tach_values),
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
        if type(samples) is not int or samples<0:
            raise ValueError("Unverified Native source sample count")
        rates=ch.get("sample_rates_hz")
        if (not isinstance(rates,list) or len(rates)>3 or
                any(type(r) is not int or r<=0 or r>1_000_000
                    for r in rates)):
            raise ValueError("Unverified Native source Fs")
        if health.stream_silent:
            label="нет новых пакетов"
        elif ch["sequence_discontinuities"] or ch["nonfinite_samples"]:
            label="ошибка потока"
        elif samples==0:
            label="нет отсчётов"
        else:
            label="поток получен"
        if n>8:
            label+="; TACH RAW не подтверждён"
        frequency=(str(rates[0])+" Гц" if len(rates)==1 else UNKNOWN)
        result.append(
            f"{name} · {samples} отсчётов · {frequency} · {label}")
    return tuple(result)
