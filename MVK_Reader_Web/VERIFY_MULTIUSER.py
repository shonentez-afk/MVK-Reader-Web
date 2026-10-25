"""Local read-only concurrent HTTP test. No live instrument requests."""
import argparse, concurrent.futures, json, time, urllib.error, urllib.request

PATHS=('/api/health','/collector/api/health','/collector/api/devices','/collector/api/server-status','/collector/api/storage-diagnostics','/api/recordings')

def check(base_url, users=8, rounds=3, timeout=8):
    base=base_url.rstrip('/')
    def request(task):
        started=time.perf_counter()
        try:
            with urllib.request.urlopen(base+task[1],timeout=timeout) as response:
                data=response.read(2*1024*1024)
                status=response.status
                if task[1]!='/' and 'json' in response.headers.get('Content-Type',''):
                    json.loads(data)
                return (task[1],status,round((time.perf_counter()-started)*1000,1),None)
        except (OSError,ValueError) as exc:
            return (task[1],None,round((time.perf_counter()-started)*1000,1),str(exc))
    tasks=[(i,p) for i in range(rounds) for p in PATHS]
    with concurrent.futures.ThreadPoolExecutor(max_workers=users) as pool:
        results=list(pool.map(request,tasks))
    failures=[r for r in results if r[1]!=200]
    print(f'Requests: {len(results)} / OK: {len(results)-len(failures)} / errors: {len(failures)}')
    print('Max response ms:', max((r[2] for r in results),default=0))
    for r in failures[:10]:print('FAILED',r)
    return len(failures)==0

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--url',default='http://127.0.0.1:8080')
    parser.add_argument('--users',type=int,default=8)
    parser.add_argument('--rounds',type=int,default=3)
    args=parser.parse_args()
    if args.users<1 or args.users>32 or args.rounds<1 or args.rounds>20:
        parser.error('users 1..32, rounds 1..20')
    raise SystemExit(0 if check(args.url,args.users,args.rounds) else 1)
