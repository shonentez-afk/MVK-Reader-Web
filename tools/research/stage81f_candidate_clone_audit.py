#!/usr/bin/env python3
"""Offline audit of externally supplied candidate MVK clone; never starts live mode."""
import argparse
import ast
import importlib.util
from pathlib import Path

def run(root):
    paths={n:root/n for n in ("dsp_core.py","protocol_10230.py","clone_cli.py","__init__.py")}
    for path in paths.values():
        compile(path.read_bytes(),str(path),"exec")
    dsp=paths["dsp_core.py"].read_text(encoding="utf-8")
    proto=paths["protocol_10230.py"].read_text(encoding="utf-8")
    cli=paths["clone_cli.py"].read_text(encoding="utf-8")
    checks={
      "syntax_all_four": True,
      "43_band_labels":"NBANDS = 43" in dsp and "BAND_LABELS" in dsp,
      "no_live_invocation_on_import":"if __name__ == '__main__':" in cli,
      "register_channel_stride_EXPECTED_0x200":"0x200 * k" in proto.split("def channel_main(",1)[1].split("def channel_bands",1)[0],
      "offline_fs_from_tsxml":"tsxml" in cli.split("def cmd_offline(",1)[1].split("def cmd_live(",1)[0].lower(),
      "real_regression_files_included":all((root/p).exists() for p in ("scripts/mvk_validate.py","scripts/validate_final_output.txt")),
    }
    for k,v in checks.items():
        print(("PASS" if v else "OPEN/FAIL"),k)
    return checks
if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("candidate_dir",type=Path)
    c=run(ap.parse_args().candidate_dir)
    print("Audit checks",sum(c.values()),"/",len(c)," (open checks do not mean runtime failures)")
