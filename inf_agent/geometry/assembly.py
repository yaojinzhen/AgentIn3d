"""Blender-facing part identity and assembly helpers.

The module intentionally imports Blender lazily so its data validation and
public API can be imported by ordinary Python tooling.  Part identity is stored
on the FACE domain: Blender preserves that attribute when registered meshes are
joined, so an evaluated mesh can still be split and attributed afterwards.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

PART_INDEX_ATTRIBUTE = "inf_agent_part_index"
REGISTRY_PROPERTY = "inf_agent_geometry_registry"
REGISTRATION_PROPERTY = "inf_agent_part_registration"
REGISTRY_SCHEMA_VERSION = "1.1"
SUPPORTED_ATTACHMENT_KINDS = frozenset(
    {"contact", "welded", "hinged", "inserted", "spaced"}
)


def _finite_triplet(value: Sequence[float], label: str) -> tuple[float, float, float]:
    if len(value) != 3:
        raise ValueError(f"{label} must contain three numbers")
    result = tuple(float(item) for item in value)
    if not all(math.isfinite(item) for item in result):
        raise ValueError(f"{label} must contain finite numbers")
    return result  # type: ignore[return-value]


@dataclass(frozen=True)
class LocalFrame:
    """A finite, non-singular local coordinate frame."""

    origin: tuple[float, float, float] = (0.0, 0.0, 0.0)
    basis: tuple[
        tuple[float, float, float],
        tuple[float, float, float],
        tuple[float, float, float],
    ] = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))

    def __post_init__(self) -> None:
        origin = _finite_triplet(self.origin, "origin")
        if len(self.basis) != 3:
            raise ValueError("basis must be a 3x3 matrix")
        rows = tuple(_finite_triplet(row, "basis row") for row in self.basis)
        determinant = (
            rows[0][0] * (rows[1][1] * rows[2][2] - rows[1][2] * rows[2][1])
            - rows[0][1] * (rows[1][0] * rows[2][2] - rows[1][2] * rows[2][0])
            + rows[0][2] * (rows[1][0] * rows[2][1] - rows[1][1] * rows[2][0])
        )
        if abs(determinant) <= 1e-9:
            raise ValueError("basis must be non-singular")
        object.__setattr__(self, "origin", origin)
        object.__setattr__(self, "basis", rows)

    @classmethod
    def from_value(cls, value: LocalFrame | dict[str, Any] | None) -> LocalFrame:
        if value is None:
            return cls()
        if isinstance(value, cls):
            return value
        if not isinstance(value, dict):
            raise TypeError("local frame must be a LocalFrame or mapping")
        return cls(origin=value["origin"], basis=value["basis"])

    def as_dict(self) -> dict[str, Any]:
        return {
            "origin": list(self.origin),
            "basis": [list(row) for row in self.basis],
        }

    def to_matrix(self) -> Any:
        """Return a Blender 4x4 matrix with basis vectors as columns."""

        try:
            from mathutils import Matrix
        except ImportError as error:  # pragma: no cover - Blender-only branch
            raise RuntimeError(
                "LocalFrame.to_matrix requires Blender mathutils"
            ) from error
        rows = self.basis
        return Matrix(
            (
                (rows[0][0], rows[1][0], rows[2][0], self.origin[0]),
                (rows[0][1], rows[1][1], rows[2][1], self.origin[1]),
                (rows[0][2], rows[1][2], rows[2][2], self.origin[2]),
                (0.0, 0.0, 0.0, 1.0),
            )
        )


def _identifier(value: str, label: str) -> str:
    if not isinstance(value, str) or not value or not value.replace("_", "a").isalnum():
        raise ValueError(f"{label} must be a non-empty identifier")
    return value


def _json_property(owner: Any, key: str, value: dict[str, Any]) -> None:
    owner[key] = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def load_registry(root: Any) -> dict[str, Any] | None:
    """Load the single registry attached to a returned asset hierarchy."""

    hierarchy = [root, *list(getattr(root, "children_recursive", ()))]
    matches: list[dict[str, Any]] = []
    for obj in hierarchy:
        try:
            raw = obj.get(REGISTRY_PROPERTY)
        except (AttributeError, TypeError):
            continue
        if raw is None:
            continue
        if not isinstance(raw, str):
            raise ValueError("geometry registry property must be JSON text")
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError("geometry registry property must contain an object")
        matches.append(parsed)
    if not matches:
        return None
    canonical = json.dumps(matches[0], sort_keys=True, separators=(",", ":"))
    if any(
        json.dumps(item, sort_keys=True, separators=(",", ":")) != canonical
        for item in matches[1:]
    ):
        raise ValueError("asset hierarchy contains conflicting geometry registries")
    return matches[0]


class PartRegistry:
    """Register semantic part instances and geometry constraints."""

    def __init__(self) -> None:
        self._registrations: list[dict[str, Any]] = []
        self._anchors: list[dict[str, Any]] = []
        self._attachments: list[dict[str, Any]] = []
        self._openings: list[dict[str, Any]] = []
        self._material_regions: list[dict[str, Any]] = []
        self._objects: dict[str, Any] = {}

    @property
    def registrations(self) -> tuple[dict[str, Any], ...]:
        return tuple(dict(item) for item in self._registrations)

    def _registration(self, registration_id: str) -> dict[str, Any]:
        try:
            return next(
                item
                for item in self._registrations
                if item["registration_id"] == registration_id
            )
        except StopIteration as error:
            raise ValueError(f"unknown registration_id: {registration_id}") from error

    def register(
        self,
        part_id: str,
        obj: Any,
        *,
        parent_part_id: str | None = None,
        instance_id: str | None = None,
        local_frame: LocalFrame | dict[str, Any] | None = None,
        role: str | None = None,
    ) -> str:
        """Tag all current mesh faces with a globally unique registration index."""

        _identifier(part_id, "part_id")
        if parent_part_id is not None:
            _identifier(parent_part_id, "parent_part_id")
        if getattr(obj, "type", None) != "MESH" or getattr(obj, "data", None) is None:
            raise ValueError("registered parts must be Blender mesh objects")
        registration_index = len(self._registrations) + 1
        registration_id = instance_id or f"{part_id}_{registration_index:03d}"
        _identifier(registration_id, "registration_id")
        if any(
            item["registration_id"] == registration_id for item in self._registrations
        ):
            raise ValueError(f"duplicate registration_id: {registration_id}")
        frame = LocalFrame.from_value(local_frame)
        attributes = obj.data.attributes
        attribute = attributes.get(PART_INDEX_ATTRIBUTE)
        if attribute is not None and (
            attribute.domain != "FACE" or attribute.data_type != "INT"
        ):
            attributes.remove(attribute)
            attribute = None
        if attribute is None:
            attribute = attributes.new(
                name=PART_INDEX_ATTRIBUTE,
                type="INT",
                domain="FACE",
            )
        for item in attribute.data:
            item.value = registration_index
        record = {
            "registration_index": registration_index,
            "registration_id": registration_id,
            "part_id": part_id,
            "role": role or part_id,
            "parent_part_id": parent_part_id,
            "object_name": obj.name_full,
            "local_frame": frame.as_dict(),
        }
        _json_property(obj, REGISTRATION_PROPERTY, record)
        self._registrations.append(record)
        self._objects[registration_id] = obj
        return registration_id

    def anchor(
        self,
        registration_id: str,
        anchor_id: str,
        frame: LocalFrame | dict[str, Any],
    ) -> str:
        self._registration(registration_id)
        _identifier(anchor_id, "anchor_id")
        if any(item["anchor_id"] == anchor_id for item in self._anchors):
            raise ValueError(f"duplicate anchor_id: {anchor_id}")
        self._anchors.append(
            {
                "anchor_id": anchor_id,
                "registration_id": registration_id,
                "local_frame": LocalFrame.from_value(frame).as_dict(),
            }
        )
        return anchor_id

    def surface_anchor(
        self,
        registration_id: str,
        anchor_id: str,
        *,
        face_index: int,
        barycentric: Sequence[float] = (1 / 3, 1 / 3, 1 / 3),
    ) -> str:
        """Declare an anchor on a carrier triangle, using its local normal/frame."""

        self._registration(registration_id)
        obj = self._objects[registration_id]
        if (
            not isinstance(face_index, int)
            or face_index < 0
            or face_index >= len(obj.data.polygons)
        ):
            raise ValueError("surface anchor face_index is outside the carrier mesh")
        weights = _finite_triplet(barycentric, "barycentric")
        if any(value < 0 for value in weights) or abs(sum(weights) - 1) > 1e-6:
            raise ValueError("barycentric weights must be non-negative and sum to one")
        polygon = obj.data.polygons[face_index]
        if len(polygon.vertices) != 3:
            raise ValueError("surface anchor requires a triangulated face")
        try:
            from mathutils import Vector
        except ImportError as error:  # pragma: no cover - Blender-only branch
            raise RuntimeError("surface anchors require Blender mathutils") from error
        vertices = [
            Vector(obj.data.vertices[index].co) for index in polygon.vertices[:3]
        ]
        tangent = vertices[1] - vertices[0]
        normal = tangent.cross(vertices[2] - vertices[0])
        if tangent.length <= 1e-9 or normal.length <= 1e-9:
            raise ValueError("surface anchor triangle is degenerate")
        tangent.normalize()
        normal.normalize()
        bitangent = normal.cross(tangent).normalized()
        origin = sum(
            (weight * vertex for weight, vertex in zip(weights, vertices)),
            Vector((0, 0, 0)),
        )
        return self.anchor(
            registration_id,
            anchor_id,
            LocalFrame(
                tuple(origin), (tuple(tangent), tuple(bitangent), tuple(normal))
            ),
        )

    def material_region(
        self, region_id: str, part_ids: Sequence[str], material_name: str
    ) -> str:
        """Bind one semantic region to material actually assigned on its parts."""

        _identifier(region_id, "region_id")
        if any(item["region_id"] == region_id for item in self._material_regions):
            raise ValueError(f"duplicate material region: {region_id}")
        declared = {item["part_id"] for item in self._registrations}
        members = list(part_ids)
        if not members or len(set(members)) != len(members) or set(members) - declared:
            raise ValueError(
                "material region must name registered part ids exactly once"
            )
        if not isinstance(material_name, str) or not material_name.strip():
            raise ValueError("material_name must be non-empty")
        self._material_regions.append(
            {
                "region_id": region_id,
                "part_ids": members,
                "material_name": material_name,
            }
        )
        return region_id

    def attach(
        self,
        attachment_id: str,
        child_registration_id: str,
        parent_registration_id: str,
        *,
        kind: str = "contact",
        child_anchor_id: str | None = None,
        parent_anchor_id: str | None = None,
        minimum_gap_m: float | None = None,
        maximum_gap_m: float | None = None,
    ) -> str:
        _identifier(attachment_id, "attachment_id")
        child = self._registration(child_registration_id)
        parent = self._registration(parent_registration_id)
        if kind not in SUPPORTED_ATTACHMENT_KINDS:
            raise ValueError(f"unsupported attachment kind: {kind}")
        if any(item["attachment_id"] == attachment_id for item in self._attachments):
            raise ValueError(f"duplicate attachment_id: {attachment_id}")
        known_anchors = {item["anchor_id"] for item in self._anchors}
        for anchor_id in (child_anchor_id, parent_anchor_id):
            if anchor_id is not None and anchor_id not in known_anchors:
                raise ValueError(f"unknown anchor_id: {anchor_id}")
        gaps = (minimum_gap_m, maximum_gap_m)
        if kind == "spaced":
            if any(value is None for value in gaps):
                raise ValueError(
                    "spaced attachments require minimum_gap_m and maximum_gap_m"
                )
            minimum, maximum = (float(value) for value in gaps if value is not None)
            if not all(
                math.isfinite(value) and value >= 0 for value in (minimum, maximum)
            ):
                raise ValueError(
                    "spaced attachment gaps must be finite and non-negative"
                )
            if maximum < minimum:
                raise ValueError("maximum_gap_m must be at least minimum_gap_m")
        elif any(value is not None for value in gaps):
            raise ValueError("gap bounds are only valid for spaced attachments")
        self._attachments.append(
            {
                "attachment_id": attachment_id,
                "part_id": child["part_id"],
                "parent_part_id": parent["part_id"],
                "child_registration_id": child_registration_id,
                "parent_registration_id": parent_registration_id,
                "kind": kind,
                "child_anchor_id": child_anchor_id,
                "parent_anchor_id": parent_anchor_id,
                "minimum_gap_m": minimum_gap_m,
                "maximum_gap_m": maximum_gap_m,
            }
        )
        return attachment_id

    def opening(
        self,
        feature_id: str,
        owner_registration_id: str,
        *,
        start: Sequence[float],
        end: Sequence[float],
        clearance_radius: float = 0.0,
        kind: str = "through_opening",
    ) -> str:
        _identifier(feature_id, "feature_id")
        if kind not in ("through_opening", "cavity_entrance"):
            raise ValueError("opening kind must be through_opening or cavity_entrance")
        owner = self._registration(owner_registration_id)
        if any(item["feature_id"] == feature_id for item in self._openings):
            raise ValueError(f"duplicate feature_id: {feature_id}")
        local_start = _finite_triplet(start, "opening start")
        local_end = _finite_triplet(end, "opening end")
        if local_start == local_end:
            raise ValueError("opening probe must have non-zero length")
        radius = float(clearance_radius)
        if not math.isfinite(radius) or radius < 0:
            raise ValueError("opening clearance_radius must be finite and non-negative")
        obj = self._objects[owner_registration_id]
        try:
            import bpy
            from mathutils import Vector
        except ImportError as error:  # pragma: no cover - Blender-only branch
            raise RuntimeError("opening probes require Blender mathutils") from error
        bpy.context.view_layer.update()
        world_start = obj.matrix_world @ Vector(local_start)
        world_end = obj.matrix_world @ Vector(local_end)
        self._openings.append(
            {
                "feature_id": feature_id,
                "kind": kind,
                "owner_part_id": owner["part_id"],
                "owner_registration_id": owner_registration_id,
                "local_start": list(local_start),
                "local_end": list(local_end),
                "world_start": [float(value) for value in world_start],
                "world_end": [float(value) for value in world_end],
                "clearance_radius_m": radius,
            }
        )
        return feature_id

    def align_anchors(
        self,
        child_registration_id: str,
        child_anchor_id: str,
        parent_registration_id: str,
        parent_anchor_id: str,
    ) -> None:
        """Move the child so both declared anchor frames coincide in world space."""

        child_obj = self._objects[child_registration_id]
        parent_obj = self._objects[parent_registration_id]
        anchors = {item["anchor_id"]: item for item in self._anchors}
        child = anchors.get(child_anchor_id)
        parent = anchors.get(parent_anchor_id)
        if child is None or child["registration_id"] != child_registration_id:
            raise ValueError("child anchor does not belong to child registration")
        if parent is None or parent["registration_id"] != parent_registration_id:
            raise ValueError("parent anchor does not belong to parent registration")
        child_local = LocalFrame.from_value(child["local_frame"]).to_matrix()
        parent_local = LocalFrame.from_value(parent["local_frame"]).to_matrix()
        target_world = parent_obj.matrix_world @ parent_local
        child_obj.matrix_world = target_world @ child_local.inverted()

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": REGISTRY_SCHEMA_VERSION,
            "part_index_attribute": PART_INDEX_ATTRIBUTE,
            "registrations": self._registrations,
            "anchors": self._anchors,
            "attachments": self._attachments,
            "openings": self._openings,
            "material_regions": self._material_regions,
        }

    def finalize(self, root: Any) -> dict[str, Any]:
        if not self._registrations:
            raise ValueError("part registry cannot be finalized without registrations")
        if self._openings:
            import bpy
            from mathutils import Vector

            bpy.context.view_layer.update()
            inverse = root.matrix_world.inverted()
            for opening in self._openings:
                # Factory.spawn_asset may subsequently move/rotate the root.
                # Root coordinates survive that placement and registered joins.
                opening["root_start"] = list(inverse @ Vector(opening["world_start"]))
                opening["root_end"] = list(inverse @ Vector(opening["world_end"]))
        value = self.as_dict()
        _json_property(root, REGISTRY_PROPERTY, value)
        return value

    def join_objects(self, objects: Iterable[Any], *, name: str | None = None) -> Any:
        """Join registered meshes while preserving face-domain part indices."""

        selected = list(objects)
        if not selected or any(
            getattr(obj, "type", None) != "MESH" for obj in selected
        ):
            raise ValueError("join_objects requires at least one mesh object")
        try:
            import bpy
        except ImportError as error:  # pragma: no cover - Blender-only branch
            raise RuntimeError("join_objects requires Blender bpy") from error
        bpy.ops.object.select_all(action="DESELECT")
        for obj in selected:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = selected[0]
        bpy.ops.object.join()
        joined = bpy.context.view_layer.objects.active
        if joined is None:
            raise RuntimeError("Blender join did not produce an active object")
        if name:
            joined.name = name
        attribute = joined.data.attributes.get(PART_INDEX_ATTRIBUTE)
        if (
            attribute is None
            or attribute.domain != "FACE"
            or attribute.data_type != "INT"
        ):
            raise RuntimeError(
                "Blender join lost the face-domain part identity attribute"
            )
        valid_indices = {item["registration_index"] for item in self._registrations}
        observed = {int(item.value) for item in attribute.data}
        if not observed or observed - valid_indices:
            raise RuntimeError("joined mesh contains invalid part identity values")
        self.finalize(joined)
        return joined


class AssemblyBuilder:
    """Convenience facade for declarative part registration and placement."""

    def __init__(self, registry: PartRegistry | None = None) -> None:
        self.registry = registry or PartRegistry()

    def register(self, *args: Any, **kwargs: Any) -> str:
        return self.registry.register(*args, **kwargs)

    def anchor(self, *args: Any, **kwargs: Any) -> str:
        return self.registry.anchor(*args, **kwargs)

    def surface_anchor(self, *args: Any, **kwargs: Any) -> str:
        return self.registry.surface_anchor(*args, **kwargs)

    def material_region(self, *args: Any, **kwargs: Any) -> str:
        return self.registry.material_region(*args, **kwargs)

    def attach(self, *args: Any, align: bool = True, **kwargs: Any) -> str:
        child = args[1] if len(args) > 1 else kwargs["child_registration_id"]
        parent = args[2] if len(args) > 2 else kwargs["parent_registration_id"]
        child_anchor = kwargs.get("child_anchor_id")
        parent_anchor = kwargs.get("parent_anchor_id")
        if align and child_anchor and parent_anchor:
            self.registry.align_anchors(child, child_anchor, parent, parent_anchor)
        return self.registry.attach(*args, **kwargs)

    def opening(self, *args: Any, **kwargs: Any) -> str:
        return self.registry.opening(*args, **kwargs)

    def join_objects(self, *args: Any, **kwargs: Any) -> Any:
        return self.registry.join_objects(*args, **kwargs)

    def finalize(self, root: Any) -> dict[str, Any]:
        return self.registry.finalize(root)


__all__ = [
    "AssemblyBuilder",
    "LocalFrame",
    "PART_INDEX_ATTRIBUTE",
    "PartRegistry",
    "REGISTRATION_PROPERTY",
    "REGISTRY_PROPERTY",
    "SUPPORTED_ATTACHMENT_KINDS",
    "load_registry",
]
