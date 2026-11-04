"""Entry point: the tray app by default, or one core command
(`museum-wallpapers next`, `status`, … see core.py), or `selftest`."""

import sys


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("tray", "--background"):
        from . import app
        return app.main(background="--background" in argv)
    if argv[0] == "selftest":
        from . import selftest
        out = argv[argv.index("--out") + 1] if "--out" in argv[1:-1] else None
        return selftest.run(out)
    from . import core
    return core.main(argv)


if __name__ == "__main__":
    sys.exit(main())
