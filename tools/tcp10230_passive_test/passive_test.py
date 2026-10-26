import argparse
import datetime as dt
import ipaddress
import json
import os
import socket
import subprocess
import time
from pathlib import Path


def windows_adapter_addresses(name):
    """Discover IPv4 addresses for a specific Windows interface alias, without network IO."""
    script = (
        "$a = Get-NetAdapter -Name '" + name.replace("'", "''") + "' -ErrorAction Stop; "
        "if ($a.Status -ne 'Up') { throw 'Adapter is not Up' }; "
        "Get-NetIPAddress -InterfaceIndex $a.ifIndex -AddressFamily IPv4 "
        "-ErrorAction Stop | Where-Object { $_.IPAddress -notlike '169.254.*' } | "
        "Select-Object -ExpandProperty IPAddress | ConvertTo-Json -Compress"
    )
    r = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        text=True, capture_output=True, timeout=12
    )
    if r.returncode:
        raise RuntimeError("Cannot obtain IPv4 for adapter %r: %s" % (name, r.stderr.strip()))
    s = r.stdout.strip()
    if not s:
        raise RuntimeError("No usable IPv4 on adapter %r" % name)
    parsed = json.loads(s)
    ips = [parsed] if isinstance(parsed, str) else parsed
    return [str(ipaddress.IPv4Address(x)) for x in ips]


def main():
    p = argparse.ArgumentParser(description="MVK01 passive TCP/10230 test: NEVER sends application data")
    p.add_argument("--host", required=True, help="Instrument IPv4 address")
    p.add_argument("--port", type=int, default=10230)
    p.add_argument("--seconds", type=float, default=12.0)
    p.add_argument("--max-mb", type=float, default=40.0)
    p.add_argument("--adapter", default="Ethernet", help="Windows interface alias; default Ethernet")
    p.add_argument("--bind-ip", help="Explicit local IPv4 address (overrides adapter lookup)")
    args = p.parse_args()
    if not (0 < args.seconds <= 60 and 0 < args.max_mb <= 200):
        p.error("seconds must be (0, 60], max-mb (0, 200]")
    if not (1 <= args.port <= 65535):
        p.error("invalid TCP port")
    try:
        host = str(ipaddress.IPv4Address(args.host))
        if args.bind_ip:
            local_ip = str(ipaddress.IPv4Address(args.bind_ip))
            selection = "manual-bind-ip"
        elif os.name == "nt":
            ips = windows_adapter_addresses(args.adapter)
            if len(ips) != 1:
                p.error("Adapter %r has %d IPv4 addresses %s; use --bind-ip to select one" % (args.adapter, len(ips), ips))
            local_ip = ips[0]
            selection = "windows-adapter"
        else:
            p.error("On non-Windows systems specify --bind-ip explicitly")
    except (ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        p.error(str(exc))
    target = Path(__file__).resolve().parent / "results"
    target.mkdir(exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = target / ("MVK_%s_%s" % (host.replace(".", "_"), stamp))
    limit = int(args.max_mb * 1024 * 1024)
    received = 0
    reason = "time_limit"
    first_data_s = None
    actual_local_ip = None
    begin = time.monotonic()
    print("Adapter: %s | Local IPv4: %s | Target: %s:%d" % (args.adapter, local_ip, host, args.port))
    print("Read-only receive test. No application payload will be transmitted.")
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(5)
            sock.bind((local_ip, 0))
            sock.connect((host, args.port))
            actual_local_ip = sock.getsockname()[0]
            if actual_local_ip != local_ip:
                raise RuntimeError("Connected from unexpected local IP %s" % actual_local_ip)
            sock.settimeout(0.5)
            with open(str(prefix) + ".raw", "wb") as out:
                while time.monotonic() - begin < args.seconds:
                    try:
                        chunk = sock.recv(min(65536, limit - received))
                    except socket.timeout:
                        continue
                    if not chunk:
                        reason = "server_closed"
                        break
                    if first_data_s is None:
                        first_data_s = round(time.monotonic() - begin, 4)
                    out.write(chunk)
                    received += len(chunk)
                    if received >= limit:
                        reason = "size_limit"
                        break
    except (OSError, RuntimeError) as exc:
        reason = "socket_error"
        print("ERROR:", exc)
    info = {
        "host": host, "port": args.port, "adapter": args.adapter,
        "selection": selection, "requested_local_ip": local_ip,
        "actual_local_ip": actual_local_ip, "received_bytes": received,
        "first_data_seconds": first_data_s,
        "elapsed_seconds": round(time.monotonic()-begin, 3),
        "stopped_because": reason, "sent_application_bytes": 0,
        "raw_file": str(prefix) + ".raw"
    }
    Path(str(prefix) + ".json").write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(info, indent=2, ensure_ascii=False))
    print("Results:", target)


if __name__ == "__main__":
    main()
