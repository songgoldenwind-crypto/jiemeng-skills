#!/usr/bin/env python3
"""Search the complete private knowledge resource stored inside this skill."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import math
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

SKILL_ROOT = Path(__file__).resolve().parents[1]
CORPUS_RELATIVE = Path("references/.private/extended-corpus")


def default_index() -> Path:
    """Return the in-skill private corpus directory (legacy API name)."""
    return SKILL_ROOT / CORPUS_RELATIVE


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


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


def match_chunk(query: str, chunk: dict[str, object]) -> tuple[float, int, int, str] | None:
    text = str(chunk.get("search_text") or "")
    if not query or not text:
        return None
    exact = text.find(query)
    if exact >= 0:
        return 1000.0 + len(query) * 20, exact, len(query), "exact_text_match"

    matcher = difflib.SequenceMatcher(None, query, text, autojunk=False)
    block = matcher.find_longest_match()
    required = max(2, math.ceil(len(query) * 0.45))
    if block.size < required:
        return None
    ratio = block.size / len(query)
    shared = len(set(query) & set(text))
    score = block.size * 25 + ratio * 100 + shared
    return score, block.b, block.size, "approximate_text_match"


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
    """Load and verify the private in-skill corpus (legacy API name)."""
    manifest_path = index / "manifest.json"
    corpus_path = index / "corpus.jsonl"
    if not manifest_path.is_file() or not corpus_path.is_file():
        raise FileNotFoundError(
            "skill 内部完整知识资源不存在。请先运行 "
            "internalize_menglin_index.py 将私有资料内化到当前 skill。"
        )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    corpus_bytes = corpus_path.read_bytes()
    expected_digest = manifest.get("content_sha256")
    actual_digest = sha256_bytes(corpus_bytes)
    if expected_digest != actual_digest:
        raise ValueError("skill 内部知识完整性校验失败")

    chunks = [
        json.loads(line)
        for line in corpus_bytes.decode("utf-8").splitlines()
        if line.strip()
    ]
    if manifest.get("chunk_count") != len(chunks):
        raise ValueError("skill 内部知识数量校验失败")
    for chunk in chunks:
        if set(chunk) != {"chunk_id", "text", "search_text"}:
            raise ValueError("skill 内部知识格式不受支持")
    return manifest, chunks


def search_index(
    query_text: str,
    chunks: list[dict[str, object]],
    max_results: int = 8,
    snippet_chars: int = 180,
) -> tuple[str, list[dict[str, object]]]:
    query = compact(query_text)
    ranked: list[tuple[float, int, int, str, dict[str, object]]] = []
    for chunk in chunks:
        match = match_chunk(query, chunk)
        if match is None:
            continue
        score, start, size, quality = match
        ranked.append((score, start, size, quality, chunk))
    ranked.sort(key=lambda item: (-item[0], str(item[4]["chunk_id"])))

    results: list[dict[str, object]] = []
    for score, start, size, quality, chunk in ranked[:max_results]:
        results.append({
            "score": round(score, 2),
            "match_quality": quality,
            "snippet": snippet_for(str(chunk.get("text") or ""), start, size, snippet_chars),
        })
    return query, results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", help="梦象、动作、状态或要反向查找的主题")
    parser.add_argument(
        "--corpus", "--index", dest="index", type=Path, default=default_index(),
        help="默认使用当前 skill 内部的私有完整知识资源",
    )
    parser.add_argument("--max-results", type=int, default=8)
    parser.add_argument("--snippet-chars", type=int, default=180)
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

    index = args.index.expanduser().resolve()
    try:
        manifest, chunks = load_index(index)
    except (FileNotFoundError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SystemExit(str(error)) from error

    if args.status:
        print(json.dumps({
            "knowledge": "ready",
            "integrity": "verified",
            "chunk_count": manifest["chunk_count"],
        }, ensure_ascii=False, indent=2))
        return

    query, results = search_index(
        args.query,
        chunks,
        args.max_results,
        args.snippet_chars,
    )
    if args.format == "text":
        if not results:
            print("NO_MATCH")
        for item in results:
            print(f"{item['match_quality']} score={item['score']} {item['snippet']}")
        return

    print(json.dumps({
        "query": args.query,
        "normalized_query": query,
        "match_count": len(results),
        "results": results,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
