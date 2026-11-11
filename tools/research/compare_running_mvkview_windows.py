#!/usr/bin/env python3
"""Stage111Z31BA: read-only, operator-triggered comparison of TWO running apps.

This tool attaches ONLY to existing top-level Windows HWNDs by PID, uses
GetDC+BitBlt to capture visible client pixels, then writes PRIVATE local PNGs
and aggregate report. It NEVER starts original MVKView, sends input, touches
debugger, reads process memory, accesses device or uploads screenshots.

Initially this is a DIRECT WINDOW ACQUISITION BASELINE; not automatic
screen routing, calibrated graphic ROI or proof of functional 1:1 parity.
Windows/Desktop requirements: numpy and PySide6.
"""
from __future__ import annotations
import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import json
from pathlib import Path
import secrets
import sys
import numpy as np

FORMAT="MVKVIEW_TWO_RUNNING_APPS_WIN32_READONLY_CAPTURE_V1"
MAX_PIXELS=10_000_000


def image_comparison_summary(original, candidate):
    """No resizing, alignment, filtering, OCR, font or DPI assumptions."""
    def verify(a):
        return (isinstance(a,np.ndarray) and a.dtype==np.uint8 and
                a.ndim==3 and a.shape[2]==4 and
                a.shape[0]>=64 and a.shape[1]>=64 and
                a.shape[0]*a.shape[1]<=MAX_PIXELS and
                bool(np.all(a[:,:,3]==255)))
    if not verify(original) or not verify(candidate):
        raise ValueError("Two bounded opaque RGBA images required")
    oh,ow=original.shape[:2]
    ch,cw=candidate.shape[:2]
    result={
        "format":FORMAT,
        "original_client_size_wh":[ow,oh],
        "candidate_client_size_wh":[cw,ch],
        "identical_client_pixel_dimensions":bool((oh,ow)==(ch,cw)),
        "automatic_scaling_or_alignment_performed":False,
        "full_window_1to1_verified":False,
        "original_executable_identity_independently_verified":False,
        "original_device_io_performed":False,
        "scope":"single current client rendering, NOT complete behaviors"}
    if (oh,ow)!=(ch,cw):
        result["comparison_rejected_reason"]="different client dimensions"
        return result
    delta=np.abs(original[:,:,:3].astype(np.int16)-
                 candidate[:,:,:3].astype(np.int16))
    result["unshifted_exact_rgb_pixels"]=int(np.count_nonzero(
        np.all(delta==0,axis=2)))
    result["unshifted_pixels_any_channel_gt_1"]=int(np.count_nonzero(
        np.any(delta>1,axis=2)))
    result["unshifted_average_abs_rgb_error"]=float(delta.mean())
    result["unshifted_pixel_identical_this_capture"]=bool(
        result["unshifted_exact_rgb_pixels"]==ow*oh)
    return result


def _native():
    if sys.platform!="win32":
        raise RuntimeError("Original/compatible HWND capture requires Windows")
    u=ctypes.WinDLL("user32",use_last_error=True)
    g=ctypes.WinDLL("gdi32",use_last_error=True)
    W=ctypes.c_void_p
    def bind(lib,name,ret,args):
        f=getattr(lib,name);f.restype=ret;f.argtypes=args;return f
    return u,g,bind


def _dpi_context(user32,bind):
    """Set compare PROCESS to native device coordinates when supported."""
    try:
        f=bind(user32,"SetProcessDpiAwarenessContext",wintypes.BOOL,[ctypes.c_void_p])
        return bool(f(ctypes.c_void_p(-4)))  # PER_MONITOR_AWARE_V2
    except AttributeError:
        return False


class _RECT(ctypes.Structure):
    _fields_=[("left",ctypes.c_long),("top",ctypes.c_long),
              ("right",ctypes.c_long),("bottom",ctypes.c_long)]


