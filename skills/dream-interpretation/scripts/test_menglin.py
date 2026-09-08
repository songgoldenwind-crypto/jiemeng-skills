#!/usr/bin/env python3
"""Behavioral checks for the optional Menglin OCR search layer."""

from __future__ import annotations

import tempfile
from pathlib import Path

from build_menglin_index import compact_search_text, normalize_display
from search_menglin import load_index, search_index


def main() -> None:
    spaced = "梦 蛇 入 门\n\n吉 凶 当 审 其 变"
    assert normalize_display(spaced) == "梦蛇入门\n\n吉凶当审其变"
    assert compact_search_text("水 浊，而忽澄。") == "水浊而忽澄"

    pages = [
        {
            "source_key": "test",
            "pdf_page": 10,
            "book_page": 2,
            "text": "蛇入门的梦例。",
            "search_text": "蛇入门的梦例",
        },
        {
            "source_key": "test",
            "pdf_page": 311,
            "book_page": 303,
            "text": "水浊而忽澄，则凶中带吉。",
            "search_text": "水浊而忽澄则凶中带吉",
        },
    ]
    normalized, results = search_index("梦见水浑浊后变清", pages, max_results=4)
    assert normalized == "水浊后澄"
    assert results
    assert results[0]["pdf_page"] == 311
    assert results[0]["match_quality"] == "approximate_ocr"
    assert len(results[0]["snippet"]) <= 181

    normalized, results = search_index("牙齿掉落", [{
        "source_key": "test",
        "pdf_page": 111,
        "book_page": 103,
        "text": "梦齿落更生。",
        "search_text": "梦齿落更生",
    }])
    assert normalized == "齿落"
    assert results[0]["match_quality"] == "exact_ocr"

    _, results = search_index("梦变", pages, pdf_page_from=300)
    assert results == []

    with tempfile.TemporaryDirectory() as temporary:
        try:
            load_index(Path(temporary))
        except FileNotFoundError:
            pass
        else:
            raise AssertionError("missing index should fail closed")

    print("PASS: Menglin OCR normalization, bounded search, and absent-index boundary verified")


if __name__ == "__main__":
    main()
