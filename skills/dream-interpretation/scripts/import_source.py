#!/usr/bin/env python3
"""Normalize the supplied classical dream text into the bundled UTF-8 dictionary."""

from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = SKILL_ROOT / "references" / "classical-dictionary.txt"
CATEGORY_RE = re.compile(r"^[一二三四五六七八九十]+、")


def decode_source(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-16", "utf-16le", "utf-8-sig", "utf-8"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("无法识别源文件编码")


def normalize(text: str) -> tuple[str, int, int]:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    start = next(
        (index for index, line in enumerate(lines) if CATEGORY_RE.match(line.strip().lstrip("\ufeff"))),
        None,
    )
    if start is None:
        raise ValueError("未找到梦象门类标题")

    selected = [line.rstrip() for line in lines[start:]]
    while selected and not selected[-1].strip():
        selected.pop()

    categories = sum(bool(CATEGORY_RE.match(line.strip())) for line in selected)
    entries = sum(
        len(line.strip().split())
        for line in selected
        if line.strip() and not CATEGORY_RE.match(line.strip())
    )
    if categories != 27 or entries != 951:
        raise ValueError(f"源文件结构变化：categories={categories}, entries={entries}")
    return "\n".join(selected) + "\n", categories, entries


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="原始 txt 文件")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    source = args.source.expanduser().resolve()
    normalized, categories, entries = normalize(decode_source(source))
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(normalized, encoding="utf-8", newline="\n")

    print(f"source_sha256={hashlib.sha256(source.read_bytes()).hexdigest()}")
    print(f"output={output}")
    print(f"categories={categories}")
    print(f"segments={entries}")


if __name__ == "__main__":
    main()
