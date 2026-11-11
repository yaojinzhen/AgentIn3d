"""Measurable dimensions and proportions; visual likeness is assessed from images."""

import math
from typing import Any


def evaluate_proportions(
    asset_spec: dict[str, Any] | None, bbox: dict[str, Any]
) -> dict[str, Any]:
    """Measure only named absolute dimensions and stable bbox ratios."""

    ranges = (
        asset_spec.get("expected_bbox_or_ratio_ranges", {})
        if isinstance(asset_spec, dict)
        else {}
    )
    measured: dict[str, float | None] = {}
    checks: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    width, depth, height = (bbox.get(name) for name in ("width", "depth", "height"))
    dimensions = (width, depth, height)
    finite = all(
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and float(value) > 0
        for value in dimensions
    )
    if finite:
        measured = {
            "width_m": float(width),
            "depth_m": float(depth),
            "height_m": float(height),
            "width_to_height": float(width) / float(height),
            "depth_to_height": float(depth) / float(height),
            "width_to_depth": float(width) / float(depth),
        }
    for name, bounds in ranges.items():
        value = measured.get(name)
        passed = value is not None and float(bounds[0]) <= value <= float(bounds[1])
        checks[name] = {
            "observed": value,
            "minimum": bounds[0],
            "maximum": bounds[1],
            "passed": passed,
        }
        if not passed:
            errors.append(
                f"AssetSpec proportion {name} is outside [{bounds[0]}, {bounds[1]}]"
            )
    return {"passed": not errors, "checks": checks, "errors": errors}
