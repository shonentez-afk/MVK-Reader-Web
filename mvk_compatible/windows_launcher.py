"""Windows one-file entry point with optional archive and verified offline FIR."""
import sys


def main(argv=None):
    from mvk_compatible.core.bundled_offline_fir import load_frozen_offline_fir

    args=tuple(sys.argv[1:] if argv is None else argv)
    profile=load_frozen_offline_fir()
    if args==('--verify-offline-fir',):
        return 0 if profile is not None else 2

    from mvk_compatible.desktop.archive_entry import run_archive_desktop
    return run_archive_desktop(args,profile=profile)


if __name__ == '__main__':
    raise SystemExit(main())
