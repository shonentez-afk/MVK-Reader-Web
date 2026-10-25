"""Offline LAN exposure readiness audit; no instrument/network connections."""
from pathlib import Path
root=Path(__file__).resolve().parent
launcher=(root/'START_READER.py').read_text(encoding='utf-8')
integrated=(root/'integrated.py').read_text(encoding='utf-8')
checks={
 'Launcher binds to loopback': "host='127.0.0.1'" in launcher,
 'ASGI denies remote clients': 'reject_remote_clients' in integrated and 'is_loopback' in integrated,
 'No LAN auto-enable': '0.0.0.0' not in launcher,
}
for label,ok in checks.items(): print(('PASS' if ok else 'FAIL')+' '+label)
print('LAN deployment status: BLOCKED until TLS termination, user authentication, authorization and firewall review are configured.')
raise SystemExit(0 if all(checks.values()) else 1)
