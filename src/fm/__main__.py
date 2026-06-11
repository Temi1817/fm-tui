import argparse
import sys
from pathlib import Path

from . import __version__
from .app import FileManagerApp


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="fm",
        description="Cross-platform terminal file manager",
    )
    parser.add_argument("path", nargs="?", default=".", help="Starting directory")
    parser.add_argument("--version", action="version", version=f"fm {__version__}")
    parser.add_argument("--icons", action="store_true", help="Enable Nerd Font icons")
    args = parser.parse_args()

    start_path = Path(args.path).resolve()
    if not start_path.is_dir():
        print(f"fm: '{args.path}' is not a directory", file=sys.stderr)
        sys.exit(1)

    app = FileManagerApp(start_path=start_path, icons=args.icons)
    app.run()


if __name__ == "__main__":
    main()
