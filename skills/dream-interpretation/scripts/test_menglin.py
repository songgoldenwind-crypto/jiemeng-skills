#!/usr/bin/env python3
"""Behavioral checks for the private in-skill knowledge layer."""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

from build_menglin_index import compact_search_text, normalize_display
from internalize_menglin_index import clean_text
from search_menglin import load_index, search_index


def main() -> None:
    spaced = "梦 蛇 入 门\n\n吉 凶 当 审 其 变"
    assert normalize_display(spaced) == "梦蛇入门\n\n吉凶当审其变"
    assert compact_search_text("水 浊，而忽澄。") == "水浊而忽澄"
    assert clean_text("条目内容\n\n304\n") == "条目内容"

    chunks = [
        {
            "chunk_id": "knowledge-0001",
            "text": "蛇入门的梦例。",
            "search_text": "蛇入门的梦例",
        },
        {
            "chunk_id": "knowledge-0002",
            "text": "水浊而忽澄，则凶中带吉。",
            "search_text": "水浊而忽澄则凶中带吉",
        },
    ]
    normalized, results = search_index("梦见水浑浊后变清", chunks, max_results=4)
    assert normalized == "水浊后澄"
    assert results
    assert results[0]["match_quality"] == "approximate_text_match"
    assert set(results[0]) == {"score", "match_quality", "snippet"}
    assert len(results[0]["snippet"]) <= 181

    normalized, results = search_index("牙齿掉落", [{
        "chunk_id": "knowledge-0003",
        "text": "梦齿落更生。",
        "search_text": "梦齿落更生",
    }])
    assert normalized == "齿落"
    assert results[0]["match_quality"] == "exact_text_match"

    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        try:
            load_index(directory)
        except FileNotFoundError:
            pass
        else:
            raise AssertionError("missing in-skill knowledge should fail closed")

        corpus = directory / "corpus.jsonl"
        corpus_bytes = b"".join(
            (json.dumps(chunk, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
            for chunk in chunks
        )
        corpus.write_bytes(corpus_bytes)
        manifest = {
            "schema_version": 1,
            "status": "ready",
            "scope": "complete_private_knowledge",
            "chunk_count": len(chunks),
            "content_sha256": hashlib.sha256(corpus_bytes).hexdigest(),
        }
        (directory / "manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        loaded_manifest, loaded_chunks = load_index(directory)
        assert loaded_manifest["chunk_count"] == 2
        assert loaded_chunks == chunks

        corpus.write_text(corpus.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        try:
            load_index(directory)
        except ValueError as error:
            assert "完整性" in str(error)
        else:
            raise AssertionError("tampered private knowledge should fail integrity checks")

    print("PASS: private in-skill knowledge search and integrity boundaries verified")


if __name__ == "__main__":
    main()
