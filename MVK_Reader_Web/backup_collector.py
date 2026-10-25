"""Run offline or while Collector is active; SQL only, no Modbus/network."""
import argparse, os
from datetime import datetime,timezone
from pathlib import Path
from collector.core import Collector

if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Create a consistent MVK SQLite snapshot')
    parser.add_argument('--output-dir',default='backups')
    args=parser.parse_args()
    root=Path(__file__).resolve().parent
    collector=Collector(Path(os.getenv('MVK_DEVICES_CONFIG',str(root/'collector/devices.json'))),
                        Path(os.getenv('MVK_COLLECTOR_DB',str(root/'collector/collector.sqlite3'))))
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    target=Path(args.output_dir)/('mvk_collector_'+stamp+'.sqlite3')
    print(collector.backup_sqlite(target))
