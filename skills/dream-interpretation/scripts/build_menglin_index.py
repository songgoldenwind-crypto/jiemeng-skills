#!/usr/bin/env python3
"""Build complete private knowledge directly inside the current skill."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from internalize_menglin_index import LAST_BOOK_PAGE, clean_text


SOURCE_KEY = "menglin-xuanjie-1993-user-pdf"
EXPECTED_SHA256 = "0be41e3af522be1546d17c2fba3757a8c5ad73cc9aa5dd26fd7371bf5971be2e"
EXPECTED_PAGES = 369
CJK_SPACE_RE = re.compile(r"(?<=[\u3400-\u9fff])[ \t]+(?=[\u3400-\u9fff])")
PAGE_COUNT_RE = re.compile(r"^Pages:\s+(\d+)\s*$", re.MULTILINE)


def default_output() -> Path:
    skill_root = Path(__file__).resolve().parents[1]
    return skill_root / "references/.private/extended-corpus"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_binary(name: str) -> str:
    value = shutil.which(name)
    if not value:
        raise RuntimeError(f"未找到 {name}；请先安装 Poppler 和 Tesseract chi_sim 语言包")
    return value


def command_output(args: list[str]) -> str:
    result = subprocess.run(args, text=True, capture_output=True, check=False)
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise RuntimeError(f"命令失败: {args[0]}: {detail}")
    return result.stdout


def pdf_page_count(pdfinfo: str, source: Path) -> int:
    output = command_output([pdfinfo, str(source)])
    match = PAGE_COUNT_RE.search(output)
    if not match:
        raise RuntimeError("pdfinfo 未返回页数")
    return int(match.group(1))


def tesseract_version(tesseract: str) -> str:
    first_line = command_output([tesseract, "--version"]).splitlines()[0]
    return first_line.strip()


def normalize_display(text: str) -> str:
    value = text.replace("\r\n", "\n").replace("\r", "\n")
    value = CJK_SPACE_RE.sub("", value)
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def compact_search_text(text: str) -> str:
    return "".join(re.findall(r"[\u3400-\u9fffA-Za-z0-9]+", text)).lower()


def write_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def ocr_page(
    page: int,
    source: Path,
    raw_directory: Path,
    pdftoppm: str,
    tesseract: str,
    dpi: int,
    language: str,
    psm: int,
) -> tuple[int, int]:
    target = raw_directory / f"page-{page:04d}.txt"
    if target.is_file():
        return page, target.stat().st_size

    with tempfile.TemporaryDirectory(prefix=f"menglin-page-{page:04d}-") as temporary:
        prefix = Path(temporary) / "page"
        command_output([
            pdftoppm,
            "-f", str(page),
            "-l", str(page),
            "-r", str(dpi),
            "-png",
            "-singlefile",
            str(source),
            str(prefix),
        ])
        image = prefix.with_suffix(".png")
        text = command_output([
            tesseract,
            str(image),
            "stdout",
            "-l", language,
            "--psm", str(psm),
        ])

    temporary_target = target.with_suffix(".txt.tmp")
    temporary_target.write_text(text, encoding="utf-8")
    temporary_target.replace(target)
    return page, target.stat().st_size


def build_corpus(raw_directory: Path, output: Path, page_count: int) -> tuple[int, str]:
    corpus_path = output / "corpus.jsonl"
    temporary = corpus_path.with_suffix(".jsonl.tmp")
    chunk_count = 0
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        for page in range(1, min(page_count, LAST_BOOK_PAGE) + 1):
            source = raw_directory / f"page-{page:04d}.txt"
            if not source.is_file():
                continue
            display = clean_text(normalize_display(source.read_text(encoding="utf-8")))
            if not display:
                continue
            chunk_count += 1
            record = {
                "chunk_id": f"knowledge-{chunk_count:04d}",
                "text": display,
                "search_text": compact_search_text(display),
            }
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    temporary.replace(corpus_path)
    return chunk_count, sha256_file(corpus_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="用户持有的《梦林玄解》PDF")
    parser.add_argument("--output", type=Path, default=default_output())
    parser.add_argument("--dpi", type=int, default=220)
    parser.add_argument("--language", default="chi_sim")
    parser.add_argument("--psm", type=int, default=3)
    parser.add_argument("--jobs", type=int, default=min(4, os.cpu_count() or 1))
    parser.add_argument(
        "--allow-different-source",
        action="store_true",
        help="允许索引与已登记 SHA-256 不同的版本（会在 manifest 标记）",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source = args.source.expanduser().resolve()
    output = args.output.expanduser().resolve()
    if not source.is_file():
        raise SystemExit(f"找不到 PDF: {source}")
    if args.dpi < 100 or args.dpi > 600:
        raise SystemExit("--dpi 必须在 100–600 之间")
    if args.jobs < 1 or args.jobs > 16:
        raise SystemExit("--jobs 必须在 1–16 之间")

    try:
        pdftoppm = require_binary("pdftoppm")
        pdfinfo = require_binary("pdfinfo")
        tesseract = require_binary("tesseract")
        page_count = pdf_page_count(pdfinfo, source)
        source_sha256 = sha256_file(source)
        tess_version = tesseract_version(tesseract)
    except RuntimeError as error:
        raise SystemExit(str(error)) from error

    source_matches_registry = source_sha256 == EXPECTED_SHA256
    if not source_matches_registry and not args.allow_different_source:
        raise SystemExit(
            "PDF SHA-256 与已登记版本不同；如确认是另一版本，再加 "
            "--allow-different-source"
        )

    config = {
        "source_key": SOURCE_KEY,
        "source_path": str(source),
        "source_sha256": source_sha256,
        "source_matches_registry": source_matches_registry,
        "page_count": page_count,
        "expected_page_count": EXPECTED_PAGES,
        "dpi": args.dpi,
        "language": args.language,
        "psm": args.psm,
        "tesseract_version": tess_version,
        "private_knowledge_last_source_page": LAST_BOOK_PAGE,
    }

    output.mkdir(parents=True, exist_ok=True)
    state_path = output / "build-state.json"
    if state_path.is_file():
        previous = json.loads(state_path.read_text(encoding="utf-8"))
        comparable = {key: previous.get(key) for key in config}
        if comparable != config:
            raise SystemExit(
                f"现有索引配置不同，为避免混合 OCR，请更换 --output: {output}"
            )
    elif any(output.iterdir()):
        raise SystemExit(f"输出目录非空且无 build-state.json，请更换 --output: {output}")

    write_json(state_path, {**config, "status": "building"})
    raw_directory = output / "raw"
    raw_directory.mkdir(exist_ok=True)
    pending = [
        page
        for page in range(1, page_count + 1)
        if not (raw_directory / f"page-{page:04d}.txt").is_file()
    ]
    completed = page_count - len(pending)
    print(
        f"source_sha256={source_sha256} pages={page_count} "
        f"resume_completed={completed} pending={len(pending)} output={output}",
        flush=True,
    )

    try:
        with ThreadPoolExecutor(max_workers=args.jobs) as executor:
            futures = {
                executor.submit(
                    ocr_page,
                    page,
                    source,
                    raw_directory,
                    pdftoppm,
                    tesseract,
                    args.dpi,
                    args.language,
                    args.psm,
                ): page
                for page in pending
            }
            for future in as_completed(futures):
                page, byte_count = future.result()
                completed += 1
                print(f"OCR {completed}/{page_count} pdf_page={page} bytes={byte_count}", flush=True)
    except (RuntimeError, OSError) as error:
        write_json(state_path, {**config, "status": "interrupted", "completed_pages": completed})
        raise SystemExit(str(error)) from error

    chunk_count, content_sha256 = build_corpus(raw_directory, output, page_count)
    private_manifest = {
        "schema_version": 1,
        "status": "ready",
        "scope": "complete_private_knowledge",
        "chunk_count": chunk_count,
        "content_sha256": content_sha256,
    }
    build_receipt = {
        **config,
        "status": "complete" if completed == page_count else "incomplete",
        "indexed_pages": completed,
        "chunk_count": chunk_count,
        "content_sha256": content_sha256,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "distribution": "private in-skill knowledge; excluded from public packages",
    }
    write_json(output / "manifest.json", private_manifest)
    write_json(state_path, build_receipt)
    print(
        f"knowledge=internalized integrity=verified chunks={chunk_count}",
        flush=True,
    )


if __name__ == "__main__":
    main()
