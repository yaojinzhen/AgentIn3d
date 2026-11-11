"""Run the complete pure-Python inf_agent development checks."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Sequence

from inf_agent.tools.markdown_links import find_broken_markdown_links


def _run(label: str, command: Sequence[str], *, repo_root: Path) -> bool:
    print(f"\n[{label}] {' '.join(command)}", flush=True)
    completed = subprocess.run(command, cwd=repo_root, check=False)
    if completed.returncode != 0:
        print(f"[{label}] FAILED ({completed.returncode})", flush=True)
        return False
    print(f"[{label}] passed", flush=True)
    return True


def run_checks(repo_root: Path, *, python: str = sys.executable) -> int:
    """Run every local check and stop at the first failure."""

    repo_root = repo_root.resolve()
    source_paths = [
        str(path.relative_to(repo_root))
        for path in sorted((repo_root / "inf_agent").iterdir())
        if path.name not in {"outputs", "__pycache__"}
        and (path.is_dir() or path.suffix == ".py")
    ]
    commands = (
        (
            "compile",
            [python, "-m", "compileall", "-q", *source_paths],
        ),
        (
            "unit",
            [
                python,
                "-m",
                "unittest",
                "discover",
                "-s",
                "inf_agent/test",
                "-p",
                "test_*.py",
            ],
        ),
        ("indexes", [python, "-m", "inf_agent.tools.generate_indexes", "--check"]),
    )
    for label, command in commands:
        if not _run(label, command, repo_root=repo_root):
            return 1

    print("\n[markdown-links] checking local documentation targets", flush=True)
    broken = find_broken_markdown_links(repo_root)
    if broken:
        for item in broken:
            print(item.render(repo_root))
        print(f"[markdown-links] FAILED ({len(broken)} missing target(s))", flush=True)
        return 1
    print("[markdown-links] passed", flush=True)

    print("\ninf_agent checks passed", flush=True)
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run compile, unit, index, and Markdown-link checks for "
            "inf_agent."
        )
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return run_checks(args.repo_root)


if __name__ == "__main__":
    raise SystemExit(main())
