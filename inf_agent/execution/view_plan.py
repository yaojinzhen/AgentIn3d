"""Shared render selections and the ordinary list of requested output files."""

from __future__ import annotations
import math
from inf_agent.workspace.contracts import GLOBAL_REVIEW_VIEW_IDS


def planned_focus_views(asset_spec):
    return [
        item
        for item in (asset_spec or {}).get("review_view_plan", [])
        if isinstance(item, dict)
        and isinstance(item.get("view_id"), str)
        and item["view_id"] not in GLOBAL_REVIEW_VIEW_IDS
    ]


def global_view_ids(design):
    views = ["perspective", "front", "side", "top", "opposite_perspective"]
    if any(
        item.get("view_id") == "bottom"
        for item in (design or {}).get("review_view_plan", [])
    ):
        views.append("bottom")
    return views


def focus_selections(metrics, *, limit=8):
    candidates = []
    for obj in metrics.get("objects", []):
        low, high = obj.get("bbox_min"), obj.get("bbox_max")
        if (
            not isinstance(low, list)
            or not isinstance(high, list)
            or len(low) != 3
            or len(high) != 3
            or not isinstance(obj.get("name"), str)
        ):
            continue
        diagonal = math.sqrt(sum((a - b) ** 2 for a, b in zip(high, low)))
        if diagonal > 1e-6:
            candidates.append((obj, diagonal))
    object_parts = {}
    for island in metrics.get("evaluated_mesh_islands", []):
        name, part_id = island.get("object_name"), island.get("part_id")
        if isinstance(name, str) and isinstance(part_id, str):
            object_parts.setdefault(name, set()).add(part_id)
    planned = planned_focus_views(
        {"review_view_plan": metrics.get("review_view_plan", [])}
    )
    if planned:
        result = []
        for plan in planned:
            chosen = []
            for part in plan["target_part_ids"]:
                options = [
                    v for v in candidates if object_parts.get(v[0]["name"]) == {part}
                ]
                if not options:
                    chosen = []
                    break
                for obj, _ in sorted(options, key=lambda v: v[0]["name"]):
                    if obj not in chosen:
                        chosen.append(obj)
            result.append((plan["view_id"], chosen, list(plan["target_part_ids"])))
        return result
    if not candidates:
        return []
    ordered = []
    for part in sorted(set(metrics.get("review_required_part_ids", []))):
        options = [v for v in candidates if object_parts.get(v[0]["name"]) == {part}]
        if options:
            selected = max(options, key=lambda v: (v[1], v[0]["name"]))
            if selected not in ordered:
                ordered.append(selected)
    largest = max(candidates, key=lambda v: (v[1], v[0]["name"]))
    if largest not in ordered:
        ordered.append(largest)
    ordered.extend(
        sorted(
            (v for v in candidates if v not in ordered),
            key=lambda v: (v[1], v[0]["name"]),
        )
    )
    return [
        (f"focus_{i:02d}", [obj], sorted(object_parts.get(obj["name"], set())))
        for i, (obj, _) in enumerate(ordered[: max(1, limit)], 1)
    ]


def expected_outputs(design, metrics, *, render, save_blend, export_glb):
    outputs = []
    if save_blend:
        outputs.append(dict(id="blend", path="scene.blend", kind="blend"))
    if export_glb:
        outputs.append(dict(id="glb", path="asset.glb", kind="glb"))
    if render:
        for name in global_view_ids(design):
            outputs.append(dict(id=name, path=f"previews/{name}.png", kind="png"))
        context = {
            **metrics,
            "review_view_plan": design.get("review_view_plan", []),
            "review_required_part_ids": [
                p["part_id"] for p in design.get("required_parts", [])
            ],
        }
        for view_id, _, parts in focus_selections(context):
            outputs.append(
                dict(
                    id=view_id,
                    path=f"previews/{view_id}.png",
                    kind="png",
                    target_part_ids=parts,
                )
            )
            for mask in ("visible", "potential"):
                outputs.append(
                    dict(
                        id=f"{view_id}_mask_{mask}",
                        path=f"previews/{view_id}_mask_{mask}.png",
                        kind="mask",
                        view_id=view_id,
                        mask=mask,
                    )
                )
    return outputs