class _BIH(ctypes.Structure):
    _fields_=[
        ("biSize",wintypes.DWORD),("biWidth",ctypes.c_long),
        ("biHeight",ctypes.c_long),("biPlanes",wintypes.WORD),
        ("biBitCount",wintypes.WORD),("biCompression",wintypes.DWORD),
        ("biSizeImage",wintypes.DWORD),("biXPelsPerMeter",ctypes.c_long),
        ("biYPelsPerMeter",ctypes.c_long),("biClrUsed",wintypes.DWORD),
        ("biClrImportant",wintypes.DWORD)]


def _locate_main_window(pid,user32,bind):
    """Identify a visible TOP-level main window; refuse ambiguous selection."""
    if type(pid) is not int or not 1<=pid<=2_147_483_647:
        raise ValueError("Expected positive Windows process ID")
    H=ctypes.c_void_p
    getpid=bind(user32,"GetWindowThreadProcessId",wintypes.DWORD,
                [H,ctypes.POINTER(wintypes.DWORD)])
    visible=bind(user32,"IsWindowVisible",wintypes.BOOL,[H])
    getrect=bind(user32,"GetClientRect",wintypes.BOOL,
                 [H,ctypes.POINTER(_RECT)])
    getlength=bind(user32,"GetWindowTextLengthW",ctypes.c_int,[H])
    gettitle=bind(user32,"GetWindowTextW",ctypes.c_int,
                  [H,ctypes.c_wchar_p,ctypes.c_int])
    matches=[]
    CALLBACK=ctypes.WINFUNCTYPE(wintypes.BOOL,H,H)
    @CALLBACK
    def visit(hwnd,opaque):
        current=wintypes.DWORD(0)
        getpid(hwnd,ctypes.byref(current))
        if current.value!=pid or not visible(hwnd):
            return True
        r=_RECT()
        if not getrect(hwnd,ctypes.byref(r)):
            return True
        w,h=r.right-r.left,r.bottom-r.top
        if min(w,h)<200 or w*h>MAX_PIXELS:
            return True
        sz=getlength(hwnd)
        if sz<1 or sz>1024:
            return True
        buf=ctypes.create_unicode_buffer(sz+1)
        gettitle(hwnd,buf,sz+1)
        if not buf.value.strip():
            return True
        matches.append((int(hwnd),w,h,buf.value))
        return True
    enum=bind(user32,"EnumWindows",wintypes.BOOL,[CALLBACK,H])
    if not enum(visit,None):
        raise OSError("EnumWindows failed")
    if len(matches)!=1:
        raise ValueError(
            "Expected exactly one visible sizable top-level window for PID "+
            str(pid)+", found "+str(len(matches))+
            "; close auxiliary dialogs and do not automate original actions")
    return matches[0]


def _capture_existing_client(hwnd,user32,gdi,bind):
    """Read-only Windows client DC -> top-down BGRA device bitmap."""
    H=ctypes.c_void_p
    I=ctypes.c_int
    getrect=bind(user32,"GetClientRect",wintypes.BOOL,
                 [H,ctypes.POINTER(_RECT)])
    getdc=bind(user32,"GetDC",H,[H])
    releasedc=bind(user32,"ReleaseDC",I,[H,H])
    dcnew=bind(gdi,"CreateCompatibleDC",H,[H])
    dcdel=bind(gdi,"DeleteDC",wintypes.BOOL,[H])
    bmpnew=bind(gdi,"CreateCompatibleBitmap",H,[H,I,I])
    bmpdel=bind(gdi,"DeleteObject",wintypes.BOOL,[H])
    select=bind(gdi,"SelectObject",H,[H,H])
    blit=bind(gdi,"BitBlt",wintypes.BOOL,
              [H,I,I,I,I,H,I,I,wintypes.DWORD])
    dib=bind(gdi,"GetDIBits",I,
             [H,H,wintypes.UINT,wintypes.UINT,
              H,ctypes.POINTER(_BIH),wintypes.UINT])
    r=_RECT()
    if not getrect(H(hwnd),ctypes.byref(r)):
        raise OSError("GetClientRect failed")
    w,h=r.right-r.left,r.bottom-r.top
    if min(w,h)<64 or w*h>MAX_PIXELS:
        raise ValueError("Win32 client dimensions are not bounded")
    source=getdc(H(hwnd))
    if not source:
        raise OSError("GetDC failed")
    mem=None;bitmap=None;old=None
    try:
        mem=dcnew(source)
        if not mem:raise OSError("CreateCompatibleDC failed")
        bitmap=bmpnew(source,w,h)
        if not bitmap:raise OSError("CreateCompatibleBitmap failed")
        old=select(mem,bitmap)
        if not old:raise OSError("SelectObject failed")
        if not blit(mem,0,0,w,h,source,0,0,0x00CC0020):
            raise OSError("BitBlt client capture failed")
        select(mem,old)
        old=None  # GetDIBits requires bitmap not selected into DC
        hdr=_BIH()
        hdr.biSize=ctypes.sizeof(_BIH)
        hdr.biWidth=w
        hdr.biHeight=-h  # top-down rows
        hdr.biPlanes=1
        hdr.biBitCount=32
        hdr.biCompression=0
        pixels=ctypes.create_string_buffer(w*h*4)
        count=dib(mem,bitmap,0,h,ctypes.cast(pixels,H),
                  ctypes.byref(hdr),0)
        if count!=h:raise OSError("GetDIBits did not return all rows")
        bgra=np.frombuffer(pixels.raw,dtype=np.uint8).reshape(h,w,4)
        rgba=np.ascontiguousarray(bgra[:,:,[2,1,0,3]])
        rgba[:,:,3]=255
        return rgba
    finally:
        if old and mem:select(mem,old)
        if bitmap:bmpdel(bitmap)
        if mem:dcdel(mem)
        releasedc(H(hwnd),source)


