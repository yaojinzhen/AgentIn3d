"""Explicit workspace creation and isolated runs, without global task state."""

from __future__ import annotations

import shutil
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from inf_agent.execution.resource_policy import DEFAULT_MAX_RUNS, ResourceLimitError
from inf_agent.workspace.contracts import (
    SCHEMA_VERSION,
    ContractError,
    load_json,
    normalize_design,
    write_json_atomic,
)
from inf_agent.workspace.input_validation import (
    normalize_dimensions,
    normalize_request_text,
    validate_reference_image,
)


class _DestinationExistsError(FileExistsError):
    pass


def _publish_by_copy(staging: Path, workspace: Path) -> None:
    """Portable no-overwrite fallback, keeping a complete staging copy on failure."""
    try:
        workspace.mkdir()
    except FileExistsError as error:
        raise _DestinationExistsError(str(workspace)) from error
    owned = []
    try:
        for source in staging.iterdir():
            target = workspace / source.name
            with target.open("xb") as destination:
                owned.append(target)
                with source.open("rb") as stream:
                    shutil.copyfileobj(stream, destination)
    except BaseException:
        # Only remove files this call created; an unknown added file keeps the
        # directory non-empty, so rmdir preserves it and staging remains usable.
        for target in reversed(owned):
            try:
                target.unlink()
            except OSError:
                pass
        try:
            workspace.rmdir()
        except OSError:
            pass
        raise


def _publish_workspace(staging: Path, workspace: Path) -> None:
    if sys.platform == "win32":
        # Windows rename fails for every existing destination, including an
        # empty directory. The complete folder becomes visible in one step.
        try:
            staging.rename(workspace)
        except FileExistsError as error:
            raise _DestinationExistsError(str(workspace)) from error
    else:
        # POSIX rename can replace an existing empty directory, so use an
        # exclusive mkdir and owned-file rollback instead.
        _publish_by_copy(staging, workspace)


def create_workspace(
    workspace: Path | str,
    *,
    prompt: str,
    image: Path | str | None = None,
    dimensions: dict | None = None,
    forbidden: list[str] | None = None,
) -> dict[str, Any]:
    workspace = Path(workspace).resolve()
    prompt, forbidden = normalize_request_text(prompt, forbidden or [])
    dimensions = normalize_dimensions(dimensions)
    reference = validate_reference_image(Path(image)) if image else None
    record = {
        "schema_version": SCHEMA_VERSION,
        "prompt": prompt,
        "explicit_dimensions_m": dimensions,
        "forbidden_items": forbidden,
        "reference_image": f"reference{reference.suffix}" if reference else None,
        "local_dependencies": [],
    }
    workspace.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{workspace.name}_create_", dir=workspace.parent)
    )
    complete = False
    published = False
    collision = False
    try:
        write_json_atomic(staging / "request.json", record)
        (staging / "asset.py").write_text(
            'from infinigen.core.placement.factory import AssetFactory\n\n\nclass GeneratedFactory(AssetFactory):\n    def create_asset(self, **params):\n        raise NotImplementedError("Implement the requested geometry and materials")\n',
            encoding="utf-8",
        )
        if reference:
            (staging / record["reference_image"]).write_bytes(reference.payload)
        complete = True
        _publish_workspace(staging, workspace)
        published = True
    except _DestinationExistsError as error:
        collision = True
        # A competing start or a pre-existing user directory is never changed.
        raise ContractError(
            f"workspace already exists; edit it or choose a new directory: {workspace}"
        ) from error
    except OSError as error:
        recovery = f"; complete staging preserved at {staging}" if complete else ""
        raise ContractError(
            f"cannot create workspace {workspace}: {error}{recovery}"
        ) from error
    except BaseException as error:
        if complete:
            error.add_note(f"Complete staging preserved at {staging}")
        raise
    finally:
        if staging.exists() and (not complete or published or collision):
            resolved = staging.resolve()
            if (
                resolved.parent != workspace.parent
                or resolved.name != staging.name
                or not staging.name.startswith(f".{workspace.name}_create_")
            ):
                raise ContractError("unexpected staging cleanup target")
            shutil.rmtree(resolved)
    return {
        "workspace": workspace.as_posix(),
        "request": record,
        "source": (workspace / "asset.py").as_posix(),
    }


def read_workspace(workspace: Path | str) -> tuple[Path, dict, dict]:
    workspace = Path(workspace).resolve()
    from inf_agent.workspace.run_input import normalize_request

    request = normalize_request(load_json(workspace / "request.json"))
    design_path = workspace / "design.json"
    design = normalize_design(load_json(design_path) if design_path.exists() else {})
    return workspace, request, design


def allocate_run(workspace: Path, *, max_runs: int = DEFAULT_MAX_RUNS) -> Path:
    runs = workspace / "runs"
    if isinstance(max_runs, bool) or not isinstance(max_runs, int) or max_runs < 1:
        raise ContractError("max_runs must be a positive integer")
    runs.mkdir(exist_ok=True)

    def used():
        return sum(path.is_dir() for path in runs.iterdir())

    def exhausted():
        return ResourceLimitError(
            f"workspace run limit reached ({max_runs}); preview/export consume runs, "
            "including failed runs. Inspect existing results or explicitly raise "
            "max_runs with --limits; no existing run was overwritten."
        )

    if used() >= max_runs:
        raise exhausted()
    name = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%f")
        + "_"
        + uuid.uuid4().hex[:8]
    )
    path = runs / name
    path.mkdir()
    # Recheck concurrent allocations without locks; only our own still-empty
    # directory can be rolled back. Existing runs and evidence are preserved.
    if used() > max_runs:
        path.rmdir()
        raise exhausted()
    return path


def workspace_status(workspace: Path | str) -> dict[str, Any]:
    workspace, request, design = read_workspace(workspace)
    runs_dir = workspace / "runs"
    runs = (
        sorted(p for p in runs_dir.iterdir() if p.is_dir()) if runs_dir.exists() else []
    )
    latest = runs[-1] if runs else None
    return {
        "workspace": workspace.as_posix(),
        "source": (workspace / "asset.py").as_posix(),
        "request": request,
        "design": design,
        "run_count": len(runs),
        "run_budget": {
            "default_limit": DEFAULT_MAX_RUNS,
            "used": len(runs),
            "remaining_at_default": max(0, DEFAULT_MAX_RUNS - len(runs)),
        },
        "latest_run": latest.as_posix() if latest else None,
        "latest_result": load_json(latest / "result.json")
        if latest and (latest / "result.json").is_file()
        else None,
    }
