"""Validate local Markdown link targets used by inf_agent documentation."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit

INLINE_LINK_RE = re.compile(r"!?\[[^\]]*\]\(\s*(<[^>]+>|[^)\s]+)")
REFERENCE_LINK_RE = re.compile(r"^\s*\[[^\]]+\]:\s*(<[^>]+>|\S+)", re.MULTILINE)
DEFAULT_MARKDOWN_ROOTS = (
    Path("README.md"),
    Path("inf_agent/README.md"),
    Path("inf_agent/docs"),
    Path("inf_agent/modeling_docs"),
    Path("inf_agent/skills"),
)


@dataclass(frozen=True)
class BrokenMarkdownLink:
    source: Path
    line: int
    target: str

    def render(self, repo_root: Path) -> str:
        try:
            source = self.source.relative_to(repo_root).as_posix()
        except ValueError:
            source = self.source.as_posix()
        return f"{source}:{self.line}: missing local Markdown target: {self.target}"


def _without_fenced_code(text: str) -> str:
    lines = []
    fence: str | None = None
    for line in text.splitlines(keepends=True):
        marker = line.lstrip()[:3]
        if marker in {"```", "~~~"}:
            fence = None if fence == marker else marker if fence is None else fence
            lines.append("\n" if line.endswith("\n") else "")
        elif fence is None:
            lines.append(line)
        else:
            lines.append("\n" if line.endswith("\n") else "")
    return "".join(lines)


def _markdown_files(repo_root: Path, roots: tuple[Path, ...]) -> list[Path]:
    files: set[Path] = set()
    for item in roots:
        path = item if item.is_absolute() else repo_root / item
        if path.is_file() and path.suffix.casefold() == ".md":
            files.add(path.resolve())
        elif path.is_dir():
            files.update(
                candidate.resolve()
                for candidate in path.rglob("*.md")
                if "outputs" not in candidate.parts
            )
    return sorted(files, key=lambda item: item.as_posix())


def _local_target(source: Path, raw_target: str, repo_root: Path) -> Path | None:
    target = raw_target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    target = unquote(target)
    if not target or target.startswith("#"):
        return None
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc:
        return None
    path_value = parsed.path
    if not path_value or any(token in path_value for token in ("<", ">")):
        return None
    if path_value.startswith("/"):
        return (repo_root / path_value.lstrip("/")).resolve()
    return (source.parent / path_value).resolve()


def find_broken_markdown_links(
    repo_root: Path,
    *,
    roots: tuple[Path, ...] = DEFAULT_MARKDOWN_ROOTS,
) -> list[BrokenMarkdownLink]:
    """Return missing local file targets without following external URLs."""

    repo_root = repo_root.resolve()
    broken: list[BrokenMarkdownLink] = []
    for source in _markdown_files(repo_root, roots):
        text = _without_fenced_code(source.read_text(encoding="utf-8"))
        matches = [*INLINE_LINK_RE.finditer(text), *REFERENCE_LINK_RE.finditer(text)]
        for match in matches:
            raw_target = match.group(1)
            target = _local_target(source, raw_target, repo_root)
            if target is not None and not target.exists():
                broken.append(
                    BrokenMarkdownLink(
                        source=source,
                        line=text.count("\n", 0, match.start()) + 1,
                        target=raw_target.strip("<>"),
                    )
                )
    return sorted(broken, key=lambda item: (item.source.as_posix(), item.line, item.target))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check local links in inf_agent Markdown files.")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    broken = find_broken_markdown_links(args.repo_root)
    if broken:
        for item in broken:
            print(item.render(args.repo_root.resolve()))
        print(f"Markdown link check failed: {len(broken)} missing target(s)")
        return 1
    print("Markdown links are valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

