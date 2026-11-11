"""Executable render, geometry, time and artifact budgets."""

from __future__ import annotations

import math
import stat
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from inf_agent.workspace.contracts import write_json_atomic

RESOURCE_POLICY_SCHEMA_VERSION = "1.1"
DEFAULT_MAX_RUNS = 20


class ResourceLimitError(RuntimeError):
    """Raised before an expensive stage when a frozen resource limit is exceeded."""


@dataclass(frozen=True)
class ResourcePolicy:
    max_runs: int = DEFAULT_MAX_RUNS
    max_resolution_width: int = 2048
    max_resolution_height: int = 2048
    max_resolution_pixels: int = 4_194_304
    max_samples: int = 256
    max_objects: int = 1024
    max_evaluated_vertices: int = 2_000_000
    max_evaluated_faces: int = 4_000_000
    max_materials: int = 256
    max_build_seconds: float = 300.0
    max_artifact_bytes: int = 2 * 1024 * 1024 * 1024
    max_wall_seconds: int = 30 * 60

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            try:
                finite = (
                    math.isfinite(value) if isinstance(value, (int, float)) else False
                )
            except OverflowError:
                finite = False
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not finite
                or value <= 0
            ):
                raise ValueError(f"{name} must be a finite positive number")
            if name != "max_build_seconds" and not isinstance(value, int):
                raise ValueError(f"{name} must be an integer")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


DEFAULT_RESOURCE_POLICY = ResourcePolicy()


def validate_render_request(
    resolution: tuple[int, int],
    samples: int,
    *,
    policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY,
) -> None:
    if (
        not isinstance(resolution, tuple)
        or len(resolution) != 2
        or any(
            not isinstance(value, int) or isinstance(value, bool) or value < 16
            for value in resolution
        )
    ):
        raise ResourceLimitError("resolution must contain two integers of at least 16")
    width, height = resolution
    if (
        width > policy.max_resolution_width
        or height > policy.max_resolution_height
        or width * height > policy.max_resolution_pixels
    ):
        raise ResourceLimitError("resolution exceeds the configured render budget")
    if (
        not isinstance(samples, int)
        or isinstance(samples, bool)
        or samples < 1
        or samples > policy.max_samples
    ):
        raise ResourceLimitError(f"samples must be between 1 and {policy.max_samples}")


def _finite_nonnegative(value: Any) -> float | None:
    try:
        finite = math.isfinite(value) if isinstance(value, (int, float)) else False
    except OverflowError:
        finite = False
    if (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and finite
        and value >= 0
    ):
        return float(value)
    return None


def _evaluated_total(metrics: dict[str, Any], field: str) -> int | None:
    objects = metrics.get("objects")
    if not isinstance(objects, list):
        return None
    total = 0
    for item in objects:
        if not isinstance(item, dict):
            return None
        observed = _finite_nonnegative(item.get(field))
        if observed is None or int(observed) != observed:
            return None
        total += int(observed)
    return total


def complexity_budget_report(
    *,
    metrics: dict[str, Any],
    build_seconds: float,
    resolution: tuple[int, int],
    samples: int,
    policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY,
) -> dict[str, Any]:
    """Return the authoritative pre-render complexity decision."""

    observed = {
        "resolution_width": resolution[0],
        "resolution_height": resolution[1],
        "resolution_pixels": resolution[0] * resolution[1],
        "samples": samples,
        "objects": metrics.get("object_count", metrics.get("mesh_count")),
        "evaluated_vertices": _evaluated_total(metrics, "evaluated_vertices"),
        "evaluated_faces": _evaluated_total(metrics, "evaluated_faces"),
        "materials": metrics.get("material_count"),
        "build_seconds": build_seconds,
    }
    checks = {
        "resolution_width": observed["resolution_width"] <= policy.max_resolution_width,
        "resolution_height": observed["resolution_height"]
        <= policy.max_resolution_height,
        "resolution_pixels": observed["resolution_pixels"]
        <= policy.max_resolution_pixels,
        "samples": observed["samples"] <= policy.max_samples,
        "objects": _finite_nonnegative(observed["objects"]) is not None
        and observed["objects"] <= policy.max_objects,
        "evaluated_vertices": observed["evaluated_vertices"] is not None
        and observed["evaluated_vertices"] <= policy.max_evaluated_vertices,
        "evaluated_faces": observed["evaluated_faces"] is not None
        and observed["evaluated_faces"] <= policy.max_evaluated_faces,
        "materials": _finite_nonnegative(observed["materials"]) is not None
        and observed["materials"] <= policy.max_materials,
        "build_seconds": _finite_nonnegative(build_seconds) is not None
        and build_seconds <= policy.max_build_seconds,
    }
    failures = [name for name, passed in checks.items() if not passed]
    return {
        "schema_version": RESOURCE_POLICY_SCHEMA_VERSION,
        "gate": "PRE_MULTI_VIEW_RENDER",
        "allowed": not failures,
        "limits": policy.to_dict(),
        "observed": observed,
        "checks": checks,
        "failed_limits": failures,
        "artifact_bytes": None,
    }


def directory_bytes(path: Path) -> int:
    total = 0
    if not path.exists():
        return total
    for item in path.rglob("*"):
        try:
            details = item.stat()
        except OSError:
            # Windows may briefly deny metadata access while Blender inherits an
            # actively written process log.  The watchdog polls again after
            # 100 ms, so skipping only that transient sample avoids turning a
            # healthy render into a framework failure without disabling quota
            # enforcement for the remaining artifacts.
            continue
        if stat.S_ISREG(details.st_mode):
            total += details.st_size
    return total


def write_budget_report(output_dir: Path, report: dict[str, Any]) -> Path:
    destination = output_dir / "resource_budget.json"
    write_json_atomic(destination, report)
    return destination


def write_build_started_report(
    *,
    output_dir: Path,
    resolution: tuple[int, int],
    samples: int,
    policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY,
) -> dict[str, Any]:
    report = {
        "schema_version": RESOURCE_POLICY_SCHEMA_VERSION,
        "gate": "BUILD_IN_PROGRESS",
        "allowed": None,
        "limits": policy.to_dict(),
        "observed": {
            "resolution_width": resolution[0],
            "resolution_height": resolution[1],
            "resolution_pixels": resolution[0] * resolution[1],
            "samples": samples,
        },
        "checks": {},
        "failed_limits": [],
        "artifact_bytes": None,
    }
    write_budget_report(output_dir, report)
    return report


def enforce_complexity_budget(
    *,
    output_dir: Path,
    metrics: dict[str, Any],
    build_seconds: float,
    resolution: tuple[int, int],
    samples: int,
    policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY,
) -> dict[str, Any]:
    report = complexity_budget_report(
        metrics=metrics,
        build_seconds=build_seconds,
        resolution=resolution,
        samples=samples,
        policy=policy,
    )
    write_budget_report(output_dir, report)
    if not report["allowed"]:
        raise ResourceLimitError(
            "pre-render resource budget exceeded: " + ", ".join(report["failed_limits"])
        )
    return report


def enforce_artifact_budget(
    output_dir: Path,
    report: dict[str, Any],
    *,
    policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY,
) -> None:
    observed = directory_bytes(output_dir)
    report["artifact_bytes"] = observed
    write_budget_report(output_dir, report)
    if observed > policy.max_artifact_bytes:
        report["allowed"] = False
        if "artifact_bytes" not in report["failed_limits"]:
            report["failed_limits"].append("artifact_bytes")
        write_budget_report(output_dir, report)
        raise ResourceLimitError("artifact bytes exceed the configured disk budget")
