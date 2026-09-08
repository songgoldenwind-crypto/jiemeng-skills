#!/usr/bin/env python3
"""Validate repository structure, Skill metadata, local links, and source census."""

from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_NAME = "dream-interpretation"
SKILL_ROOT = REPO_ROOT / "skills" / SKILL_NAME
SKILL_FILE = SKILL_ROOT / "SKILL.md"
DATA_FILE = SKILL_ROOT / "references" / "classical-dictionary.txt"
MENGLIN_SOURCE = SKILL_ROOT / "references" / "menglin-xuanjie-source.json"
CATEGORY_RE = re.compile(r"^[一二三四五六七八九十]+、")


def main() -> None:
    skill_directories = sorted(path.name for path in (REPO_ROOT / "skills").iterdir() if path.is_dir())
    assert skill_directories == [SKILL_NAME]

    skill = SKILL_FILE.read_text(encoding="utf-8")
    frontmatter = re.match(r"^---\n([\s\S]*?)\n---\n", skill)
    assert frontmatter, "SKILL.md 缺少 YAML frontmatter"
    assert re.search(rf"^name: {re.escape(SKILL_NAME)}$", frontmatter.group(1), re.MULTILINE)
    assert re.search(r"^description: .+$", frontmatter.group(1), re.MULTILINE)
    assert not re.search(r"\[TODO|TODO:|Replace this", skill)

    checked_links = 0
    for markdown in SKILL_ROOT.rglob("*.md"):
        contents = markdown.read_text(encoding="utf-8")
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", contents):
            if re.match(r"^(?:https?:|mailto:|#)", target):
                continue
            local = target.split("#", 1)[0]
            assert (markdown.parent / local).resolve().exists(), f"无效链接: {markdown}: {target}"
            checked_links += 1

    lines = DATA_FILE.read_text(encoding="utf-8").splitlines()
    categories = sum(bool(CATEGORY_RE.match(line.strip())) for line in lines)
    segments = sum(
        len(line.strip().split())
        for line in lines
        if line.strip() and not CATEGORY_RE.match(line.strip())
    )
    assert categories == 27
    assert segments == 951
    menglin = json.loads(MENGLIN_SOURCE.read_text(encoding="utf-8"))
    assert menglin["source_key"] == "menglin-xuanjie-1993-user-pdf"
    assert menglin["pdf"] == {
        "sha256": "0be41e3af522be1546d17c2fba3757a8c5ad73cc9aa5dd26fd7371bf5971be2e",
        "bytes": 8857060,
        "pages": 369,
        "has_usable_text_layer": False,
        "content_pdf_page_start": 9,
        "book_page_offset": 8,
    }
    assert not list(SKILL_ROOT.rglob("pages.jsonl")), "公开 Skill 不应包含整书 OCR 索引"
    assert not list(SKILL_ROOT.rglob("page-*.txt")), "公开 Skill 不应包含逐页 OCR"
    assert (REPO_ROOT / "LICENSE").read_text(encoding="utf-8").startswith("MIT License\n")

    print(json.dumps({
        "status": "pass",
        "skills": 1,
        "checked_links": checked_links,
        "categories": categories,
        "segments": segments,
        "menglin_pages": menglin["pdf"]["pages"],
        "full_ocr_bundled": False,
        "license": "MIT",
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
