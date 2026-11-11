"""Generate machine-readable indexes for agent asset authoring as a development tool.

The generator deliberately uses Python's standard-library ``ast`` module
instead of importing Infinigen modules. This keeps indexing independent from
``bpy`` and avoids executing asset module side effects.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = "1.0"
GENERATOR_ID = "inf_agent.indexing.generator"
DEFAULT_SOURCE_ROOTS = ("infinigen/assets", "infinigen/core")
DEFAULT_DOC_ROOT = "inf_agent/modeling_docs"
DEFAULT_OUTPUT_DIR = "inf_agent/modeling_docs/indexes"
API_LEAF_ROOTS = (
    "api_reference/function_api",
    "api_reference/material_api",
    "api_reference/node_api",
)

INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
FENCED_CODE_RE = re.compile(r"```(?:python|py|text)?\s*\n(.*?)```", re.DOTALL)
IDENTIFIER_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*\b")
SOURCE_REF_RE = re.compile(r"`(infinigen/[^`\s]+)`")


class IndexGenerationError(RuntimeError):
    """Raised when an index input is invalid or internally inconsistent."""


def _repo_relative(path: Path, repo_root: Path) -> str:
    return path.resolve().relative_to(repo_root.resolve()).as_posix()


def _doc_relative(path: Path, doc_root: Path) -> str:
    return path.resolve().relative_to(doc_root.resolve()).as_posix()


def _module_name(path: Path, repo_root: Path) -> str:
    relative = path.resolve().relative_to(repo_root.resolve()).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _safe_unparse(node: ast.AST | None) -> str | None:
    if node is None:
        return None
    try:
        return ast.unparse(node)
    except (ValueError, TypeError):
        return None


def _format_arg(arg: ast.arg, default: ast.AST | None = None) -> str:
    value = arg.arg
    annotation = _safe_unparse(arg.annotation)
    if annotation:
        value += f": {annotation}"
    if default is not None:
        value += f" = {_safe_unparse(default) or '...'}"
    return value


def _format_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    args = node.args
    positional = [*args.posonlyargs, *args.args]
    default_offset = len(positional) - len(args.defaults)
    parts: list[str] = []

    for index, arg in enumerate(positional):
        default = args.defaults[index - default_offset] if index >= default_offset else None
        parts.append(_format_arg(arg, default))
        if args.posonlyargs and index + 1 == len(args.posonlyargs):
            parts.append("/")

    if args.vararg is not None:
        parts.append("*" + _format_arg(args.vararg))
    elif args.kwonlyargs:
        parts.append("*")

    for arg, default in zip(args.kwonlyargs, args.kw_defaults, strict=True):
        parts.append(_format_arg(arg, default))

    if args.kwarg is not None:
        parts.append("**" + _format_arg(args.kwarg))

    result = f"({', '.join(parts)})"
    returns = _safe_unparse(node.returns)
    if returns:
        result += f" -> {returns}"
    return result


def _docstring_summary(node: ast.AST) -> str | None:
    if not isinstance(
        node,
        (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef),
    ):
        return None
    value = ast.get_docstring(node, clean=True)
    if not value:
        return None
    return value.splitlines()[0].strip() or None


def _decorators(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> list[str]:
    return [value for item in node.decorator_list if (value := _safe_unparse(item))]


def _function_roles(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    source_path: str,
    decorators: list[str],
) -> list[str]:
    roles: set[str] = set()
    normalized = f"/{source_path}/"

    if any("to_nodegroup" in decorator for decorator in decorators):
        roles.add("nodegroup_function")
    if any("to_material" in decorator for decorator in decorators):
        roles.add("material_function")

    used_names = {
        child.id for child in ast.walk(node) if isinstance(child, ast.Name)
    }
    used_attrs = {
        child.attr for child in ast.walk(node) if isinstance(child, ast.Attribute)
    }
    if "NodeWrangler" in used_names or "new_node" in used_attrs:
        roles.add("node_graph_function")

    if "/infinigen/assets/materials/" in normalized:
        roles.add("material_function")
    if "/infinigen/core/util/" in normalized or "/infinigen/assets/utils/" in normalized:
        roles.add("utility_function")
    if "/infinigen/core/" in normalized:
        roles.add("core_function")
    if "/infinigen/assets/objects/" in normalized:
        roles.add("asset_helper")
    return sorted(roles)


def _class_roles(source_path: str, class_name: str) -> list[str]:
    roles: set[str] = set()
    normalized = f"/{source_path}/"
    if "/infinigen/assets/materials/" in normalized:
        roles.add("material_class")
    if "/infinigen/assets/objects/" in normalized and class_name.endswith("Factory"):
        roles.add("asset_factory_candidate")
    if "/infinigen/core/" in normalized:
        roles.add("core_class")
    return sorted(roles)


def _resolve_relative_import(module: str, imported: str | None, level: int) -> str:
    if level == 0:
        return imported or ""
    package = module.split(".")[:-1]
    keep = max(0, len(package) - level + 1)
    prefix = package[:keep]
    if imported:
        prefix.extend(imported.split("."))
    return ".".join(prefix)


def _import_aliases(tree: ast.Module, module: str) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for item in node.names:
                aliases[item.asname or item.name.split(".")[0]] = item.name
        elif isinstance(node, ast.ImportFrom):
            imported_module = _resolve_relative_import(module, node.module, node.level)
            for item in node.names:
                if item.name == "*":
                    continue
                name = item.asname or item.name
                aliases[name] = ".".join(part for part in (imported_module, item.name) if part)
    return aliases


def _resolved_base(base: str, module: str, aliases: dict[str, str]) -> str:
    head, dot, tail = base.partition(".")
    if head in aliases:
        return aliases[head] + (dot + tail if dot else "")
    if not dot:
        return f"{module}.{base}"
    return base


def _symbol_base(
    *,
    symbol_id: str,
    name: str,
    qualname: str,
    kind: str,
    module: str,
    source_path: str,
    node: ast.AST,
    roles: Iterable[str],
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": symbol_id,
        "name": name,
        "qualname": qualname,
        "kind": kind,
        "module": module,
        "source_path": source_path,
        "line_start": getattr(node, "lineno", None),
        "line_end": getattr(node, "end_lineno", getattr(node, "lineno", None)),
        "roles": sorted(set(roles)),
        "api_docs": [],
    }
    summary = _docstring_summary(node)
    if summary:
        result["summary"] = summary
    return result


def _assignment_names(node: ast.Assign | ast.AnnAssign) -> list[str]:
    targets: list[ast.expr]
    if isinstance(node, ast.AnnAssign):
        targets = [node.target]
    else:
        targets = list(node.targets)
    return [target.id for target in targets if isinstance(target, ast.Name)]


def _add_symbol(symbols: dict[str, dict[str, Any]], symbol: dict[str, Any]) -> None:
    existing = symbols.get(symbol["id"])
    if existing is None:
        line = symbol.get("line_start")
        if line is not None:
            symbol["declaration_lines"] = [line]
        symbols[symbol["id"]] = symbol
        return

    line = symbol.get("line_start")
    if line is not None and line not in existing["declaration_lines"]:
        existing["declaration_lines"].append(line)
        existing["declaration_lines"].sort()
    existing["roles"] = sorted(set(existing["roles"]) | set(symbol["roles"]))
    if symbol.get("value") is not None:
        values = set(existing.get("values", []))
        if existing.get("value") is not None:
            values.add(existing["value"])
        values.add(symbol["value"])
        existing["values"] = sorted(values)
        existing["value"] = symbol["value"]


def _scan_python_file(
    path: Path,
    repo_root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    source_path = _repo_relative(path, repo_root)
    module = _module_name(path, repo_root)
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=source_path)
    except (OSError, UnicodeError, SyntaxError) as error:
        return [], [{"source_path": source_path, "error": str(error)}]

    aliases = _import_aliases(tree, module)
    symbols: dict[str, dict[str, Any]] = {}

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            class_id = f"{module}:{node.name}"
            bases = [value for item in node.bases if (value := _safe_unparse(item))]
            class_symbol = _symbol_base(
                symbol_id=class_id,
                name=node.name,
                qualname=node.name,
                kind="class",
                module=module,
                source_path=source_path,
                node=node,
                roles=_class_roles(source_path, node.name),
            )
            class_symbol["bases"] = bases
            class_symbol["resolved_bases"] = [
                _resolved_base(base, module, aliases) for base in bases
            ]
            class_symbol["decorators"] = _decorators(node)
            class_symbol["methods"] = []
            _add_symbol(symbols, class_symbol)

            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    qualname = f"{node.name}.{child.name}"
                    method_id = f"{module}:{qualname}"
                    decorators = _decorators(child)
                    method_symbol = _symbol_base(
                        symbol_id=method_id,
                        name=child.name,
                        qualname=qualname,
                        kind="async_method" if isinstance(child, ast.AsyncFunctionDef) else "method",
                        module=module,
                        source_path=source_path,
                        node=child,
                        roles=_function_roles(child, source_path, decorators),
                    )
                    method_symbol["parent_id"] = class_id
                    method_symbol["signature"] = _format_signature(child)
                    method_symbol["decorators"] = decorators
                    _add_symbol(symbols, method_symbol)
                    class_symbol["methods"].append(method_id)

                if node.name == "Nodes" and isinstance(child, (ast.Assign, ast.AnnAssign)):
                    value_node = child.value
                    value = _safe_unparse(value_node)
                    for name in _assignment_names(child):
                        qualname = f"Nodes.{name}"
                        attribute_symbol = _symbol_base(
                            symbol_id=f"{module}:{qualname}",
                            name=name,
                            qualname=qualname,
                            kind="class_attribute",
                            module=module,
                            source_path=source_path,
                            node=child,
                            roles=["node_enum"],
                        )
                        attribute_symbol["parent_id"] = class_id
                        attribute_symbol["value"] = value
                        if isinstance(value_node, ast.Constant) and isinstance(value_node.value, str):
                            attribute_symbol["bl_idname"] = value_node.value
                        _add_symbol(symbols, attribute_symbol)

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            decorators = _decorators(node)
            symbol = _symbol_base(
                symbol_id=f"{module}:{node.name}",
                name=node.name,
                qualname=node.name,
                kind="async_function" if isinstance(node, ast.AsyncFunctionDef) else "function",
                module=module,
                source_path=source_path,
                node=node,
                roles=_function_roles(node, source_path, decorators),
            )
            symbol["signature"] = _format_signature(node)
            symbol["decorators"] = decorators
            _add_symbol(symbols, symbol)

        elif source_path == "infinigen/assets/composition/material_assignments.py" and isinstance(
            node, (ast.Assign, ast.AnnAssign)
        ):
            value_node = node.value
            value = _safe_unparse(value_node)
            if value and len(value) > 500:
                value = value[:497] + "..."
            for name in _assignment_names(node):
                if name.startswith("_"):
                    continue
                symbol = _symbol_base(
                    symbol_id=f"{module}:{name}",
                    name=name,
                    qualname=name,
                    kind="module_variable",
                    module=module,
                    source_path=source_path,
                    node=node,
                    roles=["material_assignment"],
                )
                symbol["value"] = value
                _add_symbol(symbols, symbol)

    return list(symbols.values()), []


def _propagate_factory_roles(symbols: list[dict[str, Any]]) -> None:
    classes = {symbol["id"]: symbol for symbol in symbols if symbol["kind"] == "class"}
    by_simple_name: dict[str, list[str]] = defaultdict(list)
    by_full_name: dict[str, str] = {}
    for symbol_id, symbol in classes.items():
        by_simple_name[symbol["name"]].append(symbol_id)
        by_full_name[f"{symbol['module']}.{symbol['qualname']}"] = symbol_id

    for symbol in classes.values():
        if symbol["name"] == "AssetFactory" or any(
            base.split(".")[-1] == "AssetFactory" for base in symbol.get("bases", [])
        ):
            symbol["roles"] = sorted(set(symbol["roles"]) | {"asset_factory"})

    changed = True
    while changed:
        changed = False
        factory_ids = {
            symbol_id
            for symbol_id, symbol in classes.items()
            if "asset_factory" in symbol["roles"]
        }
        for symbol in classes.values():
            if "asset_factory" in symbol["roles"]:
                continue
            parent_ids: set[str] = set()
            for base in symbol.get("resolved_bases", []):
                if base in by_full_name:
                    parent_ids.add(by_full_name[base])
                parent_ids.update(by_simple_name.get(base.split(".")[-1], []))
            if parent_ids & factory_ids:
                symbol["roles"] = sorted(set(symbol["roles"]) | {"asset_factory"})
                changed = True

    factory_ids = {
        symbol_id
        for symbol_id, symbol in classes.items()
        if "asset_factory" in symbol["roles"]
    }
    for symbol in symbols:
        if symbol.get("parent_id") in factory_ids and symbol["kind"] in {"method", "async_method"}:
            symbol["roles"] = sorted(set(symbol["roles"]) | {"asset_factory_method"})


def _markdown_code_tokens(text: str) -> set[str]:
    segments = INLINE_CODE_RE.findall(text)
    segments.extend(FENCED_CODE_RE.findall(text))
    tokens: set[str] = set()
    for segment in segments:
        tokens.update(IDENTIFIER_RE.findall(segment))
    return tokens


def _source_refs(text: str, repo_root: Path) -> list[str]:
    refs: set[str] = set()
    for match in SOURCE_REF_RE.finditer(text):
        value = match.group(1).rstrip(".,;:")
        if any(character in value for character in "*{}"):
            continue
        candidate = repo_root / value
        if candidate.exists():
            refs.add(value)
    return sorted(refs)


def _api_leaf_paths(doc_root: Path) -> list[Path]:
    """Return only API fact leaves, never routing or overview documents."""

    return sorted(
        path
        for relative_root in API_LEAF_ROOTS
        for path in (doc_root / relative_root).rglob("*.md")
        if path.is_file() and path.name != "README.md"
    )


def _api_doc_category(doc_ref: str) -> str:
    for category in ("function_api", "material_api", "node_api"):
        if doc_ref.startswith(f"api_reference/{category}/"):
            return category
    raise IndexGenerationError(f"API document is not a leaf: {doc_ref}")


def _heading_code_tokens(text: str) -> set[str]:
    headings = "\n".join(
        line for line in text.splitlines() if line.startswith(("# ", "## ", "### "))
    )
    tokens: set[str] = set()
    for value in _inline_code_values(headings):
        candidate_text = value.strip().strip('"\'')
        if "(" in candidate_text:
            candidate_text = candidate_text.split("(", 1)[0]
        tokens.update(IDENTIFIER_RE.findall(candidate_text))
    return tokens


def _documented_interfaces(
    api_doc_paths: list[Path], doc_root: Path
) -> list[dict[str, Any]]:
    """Index heading-owned APIs that are not necessarily Python AST symbols."""

    documents_by_name: dict[str, set[str]] = defaultdict(set)
    for path in api_doc_paths:
        doc_ref = _doc_relative(path, doc_root)
        for name in _heading_code_tokens(path.read_text(encoding="utf-8")):
            documents_by_name[name].add(doc_ref)

    interfaces: list[dict[str, Any]] = []
    for name, documents in documents_by_name.items():
        ordered_documents = sorted(documents)
        category = _api_doc_category(ordered_documents[0])
        interfaces.append(
            {
                "id": f"documented:{name}",
                "name": name,
                "kind": "documented_interface",
                "aliases": [name.removeprefix("bpy.types."), name.rsplit(".", 1)[-1]]
                if name.startswith("bpy.types.")
                else [],
                "category": category,
                "document": ordered_documents[0],
                "documents": ordered_documents,
            }
        )
    return sorted(interfaces, key=lambda item: item["id"])


def _preferred_api_category(symbol: dict[str, Any]) -> str:
    roles = set(symbol.get("roles", []))
    if "node_enum" in roles or ".nodes." in symbol.get("module", ""):
        return "node_api"
    if roles.intersection(
        {"material_class", "material_function", "material_assignment"}
    ):
        return "material_api"
    return "function_api"


def _associate_api_docs(
    symbols: list[dict[str, Any]],
    api_doc_paths: list[Path],
    repo_root: Path,
    doc_root: Path,
) -> None:
    alias_to_ids: dict[str, set[str]] = defaultdict(set)
    symbol_by_id = {symbol["id"]: symbol for symbol in symbols}
    for symbol in symbols:
        aliases = {
            symbol["name"],
            symbol["qualname"],
            f"{symbol['module']}.{symbol['qualname']}",
            f"{symbol['module'].split('.')[-1]}.{symbol['qualname']}",
        }
        if symbol["kind"] == "class_attribute":
            aliases.add(symbol["qualname"])
        for alias in aliases:
            alias_to_ids[alias].add(symbol["id"])

    priorities: dict[str, dict[str, tuple[int, int, int, str]]] = defaultdict(dict)
    for doc_path in api_doc_paths:
        text = doc_path.read_text(encoding="utf-8")
        tokens = _markdown_code_tokens(text)
        heading_tokens = _heading_code_tokens(text)
        mentioned_sources = set(_source_refs(text, repo_root))
        doc_ref = _doc_relative(doc_path, doc_root)
        category = _api_doc_category(doc_ref)

        for token in tokens:
            candidates = set(alias_to_ids.get(token, set()))
            if not candidates and "." in token:
                candidates = set(alias_to_ids.get(token.split(".")[-1], set()))
            if not candidates:
                continue

            if len(candidates) > 1:
                narrowed = {
                    symbol_id
                    for symbol_id in candidates
                    if symbol_by_id[symbol_id]["source_path"] in mentioned_sources
                }
                if narrowed:
                    candidates = narrowed
            if len(candidates) > 1:
                narrowed = {
                    symbol_id
                    for symbol_id in candidates
                    if _preferred_api_category(symbol_by_id[symbol_id]) == category
                }
                if narrowed:
                    candidates = narrowed
            if len(candidates) != 1:
                continue

            symbol_id = next(iter(candidates))
            symbol = symbol_by_id[symbol_id]
            priority = (
                0 if token in heading_tokens else 1,
                0 if _preferred_api_category(symbol) == category else 1,
                0 if symbol["source_path"] in mentioned_sources else 1,
                doc_ref,
            )
            previous = priorities[symbol_id].get(doc_ref)
            if previous is None or priority < previous:
                priorities[symbol_id][doc_ref] = priority

    for symbol in symbols:
        ranked = sorted(
            priorities.get(symbol["id"], {}).items(), key=lambda item: item[1]
        )
        symbol["api_docs"] = [doc_ref for doc_ref, _ in ranked]


def _digest_files(paths: Iterable[Path], repo_root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted({item.resolve() for item in paths}, key=lambda item: item.as_posix()):
        digest.update(_repo_relative(path, repo_root).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def build_api_index(
    repo_root: Path,
    *,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    """Build the API index without importing scanned source modules."""

    repo_root = repo_root.resolve()
    doc_root = repo_root / DEFAULT_DOC_ROOT
    python_paths: list[Path] = []
    for source_root in DEFAULT_SOURCE_ROOTS:
        root = repo_root / source_root
        if not root.exists():
            raise IndexGenerationError(f"missing source root: {source_root}")
        python_paths.extend(root.rglob("*.py"))

    symbols: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for path in sorted(python_paths):
        file_symbols, file_errors = _scan_python_file(path, repo_root)
        symbols.extend(file_symbols)
        errors.extend(file_errors)

    _propagate_factory_roles(symbols)
    api_docs = _api_leaf_paths(doc_root)
    _associate_api_docs(symbols, api_docs, repo_root, doc_root)
    documented_interfaces = _documented_interfaces(api_docs, doc_root)

    for symbol in symbols:
        symbol.pop("resolved_bases", None)
        symbol["roles"] = sorted(set(symbol["roles"]))
        if not symbol["roles"]:
            symbol["roles"] = ["uncategorized"]
    symbols.sort(key=lambda item: item["id"])

    role_counts = Counter(role for symbol in symbols for role in symbol["roles"])
    kind_counts = Counter(symbol["kind"] for symbol in symbols)
    timestamp = generated_at_utc or datetime.now(timezone.utc).isoformat()
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": timestamp,
        "generator": GENERATOR_ID,
        "source_roots": list(DEFAULT_SOURCE_ROOTS),
        "api_leaf_roots": list(API_LEAF_ROOTS),
        "source_digest": _digest_files([*python_paths, *api_docs], repo_root),
        "statistics": {
            "python_file_count": len(python_paths),
            "api_leaf_document_count": len(api_docs),
            "symbol_count": len(symbols),
            "documented_interface_count": len(documented_interfaces),
            "parse_error_count": len(errors),
            "kind_counts": dict(sorted(kind_counts.items())),
            "role_counts": dict(sorted(role_counts.items())),
        },
        "parse_errors": errors,
        "documented_interfaces": documented_interfaces,
        "symbols": symbols,
    }


def _inline_code_values(value: str) -> list[str]:
    return [match.group(1).strip() for match in INLINE_CODE_RE.finditer(value)]


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def write_index(output_dir: Path, api_index: dict[str, Any]) -> Path:
    api_path = output_dir / "api_index.json"
    _write_json(api_path, api_index)
    return api_path


def _without_volatile_fields(value: dict[str, Any]) -> dict[str, Any]:
    result = dict(value)
    result.pop("generated_at_utc", None)
    return result


def index_is_current(
    output_dir: Path, api_index: dict[str, Any]
) -> tuple[bool, list[str]]:
    stale: list[str] = []
    for filename, expected in (("api_index.json", api_index),):
        path = output_dir / filename
        if not path.exists():
            stale.append(filename)
            continue
        try:
            actual = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            stale.append(filename)
            continue
        if _without_volatile_fields(actual) != _without_volatile_fields(expected):
            stale.append(filename)
    return not stale, stale


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate the AST/API index for agent asset authoring."
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=_default_repo_root(),
        help="Repository root. Defaults to the parent of the inf_agent package.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help=f"Output directory. Defaults to {DEFAULT_OUTPUT_DIR}.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Do not write files; exit non-zero if committed indexes are stale.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = args.repo_root.resolve()
    output_dir = (
        args.output_dir.resolve()
        if args.output_dir is not None
        else repo_root / DEFAULT_OUTPUT_DIR
    )
    api_index = build_api_index(repo_root)

    if args.check:
        current, stale = index_is_current(output_dir, api_index)
        if not current:
            print(f"stale indexes: {', '.join(stale)}")
            return 1
        print("indexes are current")
        return 0

    api_path = write_index(output_dir, api_index)
    print(
        f"wrote {api_path} "
        f"({api_index['statistics']['symbol_count']} symbols, "
        f"{api_index['statistics']['parse_error_count']} parse errors)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
