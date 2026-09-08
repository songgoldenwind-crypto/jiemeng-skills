#!/usr/bin/env python3
"""Search the bundled classical dream dictionary by scene, action, or omen."""

from __future__ import annotations

import argparse
import difflib
import json
import re
from dataclasses import dataclass
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = SKILL_ROOT / "references" / "classical-dictionary.txt"
CATEGORY_RE = re.compile(r"^([一二三四五六七八九十]+)、(.+)$")

ALIASES = (
    ("去世的人", "死人"),
    ("过世的人", "死人"),
    ("死去的人", "死人"),
    ("牙齿脱落", "齿自落"),
    ("牙齿掉落", "齿自落"),
    ("牙齿掉", "齿自落"),
    ("牙齿", "齿"),
    ("房屋", "屋宅"),
    ("房子", "屋宅"),
    ("坍塌", "倒陷"),
    ("塌了", "倒陷"),
    ("镜子", "镜"),
    ("鞋子", "鞋"),
    ("帽子", "帽"),
    ("洗澡", "沐浴"),
    ("厕所", "厕"),
    ("大便", "屎"),
    ("粪便", "粪"),
    ("小便", "尿"),
    ("钞票", "钱"),
    ("太阳", "日"),
    ("月亮", "月"),
    ("星星", "星"),
    ("下雨", "雨"),
    ("下雪", "雪"),
    ("闪电", "电光"),
    ("打雷", "雷"),
    ("彩虹", "虹"),
    ("棺材", "棺"),
    ("坟墓", "冢墓"),
    ("复生", "复活"),
    ("复活了", "复活"),
    ("老虎", "虎"),
    ("乌龟", "龟"),
    ("兔子", "兔"),
    ("老鼠", "鼠"),
    ("狗", "犬"),
    ("长出翅膀", "生羽翼"),
    ("翅膀", "羽翼"),
    ("飞起来", "飞"),
    ("吵架", "相骂"),
    ("打架", "相打"),
    ("逃出来", "脱"),
    ("逃走了", "逃走"),
)

NOISE_RE = re.compile(
    r"什么梦|哪些梦|哪种梦|哪类梦|梦见|梦到|梦里|梦中|做梦|梦的是|"
    r"代表|预示|意味着|我自己|自己|我|有人|一个|一只|一些|很多|"
    r"看见|看到|出现|然后|后来|最后|正在|有个|有一|了|的"
)
NON_CJK_RE = re.compile(r"[^\u3400-\u9fff]+")

SUSPICIOUS = (
    "癸天上屋", "云雾遮事", "身人土中", "身生羽翼飞大吉身逃走",
    "的履主", "锋快大古", "死央瓦落", "尾中生草", "穿并见水",
    "井中欲于", "长子匈", "超盖仓库", "生桥女", "快喜饨",
    "乌蛇践物", "披洗夜马", "奔统百凶", "大使满地", "凤集拳上",
    "熊罢主", "群免上天", "浩鬼在园", "螺狮生在", "峰蜈交戏", "恙螂作堆",
)


@dataclass(frozen=True)
class Entry:
    category_index: int
    category: str
    data_line: int
    source_line: int
    ordinal: int
    text: str

    @property
    def identifier(self) -> str:
        return f"{self.category_index:02d}-{self.source_line:03d}-{self.ordinal}"


def normalize_query(text: str) -> str:
    value = text.strip()
    for old, new in ALIASES:
        value = value.replace(old, new)
    value = NOISE_RE.sub("", value)
    return NON_CJK_RE.sub("", value)


def parse_dictionary(path: Path = DATA_PATH) -> tuple[list[str], list[Entry]]:
    categories: list[str] = []
    entries: list[Entry] = []
    category = ""
    category_index = 0
    for data_line, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip().lstrip("\ufeff")
        if not line:
            continue
        match = CATEGORY_RE.match(line)
        if match:
            category_index += 1
            category = match.group(2).strip()
            categories.append(category)
            continue
        if not category:
            continue
        for ordinal, text in enumerate(line.split(), 1):
            entries.append(
                Entry(category_index, category, data_line, data_line + 5, ordinal, text)
            )
    return categories, entries


