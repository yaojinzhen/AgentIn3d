"""Single fact source for execution and objective asset health.

This module deliberately does not decide visual fidelity.  It validates only
facts that Python can measure reliably and returns a bounded report consumed by
independent preview/export runs.
"""

from __future__ import annotations

import math
import re
import struct
from pathlib import Path
from typing import Any, Iterable, Literal

from PIL import Image

from inf_agent.geometry.validation import evaluate_geometry_contract
from inf_agent.quality import evaluate_proportions
from inf_agent.execution.view_plan import (
    planned_focus_views,
    expected_outputs as plan_outputs,
)

HEALTH_SCHEMA_VERSION = "1.1"
VALIDATION_SOURCE = "inf_agent.asset_health.v1"
HealthMode = Literal["preview", "final"]
DIMENSION_TOLERANCE = 0.15
MAX_NON_MANIFOLD_RATIO = 0.05
MAX_ZERO_AREA_RATIO = 0.01
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
BLEND_SIGNATURE = b"BLENDER"
GLB_SIGNATURE = b"glTF"
ARTIFACT_MINIMUM_BYTES = {
    "preview_png": 24,
    "asset_glb": 12,
    "scene_blend": 12,
}
CHROMATIC_WORDS = re.compile(
    r"\b(?:brown|red|blue|green|yellow|orange|purple|pink|gold|copper)\b"
    r"|棕|褐|红|蓝|绿|黄|橙|紫|粉|金|铜",
    re.IGNORECASE,
)


