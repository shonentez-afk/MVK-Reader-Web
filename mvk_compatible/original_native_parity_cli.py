"""Use: python -m mvk_compatible.original_native_parity_cli ORIGINAL_ADC.bin NATIVE_VERIFIED.zip

Stage111Z.27 is a LOCAL comparator only, not a new recorder, not proof
of original-same-run provenance. Real files and screenshots stay private.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from .core.original_native_parity import compare_original_native


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=("Локальная побайтовая сверка Original MVKView BIN/TSXML "
                     "с завершённым проверенным ZIP Native R6.1; "
                     "автоматическая идентичность сеанса НЕ доказуема"))
    parser.add_argument("original_adc_bin",
                        help="Путь к оригинальному BIN с .bin.tsxml; группа ADC1–8 обнаруживается по имени")
    parser.add_argument("native_verified_zip",
                        help="Завершённый SHA-проверенный Native/Qt ZIP (не RAW, не live preview)")
    parser.add_argument("--report",type=Path,
                        help="Новый локальный JSON-отчёт: создаётся с правами владельца, не перезаписывается")
    parser.add_argument("--json",action="store_true",
                        help="Показать подробный JSON в стандартном выводе (только на локальном ПК)")
    parser.add_argument("--require-bin-equal",action="store_true",
                        help="Код 3, если есть технические различия BIN; это НЕ аттестация одного сеанса")
    args=parser.parse_args(argv)
    try:
        result=compare_original_native(args.original_adc_bin,args.native_verified_zip)
        serialized=json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+"\n"
        if args.report is not None:
            p=args.report.absolute()
            if p.is_symlink() or not p.parent.is_dir():
                raise ValueError("Каталог отчёта должен существовать и не содержать символьную ссылку назначения")
            fd=os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
            try:
                with os.fdopen(fd,"w",encoding="utf-8",newline="\n") as stream:
                    stream.write(serialized)
            except Exception:
                p.unlink(missing_ok=True)
                raise
        if args.json:
            print(serialized,end="")
        else:
            print("Stage111Z.27:",result["verdict"])
            print("ADC:",result["compared_adc"],
                  "| bitwise BIN identical from file start:",
                  result["bin_bytes_equal_on_matching_file_starts"])
            print("Original same-run provenance: NOT ATTESTED.")
            print("Original BIN/TSXML data were not modified or uploaded.")
            if args.report is not None:
                print("Local report:",str(args.report))
        return (3 if args.require_bin_equal and not result["bin_bytes_equal_on_matching_file_starts"] else 0)
    except (OSError,ValueError,KeyError,TypeError,RuntimeError,UnicodeError,
            json.JSONDecodeError) as exc:
        print("Stage111Z.27 COMPARISON REFUSED:",str(exc),file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
