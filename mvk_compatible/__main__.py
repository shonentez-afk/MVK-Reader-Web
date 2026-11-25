"""CLI verification (headless) and optional native Qt desktop."""
from __future__ import annotations
import argparse
import json

def main(argv=None):
    parser = argparse.ArgumentParser(prog='mvk_compatible', description='MVKView Compatible (Stage111, архив + подтверждаемый Native R6.1 Live)')
    parser.add_argument('--verify', metavar='NATIVE_EXPORT.zip', help='Проверить локальный ZIP без запуска GUI')
    parser.add_argument('archive', metavar='BIN_TSXML_ZIP', nargs='?', help='Открыть локальную запись')
    args = parser.parse_args(argv)
    if args.verify and args.archive:
        parser.error('Выберите --verify или один файл для просмотра')
    if args.verify:
        from .core import OfflineSession
        try:
            print(json.dumps(OfflineSession.open(args.verify).verify(), ensure_ascii=False, indent=2))
        except (OSError,ValueError,KeyError,RuntimeError) as exc:
            parser.exit(2,f'Архив отклонён: {exc}\n')
        return 0
    try:
        from .desktop.archive_entry import run_archive_desktop
    except ImportError as exc:
        parser.exit(2, 'Для оконного приложения установите зависимости из requirements-desktop.txt.\n'+str(exc)+'\n')
    return run_archive_desktop((args.archive,) if args.archive else ())

if __name__=='__main__':
    raise SystemExit(main())
