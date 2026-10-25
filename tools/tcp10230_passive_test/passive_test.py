import argparse
import datetime as dt
import json
import socket
import time
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description='MVK01 passive TCP/10230 test: NO APPLICATION DATA SENT')
    p.add_argument('--host', required=True)
    p.add_argument('--port', type=int, default=10230)
    p.add_argument('--seconds', type=float, default=12.0)
    p.add_argument('--max-mb', type=float, default=40.0)
    args = p.parse_args()
    if args.seconds <= 0 or args.seconds > 60 or args.max_mb <= 0 or args.max_mb > 200:
        p.error('seconds must be 0..60, max-mb must be 0..200')
    target = Path(__file__).resolve().parent / 'results'
    target.mkdir(exist_ok=True)
    stamp = dt.datetime.now().strftime('%Y%m%d_%H%M%S')
    prefix = target / f"MVK_{args.host.replace('.', '_')}_{stamp}"
    limit = int(args.max_mb * 1024 * 1024)
    received = 0
    reason = 'time_limit'
    first_data_s = None
    begin = time.monotonic()
    print(f'Connecting to {args.host}:{args.port} (receive only)')
    try:
        with socket.create_connection((args.host, args.port), timeout=5) as sock:
            sock.settimeout(0.5)
            with open(str(prefix) + '.raw', 'wb') as out:
                while time.monotonic() - begin < args.seconds:
                    try:
                        chunk = sock.recv(min(65536, limit - received))
                    except socket.timeout:
                        continue
                    if not chunk:
                        reason = 'server_closed'
                        break
                    if first_data_s is None:
                        first_data_s = round(time.monotonic() - begin, 4)
                    out.write(chunk)
                    received += len(chunk)
                    if received >= limit:
                        reason = 'size_limit'
                        break
    except OSError as exc:
        reason = 'socket_error'
        print(f'ERROR: {exc}')
    elapsed = round(time.monotonic() - begin, 3)
    info = dict(host=args.host, port=args.port, received_bytes=received, first_data_seconds=first_data_s, elapsed_seconds=elapsed, stopped_because=reason, sent_application_bytes=0, raw_file=str(prefix) + '.raw')
    (Path(str(prefix) + '.json')).write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(info, indent=2, ensure_ascii=False))
    print(f'Results: {target}')


if __name__ == '__main__':
    main()
