"""Small checks at persisted request, run-configuration and metric boundaries."""

from __future__ import annotations
import copy
from pathlib import Path
from inf_agent.workspace.contracts import (
    ContractError,
    SCHEMA_VERSION,
    _finite,
    normalize_design,
)
from inf_agent.workspace.input_validation import (
    normalize_dimensions,
    normalize_request_text,
)


def normalize_request(value):
    if not isinstance(value, dict) or value.get("schema_version") != SCHEMA_VERSION:
        raise ContractError("request: expected a current-format object")
    forbidden = value.get("forbidden_items", [])
    if not isinstance(forbidden, list):
        raise ContractError("request.forbidden_items: expected a list of strings")
    prompt, forbidden = normalize_request_text(value.get("prompt"), forbidden)
    reference = value.get("reference_image")
    if reference is not None and (
        not isinstance(reference, str) or not reference.strip()
    ):
        raise ContractError(
            "request.reference_image: expected a filename string or null"
        )
    dimensions = value.get("explicit_dimensions_m", {})
    if not isinstance(dimensions, dict):
        raise ContractError("request.explicit_dimensions_m: expected an object")
    from inf_agent.workspace.snapshot import normalize_local_dependencies

    dependencies = normalize_local_dependencies(value.get("local_dependencies", []))
    _finite(value, "request")
    return {
        **value,
        "prompt": prompt,
        "forbidden_items": forbidden,
        "explicit_dimensions_m": normalize_dimensions(dimensions),
        "local_dependencies": dependencies,
    }


def normalize_run_config(value):
    if not isinstance(value, dict) or value.get("schema_version") != SCHEMA_VERSION:
        raise ContractError("config: unsupported run format")
    value = copy.deepcopy(value)
    for key in ("repo_root", "output_dir", "source_path", "asset_id"):
        if not isinstance(value.get(key), str) or not value[key]:
            raise ContractError(f"config.{key}: expected a non-empty string")
    for key in ("repo_root", "output_dir", "source_path"):
        if not Path(value[key]).is_absolute():
            raise ContractError(f"config.{key}: expected an absolute path")
    if value.get("factory_class") is not None and not isinstance(
        value["factory_class"], str
    ):
        raise ContractError("config.factory_class: expected a string or null")
    value["request"] = normalize_request(value.get("request"))
    if "design" in value and not isinstance(value["design"], dict):
        raise ContractError("config.design: expected an object")
    value["design"] = normalize_design(value.get("design", {}))
    parameters = value.get("parameters")
    if not isinstance(parameters, dict):
        raise ContractError("config.parameters: expected an object")
    for key in ("seed", "instance_index", "samples"):
        n = parameters.get(key)
        if not isinstance(n, int) or isinstance(n, bool):
            raise ContractError(f"config.parameters.{key}: expected an integer")
    if parameters["instance_index"] < 0 or not 0 <= parameters["seed"] <= 2**32 - 1:
        raise ContractError("config.parameters: invalid seed or instance_index")
    for key in ("save_blend", "export_glb"):
        if not isinstance(parameters.get(key), bool):
            raise ContractError(f"config.parameters.{key}: expected a bool")
    if parameters.get("render") not in ("image", "none"):
        raise ContractError("config.parameters.render: expected image or none")
    if parameters.get("render_engine") not in (
        "BLENDER_EEVEE_NEXT",
        "CYCLES",
        "BLENDER_WORKBENCH",
    ):
        raise ContractError("config.parameters.render_engine: unsupported engine")
    resolution = parameters.get("resolution")
    if not isinstance(resolution, (list, tuple)) or len(resolution) != 2:
        raise ContractError("config.parameters.resolution: expected two integers")
    from inf_agent.execution.resource_policy import (
        ResourcePolicy,
        validate_render_request,
    )

    from inf_agent.execution.material_export import MaterialExportSettings

    settings = MaterialExportSettings(
        parameters.get("texture_resolution", 2048), parameters.get("bake_samples", 4)
    )
    parameters.update(
        texture_resolution=settings.texture_resolution,
        bake_samples=settings.bake_samples,
    )
    limits = value.get("limits", {})
    if not isinstance(limits, dict):
        raise ContractError("config.limits: expected an object")
    try:
        policy = ResourcePolicy(**limits)
    except (TypeError, ValueError) as error:
        raise ContractError(f"config.limits: {error}") from error
    validate_render_request(tuple(resolution), parameters["samples"], policy=policy)
    _finite(value, "config")
    return value


