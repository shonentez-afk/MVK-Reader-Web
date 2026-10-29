"""CLI verification (headless) and optional native Qt desktop."""
from __future__ import annotations
import argparse
import json

def main(argv=None):
    parser = argparse.ArgumentParser(prog='mvk_compatible', description='MVKView Compatible (Stage111, архивный режим)')
    parser.add_argument('--verify', metavar='NATIVE_EXPORT.zip', help='Проверить локальный ZIP без запуска GUI')
    args = parser.parse_args(argv)
    if args.verify:
        from .core import OfflineSession
        try:
            print(json.dumps(OfflineSession.open(args.verify).verify(), ensure_ascii=False, indent=2))
        except (OSError,ValueError,KeyError,RuntimeError) as exc:
            parser.exit(2,f'Архив отклонён: {exc}\n')
        return 0
    try:
        from .desktop.main_window import run
    except ImportError as exc:
        parser.exit(2, 'Для оконного приложения установите зависимости из requirements-desktop.txt.\n'+str(exc)+'\n')
    return run()

if __name__=='__main__':
    raise SystemExit(main())
