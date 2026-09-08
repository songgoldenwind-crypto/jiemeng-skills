#!/usr/bin/env python3
"""Install the bundled dream-interpretation skill into supported layouts."""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_NAME = "dream-interpretation"
SKILL_SOURCE = REPO_ROOT / "skills" / SKILL_NAME

USER_PATHS = {
    "universal": Path(".agents/skills"),
    "codex": Path(".codex/skills"),
    "claude": Path(".claude/skills"),
    "cursor": Path(".cursor/skills"),
    "gemini": Path(".gemini/skills"),
    "copilot": Path(".copilot/skills"),
    "opencode": Path(".config/opencode/skills"),
    "windsurf": Path(".codeium/windsurf/skills"),
    "cline": Path(".cline/skills"),
}

PROJECT_PATHS = {
    "universal": Path(".agents/skills"),
    "codex": Path(".agents/skills"),
    "claude": Path(".claude/skills"),
    "cursor": Path(".cursor/skills"),
    "gemini": Path(".gemini/skills"),
    "copilot": Path(".github/skills"),
    "opencode": Path(".opencode/skills"),
    "windsurf": Path(".windsurf/skills"),
    "cline": Path(".cline/skills"),
}

AGENTS = tuple(name for name in USER_PATHS if name != "universal")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--agent",
        choices=("universal", *AGENTS, "all", "custom"),
        default="universal",
    )
    parser.add_argument("--scope", choices=("user", "project"), default="user")
    parser.add_argument("--target", type=Path, help="覆盖用户目录或项目根目录")
    parser.add_argument("--destination", type=Path, help="--agent custom 的精确 skills 目录")
    parser.add_argument("--force", action="store_true", help="替换已经存在的 Skill")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def target_directories(args: argparse.Namespace) -> list[Path]:
    if args.agent == "custom":
        if args.destination is None:
            raise ValueError("--agent custom requires --destination")
        return [args.destination.expanduser().resolve()]
    if args.destination is not None:
        raise ValueError("--destination can only be used with --agent custom")

    base = args.target.expanduser() if args.target else (
        Path.home() if args.scope == "user" else Path.cwd()
    )
    layouts = USER_PATHS if args.scope == "user" else PROJECT_PATHS
    agents = AGENTS if args.agent == "all" else (args.agent,)

    destinations: list[Path] = []
    seen: set[Path] = set()
    for agent in agents:
        destination = (base / layouts[agent]).resolve()
        if destination not in seen:
            destinations.append(destination)
            seen.add(destination)
    return destinations


def remove_existing(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    else:
        shutil.rmtree(path)


def install_one(source: Path, destination: Path) -> None:
    """Replace a skill while carrying its private in-skill knowledge forward."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{SKILL_NAME}-install-", dir=destination.parent))
    staging = temporary / SKILL_NAME
    try:
        shutil.copytree(
            source,
            staging,
            ignore=shutil.ignore_patterns(
                ".DS_Store", "__pycache__", "*.pyc", ".private"
            ),
        )

        if destination.is_dir() and not destination.is_symlink():
            private = destination / "references" / ".private"
            if private.exists():
                if private.is_symlink() or not private.is_dir():
                    raise RuntimeError(
                        f"refusing to replace unsupported private resource: {private}"
                    )
                preserved = staging / "references" / ".private"
                preserved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(private, preserved)

        if destination.exists() or destination.is_symlink():
            remove_existing(destination)
        shutil.move(str(staging), str(destination))
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


def install(args: argparse.Namespace) -> int:
    try:
        destinations = target_directories(args)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    operations = [(SKILL_SOURCE, directory / SKILL_NAME) for directory in destinations]
    conflicts = [destination for _, destination in operations if destination.exists() or destination.is_symlink()]
    if conflicts and not args.force:
        print("error: these skill directories already exist; use --force to replace them:", file=sys.stderr)
        for conflict in conflicts:
            print(f"  {conflict}", file=sys.stderr)
        return 1

    for source, destination in operations:
        action = "would install" if args.dry_run else "installing"
        print(f"{action} {source.name} -> {destination}")
        if args.dry_run:
            continue
        try:
            install_one(source, destination)
        except (OSError, RuntimeError) as error:
            print(f"error: {error}", file=sys.stderr)
            return 1

    if not args.dry_run:
        print(f"installed {len(operations)} skill director{'y' if len(operations) == 1 else 'ies'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(install(parse_args()))