def validate_metadata(value):
    if not isinstance(value, dict):
        raise ContractError("metadata: expected an object")
    _finite(value, "metadata")
    error = value.get("error")
    if error is not None and (
        not isinstance(error, dict)
        or any(not isinstance(error.get(k), str) for k in ("type", "message"))
    ):
        raise ContractError("metadata.error: expected type/message strings or null")
    metrics = value.get("asset", {})
    if not isinstance(metrics, dict):
        raise ContractError("metadata.asset: expected an object")

    def records(parent, key, label):
        items = parent.get(key, [])
        if not isinstance(items, list) or any(not isinstance(x, dict) for x in items):
            raise ContractError(f"{label}.{key}: expected a list of objects")
        return items

    for key in ("bbox", "part_registry", "structural"):
        if (
            key in metrics
            and metrics[key] is not None
            and not isinstance(metrics[key], dict)
        ):
            raise ContractError(f"metadata.asset.{key}: expected an object or null")
    for key in ("objects", "evaluated_mesh_islands", "negative_spaces", "focus_views"):
        records(metrics, key, "metadata.asset")
    for key in (
        "mesh_count",
        "object_count",
        "vertex_count",
        "face_count",
        "material_count",
        "uncovered_material_faces",
    ):
        if key in metrics and (
            isinstance(metrics[key], bool)
            or not isinstance(metrics[key], int)
            or metrics[key] < 0
        ):
            raise ContractError(
                f"metadata.asset.{key}: expected a non-negative integer"
            )
    for obj in metrics.get("objects", []):
        for key in (
            "evaluated_edges",
            "evaluated_faces",
            "evaluated_vertices",
            "non_manifold_edges",
            "zero_area_faces",
            "loose_vertices",
            "face_aspect_p99",
        ):
            n = obj.get(key, 0)
            if isinstance(n, bool) or not isinstance(n, (int, float)) or n < 0:
                raise ContractError(
                    f"metadata.asset.objects.{key}: expected a non-negative number"
                )
        for key in ("bbox_min", "bbox_max"):
            if key in obj and (
                not isinstance(obj[key], list)
                or len(obj[key]) != 3
                or any(
                    isinstance(n, bool) or not isinstance(n, (int, float))
                    for n in obj[key]
                )
            ):
                raise ContractError(
                    f"metadata.asset.objects.{key}: expected three numbers"
                )
    for key in ("width", "depth", "height"):
        box = metrics.get("bbox") or {}
        if key in box and (
            isinstance(box[key], bool) or not isinstance(box[key], (int, float))
        ):
            raise ContractError(f"metadata.asset.bbox.{key}: expected a number")
    for parent, key in ((metrics.get("structural") or {}, "contacts"),):
        records(parent, key, "metadata.asset.structural")
    registry = metrics.get("part_registry") or {}
    for key in (
        "registrations",
        "attachments",
        "anchors",
        "openings",
        "material_regions",
    ):
        records(registry, key, "metadata.asset.part_registry")
    for key in ("unmaterialized_meshes", "review_required_part_ids", "review_view_ids"):
        if key in metrics and (
            not isinstance(metrics[key], list)
            or any(not isinstance(x, str) for x in metrics[key])
        ):
            raise ContractError(f"metadata.asset.{key}: expected strings")
    for record in metrics.get("focus_views", []):
        if (
            not isinstance(record.get("id"), str)
            or not isinstance(record.get("target_part_ids", []), list)
            or any(not isinstance(x, str) for x in record.get("target_part_ids", []))
        ):
            raise ContractError(
                "metadata.asset.focus_views: invalid id or target_part_ids"
            )
    graph = metrics.get("structural") or {}
    for parent, label, keys in (
        (registry, "part_registry", ("errors",)),
        (graph, "structural", ("isolated_objects", "isolated_islands")),
    ):
        for key in keys:
            if key in parent and (
                not isinstance(parent[key], list)
                or any(not isinstance(x, str) for x in parent[key])
            ):
                raise ContractError(f"metadata.asset.{label}.{key}: expected strings")
    for parent, label, keys in (
        (registry, "part_registry", ("valid", "available")),
        (graph, "structural", ("connected",)),
    ):
        for key in keys:
            if key in parent and not isinstance(parent[key], bool):
                raise ContractError(f"metadata.asset.{label}.{key}: expected a bool")
    id_fields = (
        "registration_id",
        "part_id",
        "parent_part_id",
        "owner_part_id",
        "owner_registration_id",
        "child_registration_id",
        "parent_registration_id",
        "left_registration_id",
        "right_registration_id",
        "left_part_id",
        "right_part_id",
        "anchor_id",
        "child_anchor_id",
        "parent_anchor_id",
        "attachment_id",
        "feature_id",
        "region_id",
        "kind",
    )
    collections = [
        metrics.get(key, []) for key in ("evaluated_mesh_islands", "negative_spaces")
    ]
    collections += [
        registry.get(key, [])
        for key in (
            "registrations",
            "attachments",
            "anchors",
            "openings",
            "material_regions",
        )
    ]
    collections.append((metrics.get("structural") or {}).get("contacts", []))
    for items in collections:
        for record in items:
            for key in id_fields:
                if (
                    key in record
                    and record[key] is not None
                    and not isinstance(record[key], str)
                ):
                    raise ContractError(
                        f"metadata.asset.geometry.{key}: expected a string or null"
                    )
            if "part_ids" in record and (
                not isinstance(record["part_ids"], list)
                or any(not isinstance(x, str) for x in record["part_ids"])
            ):
                raise ContractError(
                    "metadata.asset.geometry.part_ids: expected strings"
                )
            for key in ("registration_indices",):
                if key in record and (
                    not isinstance(record[key], list)
                    or any(
                        not isinstance(x, int) or isinstance(x, bool)
                        for x in record[key]
                    )
                ):
                    raise ContractError(
                        f"metadata.asset.geometry.{key}: expected integer indices"
                    )
            for key in ("registration_index", "contact_component"):
                if key in record and (
                    not isinstance(record[key], int) or isinstance(record[key], bool)
                ):
                    raise ContractError(
                        f"metadata.asset.geometry.{key}: expected an integer"
                    )
            for key in ("passed", "bbox_span_valid", "within_tolerance", "closed"):
                if key in record and not isinstance(record[key], bool):
                    raise ContractError(
                        f"metadata.asset.geometry.{key}: expected a bool"
                    )
    for key in ("connected_component_count", "island_count"):
        graph = metrics.get("structural") or {}
        if key in graph and (
            not isinstance(graph[key], int)
            or isinstance(graph[key], bool)
            or graph[key] < 0
        ):
            raise ContractError(
                f"metadata.asset.structural.{key}: expected a non-negative integer"
            )
    faces = metrics.get("part_material_faces", {})
    if not isinstance(faces, dict) or any(
        not isinstance(v, dict)
        or any(
            not isinstance(n, int) or isinstance(n, bool) or n < 0 for n in v.values()
        )
        for v in faces.values()
    ):
        raise ContractError(
            "metadata.asset.part_material_faces: expected part/material face counts"
        )
    return value