def _save_png(filepath,image):
    from PySide6.QtGui import QImage
    h,w=image.shape[:2]
    packed=np.ascontiguousarray(image).tobytes()
    q=QImage(packed,w,h,w*4,QImage.Format_RGBA8888).copy()
    if not q.save(str(filepath),"PNG"):
        raise OSError("Failed to save local PNG")


def run(argv=None)->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--original-pid",type=int,required=True)
    p.add_argument("--compatible-pid",type=int,required=True)
    p.add_argument("--private-output-directory",type=Path,required=True)
    a=p.parse_args(argv)
    if a.original_pid==a.compatible_pid:
        p.error("Original and compatible windows must have DIFFERENT PIDs")
    checkout=Path(__file__).resolve().parents[2]
    target=a.private_output_directory.resolve()
    if checkout==target or checkout in target.parents or not target.is_dir():
        p.error("Use an existing PRIVATE folder outside Git checkout")
    user32,gdi,bind=_native()
    dpi_v2=_dpi_context(user32,bind)
    orig=_locate_main_window(a.original_pid,user32,bind)
    clone=_locate_main_window(a.compatible_pid,user32,bind)
    o=_capture_existing_client(orig[0],user32,gdi,bind)
    c=_capture_existing_client(clone[0],user32,gdi,bind)
    report=image_comparison_summary(o,c)
    report.update({
        "dpi_per_monitor_v2_observer_set":dpi_v2,
        "original_window_pid":a.original_pid,
        "compatible_window_pid":a.compatible_pid,
        "original_window_title_for_operator_only":orig[3],
        "compatible_window_title_for_operator_only":clone[3],
        "automatic_original_program_launch":False,
        "original_window_inputs_sent":False,
        "original_debugger_or_process_memory_access":False,
        "source_alignment_completed":False,
        "source_scenario_identity_proven":False})
    folder=target/("MVK_DIRECT_WINDOW_QA_"+
                   datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_")+
                   secrets.token_hex(4))
    folder.mkdir(mode=0o700)
    _save_png(folder/"original_client.png",o)
    _save_png(folder/"compatible_client.png",c)
    with (folder/"comparison.json").open("x",encoding="utf-8") as out:
        json.dump(report,out,ensure_ascii=False,sort_keys=True,indent=2)
        out.write("\n")
    print("Two current client windows captured to PRIVATE folder:",folder)
    print("Same pixel dimensions:",report["identical_client_pixel_dimensions"])
    print("Full functional/UI 1:1 original parity: NOT ATTESTED")
    return 0


if __name__=="__main__":
    raise SystemExit(run())
