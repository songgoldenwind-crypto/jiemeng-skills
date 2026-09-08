#!/usr/bin/env python3
"""Integration tests for installer layouts and generated archives."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALLER = REPO_ROOT / "scripts" / "install.py"
PACKAGER = REPO_ROOT / "scripts" / "package_skill.py"
INTERNALIZER = (
    REPO_ROOT / "skills/dream-interpretation/scripts/internalize_menglin_index.py"
)
SKILL_NAME = "dream-interpretation"


def run(*args: str, expect: int = 0) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [sys.executable, *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != expect:
        raise AssertionError(
            f"expected exit {expect}, got {result.returncode}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


class InstallerTests(unittest.TestCase):
    def test_codex_user_layout(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run(str(INSTALLER), "--agent", "codex", "--target", str(root))
            self.assertTrue((root / ".codex/skills" / SKILL_NAME / "SKILL.md").is_file())

    def test_existing_directory_requires_force(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            destination = root / ".agents/skills" / SKILL_NAME
            destination.mkdir(parents=True)
            marker = destination / "old.txt"
            marker.write_text("old", encoding="utf-8")
            private = destination / "references/.private/extended-corpus/corpus.jsonl"
            private.parent.mkdir(parents=True)
            private.write_text("private knowledge\n", encoding="utf-8")
            run(str(INSTALLER), "--target", str(root), expect=1)
            self.assertTrue(marker.exists())
            run(str(INSTALLER), "--target", str(root), "--force")
            self.assertFalse(marker.exists())
            self.assertTrue((destination / "SKILL.md").is_file())
            self.assertEqual(private.read_text(encoding="utf-8"), "private knowledge\n")

    def test_dry_run_and_custom_destination(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            destination = root / "custom-skills"
            run(str(INSTALLER), "--agent", "custom", "--destination", str(destination), "--dry-run")
            self.assertFalse(destination.exists())
            run(str(INSTALLER), "--agent", "custom", "--destination", str(destination))
            self.assertTrue((destination / SKILL_NAME / "SKILL.md").is_file())


class PackagingTests(unittest.TestCase):
    def test_archive_layouts_and_license(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            private = (
                REPO_ROOT / "skills" / SKILL_NAME
                / "references/.private/extended-corpus/corpus.jsonl"
            )
            private.parent.mkdir(parents=True, exist_ok=True)
            private.write_text("must not be published\n", encoding="utf-8")
            try:
                run(str(PACKAGER), "--output", str(output))
            finally:
                private.unlink()
                private.parent.rmdir()
                private.parent.parent.rmdir()

            with zipfile.ZipFile(output / f"{SKILL_NAME}.skill") as archive:
                names = archive.namelist()
                self.assertIn("SKILL.md", names)
                self.assertIn("LICENSE", names)
                self.assertIn("scripts/build_menglin_index.py", names)
                self.assertIn("scripts/internalize_menglin_index.py", names)
                self.assertIn("scripts/search_menglin.py", names)
                self.assertIn("references/03-menglin-method.md", names)
                self.assertIn("references/menglin-xuanjie-source.json", names)
                self.assertNotIn("pages.jsonl", names)
                self.assertFalse(any(".private" in Path(name).parts for name in names))
                self.assertFalse(any(name.startswith("raw/page-") for name in names))
                self.assertNotIn(f"{SKILL_NAME}/SKILL.md", names)
                self.assertTrue(archive.read("LICENSE").startswith(b"MIT License\n"))

            with zipfile.ZipFile(output / f"{SKILL_NAME}.zip") as archive:
                names = archive.namelist()
                self.assertIn(f"{SKILL_NAME}/SKILL.md", names)
                self.assertIn(f"{SKILL_NAME}/LICENSE", names)
                self.assertNotIn("SKILL.md", names)


class InternalizationTests(unittest.TestCase):
    def test_complete_legacy_index_becomes_metadata_free_in_skill_corpus(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "legacy"
            destination = root / "skill/references/.private/extended-corpus"
            source.mkdir()
            (source / "manifest.json").write_text(json.dumps({
                "status": "complete",
                "indexed_pages": 369,
                "source_sha256": (
                    "0be41e3af522be1546d17c2fba3757a8"
                    "c5ad73cc9aa5dd26fd7371bf5971be2e"
                ),
            }), encoding="utf-8")
            with (source / "pages.jsonl").open("w", encoding="utf-8") as handle:
                for page in range(1, 370):
                    handle.write(json.dumps({
                        "source_key": "private-source",
                        "pdf_page": page,
                        "book_page": page - 8,
                        "text": f"知识内容{page}\n{page}",
                        "search_text": f"知识内容{page}",
                    }, ensure_ascii=False) + "\n")

            run(
                str(INTERNALIZER),
                "--from-index", str(source),
                "--destination", str(destination),
            )

            rows = [
                json.loads(line)
                for line in (destination / "corpus.jsonl").read_text(
                    encoding="utf-8"
                ).splitlines()
            ]
            manifest = json.loads(
                (destination / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(len(rows), 368)
            self.assertEqual(manifest["chunk_count"], 368)
            self.assertTrue(all(
                set(row) == {"chunk_id", "text", "search_text"}
                for row in rows
            ))
            self.assertEqual(rows[-1]["text"], "知识内容368")
            self.assertNotIn("知识内容369", (destination / "corpus.jsonl").read_text())


if __name__ == "__main__":
    unittest.main()
