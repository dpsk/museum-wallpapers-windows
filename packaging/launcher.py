"""PyInstaller entry point (the package's __main__ uses relative imports)."""

import sys

from museum_wallpapers.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