def longest_common_subsequence(a: str, b: str) -> int:
    row = [0] * (len(b) + 1)
    for char_a in a:
        previous = 0
        for index, char_b in enumerate(b, 1):
            saved = row[index]
            if char_a == char_b:
                row[index] = previous + 1
            else:
                row[index] = max(row[index], row[index - 1])
            previous = saved
    return row[-1]


def scene_prefix(text: str) -> str:
    marker = text.find("主")
    if marker >= 2:
        return text[:marker]
    return text[: max(3, len(text) // 2)]


def score(query: str, entry: Entry) -> tuple[float, str] | None:
    text = normalize_query(entry.text)
    scene = normalize_query(scene_prefix(entry.text))
    if not query or not text:
        return None

    shared = set(query) & set(scene)
    block = difflib.SequenceMatcher(None, query, scene).find_longest_match().size
    lcs = longest_common_subsequence(query, scene)
    full_shared = set(query) & set(text)
    full_block = difflib.SequenceMatcher(None, query, text).find_longest_match().size
    scene_match = not (
        (len(query) >= 3 and block < 2 and len(shared) < 2)
        or (len(query) == 2 and block < 2 and len(shared) < 2)
        or (len(query) == 1 and query not in scene)
    )
    # Prediction-side matches are for deliberate reverse lookups such as “发财”.
    # Require the whole normalized query so a long dream narrative does not pull
    # in unrelated entries merely because their predicted outcomes share two chars.
    full_match = query in text

    if not scene_match and not full_match:
        return None

    value = 0.0
    scope = "scene" if scene_match else "omen"
    if query in scene:
        value += 120
    elif len(scene) >= 2 and scene in query:
        value += 90
    value += block * 16
    value += lcs * 10
    value += len(shared) * 4
    value += difflib.SequenceMatcher(None, query, scene).ratio() * 20

    if scope == "omen":
        value = 20 + full_block * 8 + len(full_shared) * 2
        if query in text:
            value += 30
    elif query in text and query not in scene:
        value += 6
    return value, scope


def warning_for(text: str) -> str | None:
    if any(fragment in text for fragment in SUSPICIOUS):
        return "此版本原句疑有误字、缺字或粘连；请按原样引用并降低结论强度"
    return None


def search_entries(
    query_text: str,
    category: str | None = None,
    max_results: int = 8,
) -> tuple[str, list[dict[str, object]]]:
    _, entries = parse_dictionary()
    query = normalize_query(query_text)
    category_filter = normalize_query(category or "")
    ranked: list[tuple[float, str, Entry]] = []
    for entry in entries:
        if category_filter and category_filter not in normalize_query(entry.category):
            continue
        match = score(query, entry)
        if match is not None:
            value, scope = match
            ranked.append((value, scope, entry))
    ranked.sort(key=lambda item: (-item[0], item[2].source_line, item[2].ordinal))

    results: list[dict[str, object]] = []
    for value, scope, entry in ranked[:max_results]:
        results.append(
            {
                "id": entry.identifier,
                "score": round(value, 2),
                "match_scope": scope,
                "category": entry.category,
                "entry": entry.text,
                "data_line": entry.data_line,
                "source_line": entry.source_line,
                "source_warning": warning_for(entry.text),
            }
        )
    return query, results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", help="梦中的核心对象、动作和状态，或反向查询的梦兆结果")
    parser.add_argument("--category", help="只检索名称包含该文字的门类")
    parser.add_argument("--max-results", type=int, default=8)
    parser.add_argument("--list-categories", action="store_true")
    parser.add_argument("--format", choices=("json", "text"), default="json")
    args = parser.parse_args()

    categories, entries = parse_dictionary()
    if args.list_categories:
        for index, category in enumerate(categories, 1):
            print(f"{index:02d}\t{category}")
        return
    if not args.query:
        parser.error("--query 或 --list-categories 至少提供一个")
    if args.max_results < 1:
        parser.error("--max-results 必须大于 0")

    query, results = search_entries(args.query, args.category, args.max_results)

    if args.format == "text":
        if not results:
            print("NO_MATCH")
        for item in results:
            warning = f" WARNING={item['source_warning']}" if item["source_warning"] else ""
            print(
                f"{item['id']} score={item['score']} category={item['category']} "
                f"entry={item['entry']}{warning}"
            )
        return

    print(
        json.dumps(
            {
                "query": args.query,
                "normalized_query": query,
                "category_filter": args.category,
                "match_count": len(results),
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
