"""Create a portable zip while retaining executable permissions."""
from __future__ import annotations

import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--include-root", action="store_true")
    args = parser.parse_args()
    source = args.source.resolve()
    args.archive.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(args.archive, "w", ZIP_DEFLATED) as output:
        for path in sorted(source.rglob("*")):
            if not path.is_file():
                continue
            name = path.relative_to(source.parent if args.include_root else source)
            output.write(path, name)


if __name__ == "__main__":
    main()
