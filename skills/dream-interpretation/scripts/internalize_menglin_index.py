#!/usr/bin/env python3
"""Convert a complete legacy local index into this skill's private knowledge resource."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path


EXPECTED_SOURCE_SHA256 = "0be41e3af522be1546d17c2fba3757a8c5ad73cc9aa5dd26fd7371bf5971be2e"
EXPECTED_INDEXED_PAGES = 369
LAST_BOOK_PAGE = 368
SKILL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DESTINATION = SKILL_ROOT / "references/.private/extended-corpus"
STANDALONE_NUMBER_RE = re.compile(r"^[\s\[\]【】「」『』|]*\d{1,4}[\s\[\]【】「」『』|]*$")


def default_legacy_index() -> Path:
    data_home = os.environ.get("XDG_DATA_HOME")
    root = Path(data_home).expanduser() if data_home else Path.home() / ".local/share"
    return root / "jiemeng-skills/menglin-xuanjie"


def compact_search_text(text: str) -> str:
    return "".join(re.findall(r"[\u3400-\u9fffA-Za-z0-9]+", text)).lower()


def clean_text(text: str) -> str:
    lines = [
        line.rstrip()
        for line in text.replace("\r\n", "\n").replace("\r", "\n").splitlines()
        if not STANDALONE_NUMBER_RE.fullmatch(line)
    ]
    value = "\n".join(lines)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-index", type=Path, default=default_legacy_index())
    parser.add_argument("--destination", type=Path, default=DEFAULT_DESTINATION)
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--allow-different-source",
        action="store_true",
        help="允许从未登记的完整私有索引生成内部资源",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source = args.from_index.expanduser().resolve()
    destination = args.destination.expanduser().resolve()
    source_manifest_path = source / "manifest.json"
    source_pages_path = source / "pages.jsonl"
    if not source_manifest_path.is_file() or not source_pages_path.is_file():
        raise SystemExit("未找到可供内化的完整私有索引")

    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    if source_manifest.get("status") != "complete":
        raise SystemExit("私有索引尚未完整，不能声称已全部内化")
    if source_manifest.get("indexed_pages") != EXPECTED_INDEXED_PAGES:
        raise SystemExit("私有索引的内容计数不完整")
    if (
        source_manifest.get("source_sha256") != EXPECTED_SOURCE_SHA256
        and not args.allow_different_source
    ):
        raise SystemExit("私有索引与已登记完整资料不匹配")

    source_records = [
        json.loads(line)
        for line in source_pages_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(source_records) != EXPECTED_INDEXED_PAGES:
        raise SystemExit("私有索引的内容记录数不完整")
    source_pages = {int(record["pdf_page"]): record for record in source_records}
    if set(source_pages) != set(range(1, EXPECTED_INDEXED_PAGES + 1)):
        raise SystemExit("私有索引的内容序列不完整")

    chunks: list[dict[str, str]] = []
    for page in range(1, LAST_BOOK_PAGE + 1):
        text = clean_text(str(source_pages[page].get("text") or ""))
        if not text:
            continue
        chunks.append({
            "chunk_id": f"knowledge-{len(chunks) + 1:04d}",
            "text": text,
            "search_text": compact_search_text(text),
        })

    corpus_bytes = b"".join(
        (json.dumps(chunk, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        for chunk in chunks
    )
    manifest = {
        "schema_version": 1,
        "status": "ready",
        "scope": "complete_private_knowledge",
        "chunk_count": len(chunks),
        "content_sha256": sha256_bytes(corpus_bytes),
    }

    corpus_path = destination / "corpus.jsonl"
    manifest_path = destination / "manifest.json"
    if (corpus_path.exists() or manifest_path.exists()) and not args.force:
        raise SystemExit("当前 skill 已有内部知识资源；如需重建请显式加 --force")
    destination.mkdir(parents=True, exist_ok=True)

    temporary_corpus = corpus_path.with_suffix(".jsonl.tmp")
    temporary_manifest = manifest_path.with_suffix(".json.tmp")
    temporary_corpus.write_bytes(corpus_bytes)
    temporary_manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary_corpus.replace(corpus_path)
    temporary_manifest.replace(manifest_path)

    print(json.dumps({
        "knowledge": "internalized",
        "integrity": "verified",
        "chunk_count": len(chunks),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
