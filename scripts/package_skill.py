#!/usr/bin/env python3
"""Build reproducible .skill and wrapped .zip archives."""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_NAME = "dream-interpretation"
SKILL_ROOT = REPO_ROOT / "skills" / SKILL_NAME
FIXED_TIMESTAMP = (2020, 1, 1, 0, 0, 0)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=REPO_ROOT / "dist")
    return parser.parse_args()


def skill_files() -> list[Path]:
    return sorted(
        path
        for path in SKILL_ROOT.rglob("*")
        if path.is_file()
        and path.name != ".DS_Store"
        and ".private" not in path.relative_to(SKILL_ROOT).parts
        and "__pycache__" not in path.parts
        and path.suffix != ".pyc"
    )


def write_archive(path: Path, wrapper: bool) -> None:
    prefix = f"{SKILL_NAME}/" if wrapper else ""
    entries = [
        (source, prefix + source.relative_to(SKILL_ROOT).as_posix())
        for source in skill_files()
    ]
    entries.append((REPO_ROOT / "LICENSE", prefix + "LICENSE"))
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for source, name in sorted(entries, key=lambda item: item[1]):
            info = zipfile.ZipInfo(name, FIXED_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o755 if source.stat().st_mode & 0o111 else 0o644) << 16
            archive.writestr(info, source.read_bytes())


def main() -> None:
    args = parse_args()
    output = args.output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    skill_archive = output / f"{SKILL_NAME}.skill"
    wrapped_archive = output / f"{SKILL_NAME}.zip"
    write_archive(skill_archive, wrapper=False)
    write_archive(wrapped_archive, wrapper=True)
    print(skill_archive)
    print(wrapped_archive)


if __name__ == "__main__":
    main()
