#!/usr/bin/env python3
"""Behavioral checks for the bundled dream dictionary and search ranking."""

from __future__ import annotations

from search_dreams import parse_dictionary, search_entries


def top(query: str, category: str | None = None) -> dict[str, object]:
    _, results = search_entries(query, category, 5)
    assert results, query
    return results[0]


def main() -> None:
    categories, entries = parse_dictionary()
    assert len(categories) == 27
    assert len(entries) == 951

    assert top("梦见牙齿掉了")["entry"] == "齿自落者父母凶"
    assert top("梦见蛇咬我")["entry"] == "蛇咬人主得大财"
    assert top("梦见井水")["entry"] == "取井水清吉浑凶"

    _, modern = search_entries("梦见手机碎了")
    assert modern == []

    _, reverse = search_entries("什么梦代表发财")
    assert reverse
    assert all(item["match_scope"] == "omen" for item in reverse)
    assert {item["entry"] for item in reverse} >= {
        "入果园中大发财",
        "火焰炎炎主发财",
    }

    wings = top("梦见自己长出翅膀飞起来")
    assert wings["source_warning"] is not None

    fish = top("梦见鱼", "鱼虾")
    assert fish["category"] == "龟鳖 鱼虾 昆虫"

    print("PASS: 27 categories, 951 segments, common queries and boundaries verified")


if __name__ == "__main__":
    main()
