"""Original PageStart session-only inputs and bounded offline library.

Private _Unit128.pas dispatch: bTaskView=Mode1, bTaskConnect=Mode2,
bTaskConfigIP=Mode4, bTaskConfigCalib=Mode5 (DFM hidden),
bTaskConfigCh=Mode6. edLibraryPathAfterDialog 00848E90 only
normalises the picked local folder. Nothing here opens a TCP socket.
"""
from __future__ import annotations

from dataclasses import dataclass,replace
from ipaddress import IPv4Address
from pathlib import Path

SOURCE="ORIGINAL_IDR_PAGESTART_LOCAL_LIBRARY_CORE_STAGE111Z31BU"
START_IP_DEFAULT="192.168.0.30"
START_LIBRARY_DEFAULT="*"
START_IP_RECT=(157,208,173,24)
START_LIBRARY_RECT=(29,276,301,24)
START_BUTTONS=(
    ("bTaskConnect",29,19,301,86,"Gears",0,2),
    ("bTaskConfigCh",370,19,458,86,"EditGear",1,6),
    ("bTaskView",29,105,301,86,"Open",6,1),
    ("bTaskConfigIP",370,105,458,86,"EditNet",2,4),
    ("bTaskConfigCalib",370,193,458,86,"EditCalib",3,5),
)
LIBRARY_SUFFIXES=frozenset((".zip",".bin",".tsxml"))
MAX_LIBRARY_FILES=256
MAX_SOURCE_SIZE=2*1024**3


def validate_source_ipv4(text):
    """Only validates an explicit numeric address; never probes hardware."""
    if not isinstance(text,str) or text!=text.strip() or len(text)>15:
        raise ValueError("Original edIpAddr requires numeric IPv4")
    try:
        parsed=IPv4Address(text)
    except (ValueError,TypeError) as exc:
        raise ValueError("Original edIpAddr requires numeric IPv4") from exc
    if parsed.is_multicast or parsed.is_unspecified or parsed.is_loopback or (
            parsed==IPv4Address("255.255.255.255")):
        raise ValueError("Device IP must be a unicast non-loopback address")
    return str(parsed)


def _checked_directory(path):
    directory=Path(path).absolute()
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("edLibraryPath must be an existing ordinary directory")
    return directory.resolve(strict=True)


@dataclass(frozen=True)
class SourceLibraryItem:
    basename:str
    size_bytes:int
    extension:str

    def __post_init__(self):
        if (not isinstance(self.basename,str) or not self.basename or
                any(c in self.basename for c in ("/","\\","\x00")) or
                type(self.size_bytes) is not int or not 0<self.size_bytes<=MAX_SOURCE_SIZE or
                self.extension not in LIBRARY_SUFFIXES):
            raise ValueError("Untrusted local recording metadata")


@dataclass(frozen=True)
class OriginalStartWorkspace:
    device_ipv4:str=START_IP_DEFAULT
    library_path:Path|None=None
    source:str=SOURCE

    def __post_init__(self):
        validate_source_ipv4(self.device_ipv4)
        if self.library_path is not None:
            _checked_directory(self.library_path)

    def with_device_ip(self,value):
        return replace(self,device_ipv4=validate_source_ipv4(value))

    def with_library(self,path):
        return replace(self,library_path=_checked_directory(path))

    def directory(self):
        if self.library_path is None:
            raise ValueError("Original edLibraryPath must be explicitly selected")
        return _checked_directory(self.library_path)

    def list_recordings(self):
        """On user refresh only: list bounded files without reading data."""
        base=self.directory()
        found=[]
        for candidate in base.iterdir():
            if candidate.suffix.lower() not in LIBRARY_SUFFIXES:
                continue
            if candidate.is_symlink() or not candidate.is_file():
                continue
            size=candidate.stat().st_size
            if not 0<size<=MAX_SOURCE_SIZE:
                continue
            found.append(SourceLibraryItem(
                candidate.name,size,candidate.suffix.lower()))
            if len(found)>MAX_LIBRARY_FILES:
                raise ValueError("Too many original local library recordings")
        return tuple(sorted(found,key=lambda e:e.basename.casefold()))

    def selected_file(self,basename):
        """Keep operator file selection inside explicit original LibraryPath."""
        if (not isinstance(basename,str) or not basename or
                Path(basename).name!=basename or
                "/" in basename or "\\" in basename or "\x00" in basename):
            raise ValueError("Invalid local library source filename")
        base=self.directory()
        path=base/basename
        if path.is_symlink() or not path.is_file() or path.parent!=base:
            raise ValueError("Source file is outside configured library")
        if (path.suffix.lower() not in LIBRARY_SUFFIXES or
                not 0<path.stat().st_size<=MAX_SOURCE_SIZE):
            raise ValueError("Selected original library file unavailable")
        return path

    def source_route(self,button):
        row=next((x for x in START_BUTTONS if x[0]==button),None)
        if row is None:
            raise ValueError("Unknown original PageStart button")
        return dict(button=button,original_mode=row[7],
                    device_command_issued=False,
                    original_mode_1_to_6_source_accepted=True)

    def report(self):
        return {
            "source":SOURCE,
            "original_default_ip":START_IP_DEFAULT,
            "device_ipv4":self.device_ipv4,
            "library_explicit":self.library_path is not None,
            "original_library_placeholder":START_LIBRARY_DEFAULT,
            "network_scan_performed":False,
            "device_io_performed":False,
            "original_task_dispatch_recovered":True,
            "original_runtime_localization_or_pixel_parity_verified":False,
        }


assert len(START_BUTTONS)==5
