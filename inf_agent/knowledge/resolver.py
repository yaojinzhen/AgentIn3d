"""Read maintained knowledge or an exact repository symbol without receipts."""

from __future__ import annotations
import ast
from pathlib import Path
from inf_agent.workspace.contracts import ContractError


def read_knowledge(
    repo_root: Path, *, document: str | None = None, symbol: str | None = None
) -> dict:
    if (document is None) == (symbol is None):
        raise ContractError("choose one document or module:symbol")
    repo_root = repo_root.resolve()
    if document is not None:
        docs = (repo_root / "inf_agent/modeling_docs").resolve()
        path = (docs / document).resolve()
        if not path.is_relative_to(docs) or path.suffix != ".md" or not path.is_file():
            raise ContractError("document must be a modeling_docs Markdown leaf")
        return {"path": path.as_posix(), "content": path.read_text(encoding="utf-8")}
    module, separator, qualname = symbol.partition(":")
    if (
        not separator
        or not all(x.isidentifier() for x in module.split("."))
        or not all(x.isidentifier() for x in qualname.split("."))
    ):
        raise ContractError("symbol must use module:qualified_symbol")
    path = repo_root.joinpath(*module.split(".")).with_suffix(".py")
    if not path.is_file():
        path = repo_root.joinpath(*module.split("."), "__init__.py")
    if not path.is_file() or not path.resolve().is_relative_to(repo_root):
        raise ContractError(f"repository source not found for {module}")
    content = path.read_text(encoding="utf-8")
    tree = ast.parse(content)
    body = tree.body
    node = None
    for name in qualname.split("."):
        node = next(
            (
                x
                for x in body
                if isinstance(x, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                and x.name == name
            ),
            None,
        )
        if node is None:
            raise ContractError(f"source symbol not found: {symbol}")
        body = node.body
    lines = content.splitlines()
    start = min([node.lineno, *(x.lineno for x in node.decorator_list)])
    return {
        "path": path.as_posix(),
        "symbol": symbol,
        "start_line": start,
        "content": "\n".join(lines[start - 1 : node.end_lineno]),
    }
