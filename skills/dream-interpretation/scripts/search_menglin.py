#!/usr/bin/env python3
"""Search a private OCR index of the user's Menglin Xuanjie PDF."""

from __future__ import annotations

import argparse
import difflib
import json
import math
import os
import re
from pathlib import Path


ALIASES = (
    ("梦到", ""),
    ("梦见", ""),
    ("梦中", ""),
    ("梦里", ""),
    ("牙齿掉落", "齿落"),
    ("牙齿掉", "齿落"),
    ("房屋倒塌", "屋倒"),
    ("房子倒塌", "屋倒"),
    ("牙齿", "齿"),
    ("房子", "屋"),
    ("房屋", "屋"),
    ("浑浊", "浊"),
    ("变清", "澄"),
    ("去世的人", "死者"),
    ("过世的人", "死者"),
)


def default_index() -> Path:
    data_home = os.environ.get("XDG_DATA_HOME")
    root = Path(data_home).expanduser() if data_home else Path.home() / ".local" / "share"
    return root / "jiemeng-skills" / "menglin-xuanjie"


def compact(text: str) -> str:
    value = text.lower().strip()
    for old, new in ALIASES:
        value = value.replace(old, new)
    return "".join(re.findall(r"[\u3400-\u9fffA-Za-z0-9]+", value))


def compact_with_positions(text: str) -> tuple[str, list[int]]:
    characters: list[str] = []
    positions: list[int] = []
    for position, character in enumerate(text):
        if re.match(r"[\u3400-\u9fffA-Za-z0-9]", character):
            characters.append(character.lower())
            positions.append(position)
    return "".join(characters), positions


def match_page(query: str, page: dict[str, object]) -> tuple[float, int, int, str] | None:
    text = str(page.get("search_text") or "")
    if not query or not text:
        return None
    exact = text.find(query)
    if exact >= 0:
        return 1000.0 + len(query) * 20, exact, len(query), "exact_ocr"

    matcher = difflib.SequenceMatcher(None, query, text, autojunk=False)
    block = matcher.find_longest_match()
    required = max(2, math.ceil(len(query) * 0.45))
    if block.size < required:
        return None
    ratio = block.size / len(query)
    shared = len(set(query) & set(text))
    score = block.size * 25 + ratio * 100 + shared
    return score, block.b, block.size, "approximate_ocr"


def snippet_for(text: str, compact_start: int, compact_size: int, limit: int) -> str:
    compact_text, positions = compact_with_positions(text)
    if not compact_text or not positions:
        return text[:limit]
    compact_start = min(max(compact_start, 0), len(positions) - 1)
    compact_end = min(compact_start + max(compact_size, 1) - 1, len(positions) - 1)
    raw_start = positions[compact_start]
    raw_end = positions[compact_end] + 1
    padding = max(20, (limit - (raw_end - raw_start)) // 2)
    start = max(0, raw_start - padding)
    end = min(len(text), raw_end + padding)
    value = re.sub(r"\s+", " ", text[start:end]).strip()
    if start:
        value = "…" + value
    if end < len(text):
        value += "…"
    return value[: limit + 1].rstrip() + ("…" if len(value) > limit else "")


def load_index(index: Path) -> tuple[dict[str, object], list[dict[str, object]]]:
    manifest_path = index / "manifest.json"
    pages_path = index / "pages.jsonl"
    if not manifest_path.is_file() or not pages_path.is_file():
        raise FileNotFoundError(
            f"未找到完整索引: {index}\n"
            "请先运行 build_menglin_index.py 对用户持有的 PDF 建立本地 OCR 索引。"
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    pages = [
        json.loads(line)
        for line in pages_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return manifest, pages


def search_index(
    query_text: str,
    pages: list[dict[str, object]],
    max_results: int = 8,
    snippet_chars: int = 180,
    pdf_page_from: int | None = None,
    pdf_page_to: int | None = None,
) -> tuple[str, list[dict[str, object]]]:
    query = compact(query_text)
    ranked: list[tuple[float, int, int, str, dict[str, object]]] = []
    for page in pages:
        pdf_page = int(page["pdf_page"])
        if pdf_page_from is not None and pdf_page < pdf_page_from:
            continue
        if pdf_page_to is not None and pdf_page > pdf_page_to:
            continue
        match = match_page(query, page)
        if match is None:
            continue
        score, start, size, quality = match
        ranked.append((score, start, size, quality, page))
    ranked.sort(key=lambda item: (-item[0], int(item[4]["pdf_page"])))

    results: list[dict[str, object]] = []
    for score, start, size, quality, page in ranked[:max_results]:
        results.append({
            "source_key": page.get("source_key"),
            "pdf_page": page.get("pdf_page"),
            "book_page": page.get("book_page"),
            "score": round(score, 2),
            "match_quality": quality,
            "snippet": snippet_for(str(page.get("text") or ""), start, size, snippet_chars),
            "source_warning": "OCR 可能有错字、脱字或分段错误；关键原句必须回看 PDF 页图。",
        })
    return query, results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", help="梦象、动作、状态或要反向查找的主题")
    parser.add_argument("--index", type=Path, default=default_index())
    parser.add_argument("--max-results", type=int, default=8)
    parser.add_argument("--snippet-chars", type=int, default=180)
    parser.add_argument("--pdf-page-from", type=int, help="只检索该 PDF 页及之后")
    parser.add_argument("--pdf-page-to", type=int, help="只检索该 PDF 页及之前")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--format", choices=("json", "text"), default="json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.status and not args.query:
        raise SystemExit("--query 或 --status 至少提供一个")
    if args.max_results < 1 or args.max_results > 50:
        raise SystemExit("--max-results 必须在 1–50 之间")
    if args.snippet_chars < 40 or args.snippet_chars > 500:
        raise SystemExit("--snippet-chars 必须在 40–500 之间")
    if args.pdf_page_from is not None and args.pdf_page_from < 1:
        raise SystemExit("--pdf-page-from 必须大于 0")
    if args.pdf_page_to is not None and args.pdf_page_to < 1:
        raise SystemExit("--pdf-page-to 必须大于 0")
    if (
        args.pdf_page_from is not None
        and args.pdf_page_to is not None
        and args.pdf_page_from > args.pdf_page_to
    ):
        raise SystemExit("--pdf-page-from 不能大于 --pdf-page-to")

    index = args.index.expanduser().resolve()
    try:
        manifest, pages = load_index(index)
    except (FileNotFoundError, json.JSONDecodeError) as error:
        raise SystemExit(str(error)) from error

    if args.status:
        print(json.dumps({"index": str(index), "manifest": manifest}, ensure_ascii=False, indent=2))
        return

    query, results = search_index(
        args.query,
        pages,
        args.max_results,
        args.snippet_chars,
        args.pdf_page_from,
        args.pdf_page_to,
    )
    if args.format == "text":
        if not results:
            print("NO_MATCH")
        for item in results:
            page = f"PDF {item['pdf_page']}"
            if item["book_page"] is not None:
                page += f" / 书页 {item['book_page']}"
            print(f"{page} {item['match_quality']} score={item['score']} {item['snippet']}")
        return

    print(json.dumps({
        "query": args.query,
        "normalized_query": query,
        "index": str(index),
        "source_sha256": manifest.get("source_sha256"),
        "match_count": len(results),
        "results": results,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
