"""Cross-check original TMVKThread MvkSampleRate/FreezeUpdate receive proof.

Joint private evidence: mvkview.idp, Projects.7z (_Unit115/_Unit125/
_Unit128/mvkform.dfm), mvk_idr(1).sqlite. No original binaries or
industrial packets are stored in this module.
"""
from __future__ import annotations

SCHEMA="MVK_SOURCE_TMVKTHREAD_RECEIVE_GATE_V1"
SOURCE_RATES=frozenset((512,2048,8192,32768,65536))
U64=(1<<64)-1
_FIELDS=("accepted_elements","rate_skipped_elements",
         "freeze_skipped_elements","rate_skipped_frames",
         "freeze_skipped_frames","last_skipped_native_samples")


def _u64(value,label):
    if type(value) is not int or not 0<=value<=U64:
        raise ValueError("Original receive gate: invalid "+label)
    return value


def validate_original_receive_gate_receipt(
        receipt:dict|None,channels:list[dict])->dict|None:
    """Validate in-memory source gate without inventing physical SetRate."""
    if receipt is None:
        return None
    if not isinstance(receipt,dict) or receipt.get("schema")!=SCHEMA:
        raise ValueError("Original receive gate: invalid schema")
    if (receipt.get("initial_thread_rate_hz")!=777 or
            receipt.get("source_initial_menu_rate_hz")!=65536 or
            receipt.get("selected_rate_hz") not in SOURCE_RATES or
            receipt.get("source_menu_selected") is not True or
            receipt.get("physical_setrate_not_inferred") is not True or
            receipt.get("original_delphi_parity_verified") is not False or
            type(receipt.get("freeze_update")) is not bool or
            not isinstance(channels,list) or len(channels)!=10 or
            not isinstance(receipt.get("channels"),list) or
            len(receipt["channels"])!=10):
        raise ValueError("Original receive gate: source menu/Freeze receipt contradicts IDP")
    selections=_u64(receipt.get("selection_changes"),"selection_changes")
    freezes=_u64(receipt.get("freeze_changes"),"freeze_changes")
    if selections<1:
        raise ValueError("Original receive gate: initial 777->65536 menu missing")
    rows=[]
    for i,row in enumerate(receipt["channels"]):
        if (not isinstance(row,dict) or row.get("channel")!=i+1 or
                not isinstance(channels[i],dict) or
                channels[i].get("channel")!=i+1):
            raise ValueError("Original receive gate: channel identity mismatch")
        source={field:_u64(row.get(field),field) for field in _FIELDS}
        unit_width=4 if i>=8 else 1
        native_samples=_u64(channels[i].get("samples"),"native_samples")
        expected=native_samples*unit_width
        actual=sum(source[x] for x in _FIELDS[:3])
        if expected>U64 or actual!=expected:
            raise ValueError("Original receive gate: accepted+skipped not equal real TCP payload")
        skipped=source["rate_skipped_elements"]+source["freeze_skipped_elements"]
        skip_frames=source["rate_skipped_frames"]+source["freeze_skipped_frames"]
        if ((skipped==0)!=(skip_frames==0) or
                (source["rate_skipped_frames"]>0 and source["rate_skipped_elements"]==0) or
                (source["freeze_skipped_frames"]>0 and source["freeze_skipped_elements"]==0) or
                source["last_skipped_native_samples"]>native_samples or
                (source["last_skipped_native_samples"]==0)!=(skipped==0) or
                source["rate_skipped_frames"]>channels[i]["frames"] or
                source["freeze_skipped_frames"]>channels[i]["frames"] or
                (source["freeze_skipped_frames"]>0 and freezes==0)):
            raise ValueError("Original receive gate: invalid dropped-frame proof")
        rows.append({"channel":i+1,**source})
    return {
        "schema":SCHEMA,"selected_rate_hz":receipt["selected_rate_hz"],
        "initial_thread_rate_hz":777,"source_initial_menu_rate_hz":65536,
        "source_menu_selected":True,"physical_setrate_not_inferred":True,
        "freeze_update":receipt["freeze_update"],
        "selection_changes":selections,"freeze_changes":freezes,
        "channels":rows,
        "original_delphi_parity_verified":False,
        "source_receive_gate_validated":True,
    }
