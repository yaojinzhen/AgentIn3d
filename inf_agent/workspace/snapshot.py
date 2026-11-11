"""Explicit local file snapshots with stable paths relative to asset.py."""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import shutil
from inf_agent.workspace.contracts import ContractError
from inf_agent.workspace.input_validation import (
    ValidatedImage,
    validate_reference_image,
)


def normalize_local_dependencies(value):
    if not isinstance(value, list) or any(
        not isinstance(p, str) or not p.strip() for p in value
    ):
        raise ContractError(
            "request.local_dependencies: expected relative file/directory strings"
        )
    result = []
    for text in value:
        path = Path(text)
        if (
            path.is_absolute()
            or path.drive
            or ".." in path.parts
            or not path.parts
            or path.parts[0].casefold() == "runs"
        ):
            raise ContractError(
                f"local dependency must be a workspace-relative file/directory outside runs: {text}"
            )
        normalized = path.as_posix()
        if normalized not in result:
            result.append(normalized)
    return result


@dataclass
class SnapshotPlan:
    files: dict[Path, Path]
    reference: ValidatedImage | None
    design: Path | None


def prepare_snapshot(workspace: Path, request: dict) -> SnapshotPlan:
    """Validate the selected file tree before allocating a run; never scan runs."""
    workspace = workspace.resolve()
    files = {}

    def add(relative, ancestors=frozenset()):
        path = workspace / relative
        try:
            resolved = path.resolve(strict=True)
        except (OSError, RuntimeError) as error:
            raise ContractError(
                f"local dependency is unavailable: {relative}: {error}"
            ) from error
        if not resolved.is_relative_to(workspace) or resolved.is_relative_to(
            workspace / "runs"
        ):
            raise ContractError(
                f"local dependency resolves outside workspace inputs: {relative}"
            )
        if resolved.is_dir():
            if resolved in ancestors:
                raise ContractError(f"local dependency directory cycle: {relative}")
            for child in sorted(resolved.iterdir()):
                if child.name != "__pycache__" and child.suffix != ".pyc":
                    add(relative / child.name, ancestors | {resolved})
        elif resolved.is_file():
            files[relative] = resolved
        else:
            raise ContractError(
                f"local dependency is not a regular file/directory: {relative}"
            )

    add(Path("asset.py"))
    for text in normalize_local_dependencies(request.get("local_dependencies", [])):
        add(Path(text))
    reference_path = request.get("reference_image")
    reference = (
        validate_reference_image(workspace / reference_path) if reference_path else None
    )
    design = workspace / "design.md"
    if design.exists() and not design.is_file():
        raise ContractError("design.md must be a file when present")
    return SnapshotPlan(files, reference, design if design.is_file() else None)


def write_snapshot(
    plan: SnapshotPlan, inputs: Path, request: dict
) -> tuple[Path, dict, dict]:
    source_root = inputs / "source"
    source_root.mkdir(parents=True)
    for relative, original in plan.files.items():
        destination = source_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original, destination)
    request = dict(request)
    if plan.reference is not None:
        image = inputs / ("reference" + plan.reference.suffix)
        image.write_bytes(plan.reference.payload)
        request["reference_image"] = image.as_posix()
    if plan.design is not None:
        shutil.copy2(plan.design, inputs / "design.md")
    context = dict(
        mode="explicit_local_snapshot",
        source_root=source_root.as_posix(),
        files=sorted(p.as_posix() for p in plan.files),
        external_dependencies="current_python_environment",
    )
    return source_root / "asset.py", request, context