def _chromatic_render_check(
    asset_spec: dict[str, Any] | None,
    output_dir: Path,
    metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Detect the narrow case of a requested colored primary body rendering gray."""

    result: dict[str, Any] = {
        "required": False,
        "measured": False,
        "passed": True,
        "colored_fraction": None,
        "brown_top_fraction": None,
    }
    if not isinstance(asset_spec, dict):
        return result
    primary_ids = {
        part.get("part_id")
        for part in asset_spec.get("required_parts", [])
        if part.get("role") in {"primary_shell", "body", "primary"}
    }
    if not primary_ids:
        return result
    regions = asset_spec.get("material_regions", [])
    expected = any(
        primary_ids.intersection(region.get("part_ids", []))
        and CHROMATIC_WORDS.search(str(region.get("semantics", "")))
        for region in regions
    )
    if not expected:
        return result
    result["required"] = True
    focus_id = "focus_01"
    if metrics is not None:
        focus_views = metrics.get("focus_views", [])
        selected = next(
            (
                item
                for item in focus_views
                if primary_ids.intersection(item.get("target_part_ids", []))
            ),
            None,
        )
        if (
            selected is None
            and len(focus_views) == 1
            and not focus_views[0].get("target_part_ids")
        ):
            selected = focus_views[0]
        if selected is None:
            return result
        focus_id = selected["id"]
    preview = output_dir / "previews" / f"{focus_id}.png"
    mask = output_dir / "previews" / f"{focus_id}_mask_visible.png"
    if not preview.is_file() or not mask.is_file():
        return result
    try:
        with Image.open(preview) as source, Image.open(mask) as mask_source:
            rgb = source.convert("RGB")
            grayscale = mask_source.convert("L")
            if rgb.size != grayscale.size:
                return result
            foreground = colored = 0
            for pixel, mask_value in zip(rgb.getdata(), grayscale.getdata()):
                if mask_value < 128:
                    continue
                foreground += 1
                maximum = max(pixel)
                if maximum >= 24 and (maximum - min(pixel)) / maximum >= 0.12:
                    colored += 1
    except (OSError, ValueError):
        return result
    if foreground < 64:
        return result
    fraction = colored / foreground
    result.update(
        measured=True,
        colored_fraction=round(fraction, 6),
        passed=fraction >= 0.02,
    )
    return result


def _focus_plan_check(
    asset_spec: dict[str, Any] | None, metrics: dict[str, Any]
) -> dict[str, Any]:
    """Require a distinct part-targeted focus for each declared focus claim."""

    planned = planned_focus_views(asset_spec)
    observed = {
        item["id"]: frozenset(item.get("target_part_ids", []))
        for item in metrics.get("focus_views", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    missing = [
        item["view_id"]
        for item in planned
        if observed.get(item["view_id"]) != frozenset(item.get("target_part_ids", []))
    ]
    return {
        "required": [item["view_id"] for item in planned],
        "missing": missing,
        "passed": not missing,
    }


def inspect_artifact(path: Path, *, kind: str, requested: bool) -> dict[str, Any]:
    """Inspect one Blender-owned artifact without importing Blender."""

    if kind not in ARTIFACT_MINIMUM_BYTES:
        raise ValueError(f"unsupported artifact kind: {kind}")
    exists = path.is_file()
    size = path.stat().st_size if exists else 0
    header_valid: bool | None = None
    detail: str | None = None
    if exists:
        try:
            with path.open("rb") as stream:
                header = stream.read(12)
            if kind == "preview_png":
                header_valid = header.startswith(PNG_SIGNATURE)
            elif kind == "scene_blend":
                header_valid = header.startswith(BLEND_SIGNATURE)
            elif len(header) == 12:
                magic, version, declared_size = struct.unpack("<4sII", header)
                header_valid = (
                    magic == GLB_SIGNATURE and version == 2 and declared_size == size
                )
            else:
                header_valid = False
            if not header_valid:
                detail = f"{kind} has an invalid file header"
        except OSError as error:
            header_valid = False
            detail = f"cannot read {kind}: {error}"
    elif requested:
        detail = f"{kind} is missing"
    minimum = ARTIFACT_MINIMUM_BYTES[kind]
    if exists and size < minimum:
        detail = f"{kind} is too small: {size} bytes, expected at least {minimum}"
    valid = exists and size >= minimum and header_valid is True
    return {
        "requested": requested,
        "path": path.as_posix(),
        "exists": exists,
        "bytes": size,
        "minimum_bytes": minimum,
        "header_valid": header_valid,
        "valid": valid if requested else None,
        "detail": detail,
    }


def _finite_positive(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and float(value) > 1e-6
    )


def _artifact_checks(output_dir: Path, outputs: list[dict[str, Any]]) -> dict[str, Any]:
    kinds = {
        "png": "preview_png",
        "mask": "preview_png",
        "blend": "scene_blend",
        "glb": "asset_glb",
    }
    return {
        item["id"]: inspect_artifact(
            output_dir / item["path"], kind=kinds[item["kind"]], requested=True
        )
        for item in outputs
    }


def _requires_connected_asset(request: dict[str, Any]) -> bool:
    text = " ".join(str(item).casefold() for item in request.get("forbidden_items", []))
    return any(
        token in text
        for token in (
            "floating",
            "detached",
            "separated",
            "悬空",
            "分离",
            "未连接",
        )
    )


def _dimension_checks(
    request: dict[str, Any], bbox: dict[str, Any]
) -> tuple[dict[str, Any], list[str]]:
    checks: dict[str, Any] = {}
    errors: list[str] = []
    for name, expected in request.get("explicit_dimensions_m", {}).items():
        observed = bbox.get(name)
        valid = _finite_positive(expected) and _finite_positive(observed)
        relative_error = (
            abs(float(observed) - float(expected)) / float(expected) if valid else None
        )
        passed = valid and relative_error <= DIMENSION_TOLERANCE
        checks[name] = {
            "expected_m": expected,
            "observed_m": observed,
            "relative_error": relative_error,
            "tolerance": DIMENSION_TOLERANCE,
            "passed": passed,
        }
        if not passed:
            errors.append(f"explicit {name} is outside the 15% tolerance")
    return checks, errors


def _topology_check(
    metrics: dict[str, Any],
) -> tuple[dict[str, Any], list[str], list[str]]:
    objects = metrics.get("objects")
    if not isinstance(objects, list):
        return (
            {
                "available": False,
                "passed": False,
                "reason": "the current contract requires per-object topology metrics",
            },
            ["per-object topology metrics are unavailable"],
            [],
        )
    edges = sum(max(0, int(item.get("evaluated_edges", 0))) for item in objects)
    faces = sum(max(0, int(item.get("evaluated_faces", 0))) for item in objects)
    non_manifold = sum(
        max(0, int(item.get("non_manifold_edges", 0))) for item in objects
    )
    zero_area = sum(max(0, int(item.get("zero_area_faces", 0))) for item in objects)
    loose = sum(max(0, int(item.get("loose_vertices", 0))) for item in objects)
    non_manifold_ratio = non_manifold / max(1, edges)
    zero_area_ratio = zero_area / max(1, faces)
    passed = (
        faces > 0
        and loose == 0
        and non_manifold_ratio <= MAX_NON_MANIFOLD_RATIO
        and zero_area_ratio <= MAX_ZERO_AREA_RATIO
    )
    errors = []
    if faces <= 0:
        errors.append("evaluated meshes contain no faces")
    if loose:
        errors.append(f"evaluated meshes contain {loose} loose vertices")
    if non_manifold_ratio > MAX_NON_MANIFOLD_RATIO:
        errors.append("severe non-manifold edge ratio exceeds 5%")
    if zero_area_ratio > MAX_ZERO_AREA_RATIO:
        errors.append("severe zero-area face ratio exceeds 1%")
    p99 = max(
        (float(item.get("face_aspect_p99", 0.0)) for item in objects),
        default=0.0,
    )
    warnings = (
        [f"face aspect P99 is high ({p99:.2f}); inspect the affected object"]
        if p99 > 200.0
        else []
    )
    return (
        {
            "available": True,
            "evaluated_edges": edges,
            "evaluated_faces": faces,
            "non_manifold_edges": non_manifold,
            "non_manifold_ratio": non_manifold_ratio,
            "zero_area_faces": zero_area,
            "zero_area_ratio": zero_area_ratio,
            "loose_vertices": loose,
            "maximum_object_face_aspect_p99": p99,
            "passed": passed,
        },
        errors,
        warnings,
    )


def _material_check(metrics: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    missing = metrics.get("unmaterialized_meshes", [])
    uncovered = metrics.get("uncovered_material_faces", 0)
    if not isinstance(missing, list):
        missing = []
    if not isinstance(uncovered, int) or isinstance(uncovered, bool):
        uncovered = 0
    passed = metrics.get("material_count", 0) > 0 and not missing and uncovered == 0
    errors = []
    if metrics.get("material_count", 0) <= 0:
        errors.append("asset has no assigned material")
    if missing:
        errors.append(
            "visible meshes without material: " + ", ".join(map(str, missing[:8]))
        )
    if uncovered:
        errors.append(f"{uncovered} evaluated faces have no assigned material")
    return {
        "material_count": metrics.get("material_count", 0),
        "unmaterialized_meshes": missing,
        "uncovered_faces": uncovered,
        "passed": passed,
    }, errors


def _log_has_traceback(path: Path) -> bool:
    marker = "\nTraceback (most recent call last):"
    tail = "\n"
    with path.open("r", encoding="utf-8", errors="replace") as stream:
        while block := stream.read(64 * 1024):
            text = tail + block
            if marker in text:
                return True
            tail = text[-(len(marker) - 1) :]
    return False


def evaluate_asset_health(
    *,
    metrics: dict[str, Any],
    output_dir: Path,
    request: dict[str, Any],
    asset_spec: dict[str, Any] | None = None,
    part_manifest: dict[str, Any] | None = None,
    mode: HealthMode,
    execution_ok: bool,
    execution_errors: Iterable[str] = (),
    execution_warnings: Iterable[str] = (),
    render: bool = True,
    save_blend: bool = True,
    export_glb: bool | None = None,
    expected_outputs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Evaluate execution and objective health without claiming visual quality."""

    errors = [str(item) for item in execution_errors]
    warnings = [str(item) for item in execution_warnings]
    run_log = output_dir / "run.log"
    run_log_exists = run_log.is_file() and run_log.stat().st_size > 0
    no_traceback = False
    if run_log_exists:
        no_traceback = not _log_has_traceback(run_log)
    execution_passed = execution_ok and run_log_exists and no_traceback
    if not run_log_exists:
        errors.append("run.log is missing or empty")
    elif not no_traceback:
        errors.append("run.log contains a traceback")

    bbox = metrics.get("bbox") if isinstance(metrics.get("bbox"), dict) else {}
    bbox_nonzero_finite = all(
        _finite_positive(bbox.get(name)) for name in ("width", "depth", "height")
    )
    mesh_present = (
        isinstance(metrics.get("mesh_count"), int)
        and metrics.get("mesh_count", 0) > 0
        and isinstance(metrics.get("vertex_count"), int)
        and metrics.get("vertex_count", 0) >= 3
    )
    if not mesh_present:
        errors.append("asset has no usable visible mesh")
    if not bbox_nonzero_finite:
        errors.append("asset bbox is empty or contains non-finite dimensions")

    dimensions, dimension_errors = _dimension_checks(request, bbox)
    errors.extend(dimension_errors)
    proportions = evaluate_proportions(asset_spec, bbox)
    errors.extend(proportions["errors"])
    topology, topology_errors, topology_warnings = _topology_check(metrics)
    errors.extend(topology_errors)
    warnings.extend(topology_warnings)
    material, material_errors = _material_check(metrics)
    errors.extend(material_errors)
    chromatic_render = (
        _chromatic_render_check(asset_spec, output_dir, metrics)
        if render
        else {"required": False, "measured": False, "passed": True}
    )
    if chromatic_render["measured"] and not chromatic_render["passed"]:
        warnings.append(
            "colored primary material appears nearly achromatic; inspect the rendered image"
        )
    focus_plan = (
        _focus_plan_check(asset_spec, metrics)
        if render
        else {"required": [], "missing": [], "passed": True}
    )
    if not focus_plan["passed"]:
        errors.append(
            "declared part-focus views have no matching isolated part evidence: "
            + ", ".join(focus_plan["missing"])
        )

    structural = metrics.get("structural")
    connected = (
        structural.get("connected")
        if isinstance(structural, dict)
        and isinstance(structural.get("connected"), bool)
        else None
    )
    connectivity_required = _requires_connected_asset(request)
    connectivity_passed = connected is not False or not connectivity_required
    if connected is False:
        detail = ", ".join(
            str(item) for item in structural.get("isolated_objects", [])[:8]
        )
        message = "mesh-aware contact graph reports separated components"
        if detail:
            message += f": {detail}"
        if connectivity_required:
            errors.append(message)
        else:
            warnings.append(message)

    geometry = evaluate_geometry_contract(
        asset_spec=asset_spec,
        part_manifest=part_manifest,
        metrics=metrics,
    )
    errors.extend(geometry["errors"])
    warnings.extend(geometry["warnings"])

    outputs = (
        expected_outputs
        if expected_outputs is not None
        else plan_outputs(
            asset_spec or {},
            metrics,
            render=render,
            save_blend=save_blend,
            export_glb=(mode == "final") if export_glb is None else export_glb,
        )
    )
    artifacts = _artifact_checks(output_dir, outputs)
    artifacts_passed = all(
        item["valid"] is True for item in artifacts.values() if item["requested"]
    )
    if not artifacts_passed:
        errors.append(f"required {mode} artifacts are missing or invalid")

    objective_passed = all(
        (
            mesh_present,
            bbox_nonzero_finite,
            all(item["passed"] for item in dimensions.values()),
            proportions["passed"],
            topology["passed"],
            material["passed"],
            focus_plan["passed"],
            connectivity_passed,
            geometry["passed"],
            artifacts_passed,
        )
    )
    success = execution_passed and objective_passed
    return {
        "schema_version": HEALTH_SCHEMA_VERSION,
        "validation_source": VALIDATION_SOURCE,
        "mode": mode,
        "success": success,
        "layers": {
            "execution_health": {
                "passed": execution_passed,
                "run_log_exists": run_log_exists,
                "no_traceback": no_traceback,
            },
            "objective_asset_health": {
                "passed": objective_passed,
                "mesh_present": mesh_present,
                "bbox_nonzero_finite": bbox_nonzero_finite,
                "explicit_dimensions": dimensions,
                "asset_spec_proportions": proportions,
                "topology": topology,
                "materials": material,
                "chromatic_render": chromatic_render,
                "focus_plan": focus_plan,
                "connectivity": {
                    "required": connectivity_required,
                    "connected": connected,
                    "passed": connectivity_passed,
                    "measurement": structural,
                },
                "artifacts": artifacts,
            },
            "geometry_and_assembly": geometry,
            "visual_fidelity": {
                "machine_decision": None,
                "status": "NOT_CHECKED",
            },
        },
        "errors": list(dict.fromkeys(errors)),
        "warnings": list(dict.fromkeys(warnings)),
    }
