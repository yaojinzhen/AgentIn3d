"""Small JSON persistence and optional geometric design validation."""

from __future__ import annotations

import json
import copy
import math
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "2"
PRODUCT_VERSION = "1.1"
ASSET_OUTPUTS_ROOT = Path("inf_agent/outputs")
GLOBAL_REVIEW_VIEW_IDS = frozenset(
    {"perspective", "front", "side", "top", "opposite_perspective", "bottom"}
)
AXES = {"+X", "-X", "+Y", "-Y", "+Z", "-Z"}


class ContractError(ValueError):
    """Invalid user input or unreadable execution data."""


def load_json(path: Path | str) -> dict[str, Any]:
    path = Path(path)
    try:
        data = json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=lambda x: (_ for _ in ()).throw(
                ValueError(f"non-finite number: {x}")
            ),
        )
        if not isinstance(data, dict):
            raise ValueError("expected a JSON object")
        _finite(data, str(path))
        return data
    except (OSError, UnicodeError, ValueError) as error:
        raise ContractError(f"cannot read {path}: {error}") from error


def write_json_atomic(path: Path | str, data: dict[str, Any]) -> None:
    path = Path(path)
    temporary = None
    try:
        payload = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        for attempt in range(8):
            try:
                os.replace(temporary, path)
                break
            except PermissionError as error:
                if os.name != "nt" or error.winerror not in {5, 32} or attempt == 7:
                    raise
                time.sleep(0.01 * (attempt + 1))
    except (OSError, ValueError, TypeError) as error:
        raise ContractError(f"cannot write {path}: {error}") from error
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _finite(value: Any, label: str) -> None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            finite = math.isfinite(value)
        except OverflowError:
            finite = False
        if not finite:
            raise ContractError(f"{label}: numbers must be finite")
    if isinstance(value, dict):
        for key, item in value.items():
            _finite(item, f"{label}.{key}")
    elif isinstance(value, list):
        for i, item in enumerate(value):
            _finite(item, f"{label}[{i}]")


def _id(value: Any, label: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", value):
        raise ContractError(
            f"{label}: expected a lowercase part/view identifier with digits or underscores"
        )
    return value


def validate_asset_id(value: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_-]*", value):
        raise ContractError("asset_id must use letters, digits, underscores or hyphens")


def _is_finite_number(value: Any) -> bool:
    try:
        return math.isfinite(value)
    except (OverflowError, TypeError):
        return False


def _number(value: Any, label: str, *, minimum: float = 0) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not _is_finite_number(value)
        or value < minimum
    ):
        raise ContractError(f"{label}: expected a finite number >= {minimum}")
    return float(value)


def _records(data: dict, key: str, identity: str) -> list[dict]:
    values = data.get(key, [])
    if not isinstance(values, list) or any(
        not isinstance(item, dict) for item in values
    ):
        raise ContractError(f"{key}: expected a list of objects")
    seen = set()
    for item in values:
        value = _id(item.get(identity), f"{key}.{identity}")
        if value in seen:
            raise ContractError(f"{key}: duplicate {identity}: {value}")
        seen.add(value)
    return values


