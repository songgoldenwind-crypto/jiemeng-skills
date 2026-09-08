#!/usr/bin/env python3
"""Integration tests for installer layouts and generated archives."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALLER = REPO_ROOT / "scripts" / "install.py"
PACKAGER = REPO_ROOT / "scripts" / "package_skill.py"
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
            run(str(INSTALLER), "--target", str(root), expect=1)
            self.assertTrue(marker.exists())
            run(str(INSTALLER), "--target", str(root), "--force")
            self.assertFalse(marker.exists())
            self.assertTrue((destination / "SKILL.md").is_file())

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
            run(str(PACKAGER), "--output", str(output))

            with zipfile.ZipFile(output / f"{SKILL_NAME}.skill") as archive:
                names = archive.namelist()
                self.assertIn("SKILL.md", names)
                self.assertIn("LICENSE", names)
                self.assertIn("scripts/build_menglin_index.py", names)
                self.assertIn("scripts/search_menglin.py", names)
                self.assertIn("references/03-menglin-method.md", names)
                self.assertIn("references/menglin-xuanjie-source.json", names)
                self.assertNotIn("pages.jsonl", names)
                self.assertFalse(any(name.startswith("raw/page-") for name in names))
                self.assertNotIn(f"{SKILL_NAME}/SKILL.md", names)
                self.assertTrue(archive.read("LICENSE").startswith(b"MIT License\n"))

            with zipfile.ZipFile(output / f"{SKILL_NAME}.zip") as archive:
                names = archive.namelist()
                self.assertIn(f"{SKILL_NAME}/SKILL.md", names)
                self.assertIn(f"{SKILL_NAME}/LICENSE", names)
                self.assertNotIn("SKILL.md", names)


if __name__ == "__main__":
    unittest.main()