def normalize_design(value: dict[str, Any] | None) -> dict[str, Any]:
    """Validate only geometry that was declared; no provenance or route protocol."""
    if value is not None and not isinstance(value, dict):
        raise ContractError("design: expected an object")
    data = copy.deepcopy({} if value is None else value)
    _finite(data, "design")
    defaults = {
        "front_axis": "-Y",
        "up_axis": "+Z",
        "required_parts": [],
        "attachment_constraints": [],
        "required_openings_or_negative_spaces": [],
        "geometry_exemptions": [],
        "material_regions": [],
        "review_view_plan": [],
        "expected_bbox_or_ratio_ranges": {},
    }
    for key, default in defaults.items():
        data.setdefault(key, default)
    front, up = data["front_axis"], data["up_axis"]
    if (
        not isinstance(front, str)
        or not isinstance(up, str)
        or front not in AXES
        or up not in AXES
        or front[-1] == up[-1]
    ):
        raise ContractError(
            "front_axis and up_axis must be orthogonal signed cardinal axes"
        )
    parts = _records(data, "required_parts", "part_id")
    ids = {item["part_id"] for item in parts}
    for part in parts:
        low = part.setdefault("minimum_count", 1)
        high = part.setdefault("maximum_count", low)
        if (
            any(isinstance(n, bool) or not isinstance(n, int) for n in (low, high))
            or low < 1
            or high < low
        ):
            raise ContractError(
                "required_parts: counts must be positive integers with minimum <= maximum"
            )
        parent = part.get("parent_part_id")
        if parent is not None and (
            not isinstance(parent, str)
            or parent not in ids
            or parent == part["part_id"]
        ):
            raise ContractError(
                "required_parts: parent_part_id must refer to another declared part"
            )
        if "role" in part and not isinstance(part["role"], str):
            raise ContractError("required_parts.role: expected a string")
        part.setdefault("exemptions", [])
        if not isinstance(part["exemptions"], list) or any(
            not isinstance(x, str) for x in part["exemptions"]
        ):
            raise ContractError("required_parts.exemptions: expected strings")
    parents = {p["part_id"]: p.get("parent_part_id") for p in parts}
    for part_id in ids:
        seen = set()
        current = part_id
        while current is not None:
            if current in seen:
                raise ContractError("required_parts: parent cycle")
            seen.add(current)
            current = parents[current]
    attachments = _records(data, "attachment_constraints", "attachment_id")
    for item in attachments:
        if (
            not isinstance(item.get("part_id"), str)
            or not isinstance(item.get("parent_part_id"), str)
            or item.get("part_id") not in ids
            or item.get("parent_part_id") not in ids
            or item["part_id"] == item["parent_part_id"]
        ):
            raise ContractError(
                "attachment_constraints: child and parent must be distinct declared parts"
            )
        item.setdefault("kind", "contact")
        if not isinstance(item["kind"], str) or item["kind"] not in {
            "contact",
            "welded",
            "hinged",
            "inserted",
            "spaced",
        }:
            raise ContractError("attachment_constraints.kind is unsupported")
        if "require_anchors" in item and not isinstance(item["require_anchors"], bool):
            raise ContractError(
                "attachment_constraints.require_anchors: expected a bool"
            )
        if item["kind"] == "spaced":
            low = _number(item.get("minimum_gap_m"), "minimum_gap_m")
            high = _number(item.get("maximum_gap_m"), "maximum_gap_m")
            if high < low:
                raise ContractError(
                    "spaced attachment requires minimum_gap_m <= maximum_gap_m"
                )
    for item in _records(data, "required_openings_or_negative_spaces", "feature_id"):
        if (
            not isinstance(item.get("owner_part_id"), str)
            or item.get("owner_part_id") not in ids
        ):
            raise ContractError("opening owner_part_id must be a declared part")
        item.setdefault("kind", "through_opening")
        if item["kind"] not in ("through_opening", "cavity_entrance"):
            raise ContractError(
                "opening kind must be through_opening or cavity_entrance"
            )
    for item in _records(data, "material_regions", "region_id"):
        targets = item.get("part_ids")
        if (
            not isinstance(targets, list)
            or not targets
            or any(not isinstance(x, str) or x not in ids for x in targets)
        ):
            raise ContractError(
                "material_regions.part_ids must reference declared parts"
            )
    views = _records(data, "review_view_plan", "view_id")
    for view in views:
        name = view["view_id"]
        if name.endswith(("_mask_visible", "_mask_potential")):
            raise ContractError("view_id uses a reserved mask suffix")
        targets = view.setdefault("target_part_ids", [])
        if not isinstance(targets, list) or any(
            not isinstance(x, str) or x not in ids for x in targets
        ):
            raise ContractError(
                "review_view_plan.target_part_ids must reference declared parts"
            )
        if name not in GLOBAL_REVIEW_VIEW_IDS and not targets:
            raise ContractError("part-focus views require target_part_ids")
    ranges = data["expected_bbox_or_ratio_ranges"]
    if not isinstance(ranges, dict):
        raise ContractError("expected_bbox_or_ratio_ranges must be an object")
    for name, bounds in ranges.items():
        if (
            name
            not in {
                "width_m",
                "depth_m",
                "height_m",
                "width_to_height",
                "depth_to_height",
                "width_to_depth",
            }
            or not isinstance(bounds, list)
            or len(bounds) != 2
        ):
            raise ContractError("invalid dimension or ratio range")
        low, high = (_number(v, name, minimum=1e-12) for v in bounds)
        if low > high:
            raise ContractError(f"{name}: lower bound exceeds upper bound")
    exemptions = data["geometry_exemptions"]
    if not isinstance(exemptions, list) or any(
        not isinstance(x, dict)
        or not isinstance(x.get("kind"), str)
        or x.get("kind") not in {"non_contact", "penetration", "multi_island"}
        or not isinstance(x.get("target_id"), str)
        for x in exemptions
    ):
        raise ContractError("invalid geometry_exemptions")
    return data


def part_manifest_from_design(design: dict[str, Any]) -> dict[str, Any] | None:
    """Derive the validator's part facts without a second authored manifest."""
    if not design["required_parts"]:
        return None
    return {
        "parts": [
            {
                "part_id": p["part_id"],
                "parent_part_id": p.get("parent_part_id"),
                "exemptions": p.get("exemptions", []),
            }
            for p in design["required_parts"]
        ]
    }
