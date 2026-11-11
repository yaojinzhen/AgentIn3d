"""Blender-specific operations for the generated-asset execution package.

The flow follows ``infinigen_examples.generate_asset_simple``: configure one
scene, instantiate one factory, call ``spawn_asset``/``finalize_assets``, frame
the result, and write Blender-owned outputs.
"""

from __future__ import annotations

import hashlib
import inspect
import math
import time
from pathlib import Path
from typing import Any

from inf_agent.geometry.assembly import PART_INDEX_ATTRIBUTE, load_registry
from inf_agent.execution.view_plan import focus_selections, global_view_ids


class BlenderSession:
    """Own Blender/Infinigen state for one generated asset run."""

    def __init__(self) -> None:
        self.import_timings_seconds: dict[str, float] = {}
        try:
            started = time.monotonic()
            import bpy

            self.import_timings_seconds["bpy"] = round(time.monotonic() - started, 6)
            started = time.monotonic()
            import gin
            from mathutils import Vector
            from mathutils.bvhtree import BVHTree

            self.import_timings_seconds["gin_mathutils"] = round(
                time.monotonic() - started, 6
            )

            started = time.monotonic()
            from infinigen.core import init
            from infinigen.core.placement.factory import AssetFactory
            from infinigen.core.util import blender as butil
            from infinigen.core.util.math import FixedSeed

            self.import_timings_seconds["infinigen_core"] = round(
                time.monotonic() - started, 6
            )
        except ImportError as error:
            raise RuntimeError(
                "Blender/Infinigen runtime is unavailable; run with Python 3.11 "
                "that can import bpy and the repository package"
            ) from error

        try:
            started = time.monotonic()
            import bmesh

            self.import_timings_seconds["bmesh"] = round(time.monotonic() - started, 6)
        except ImportError:
            bmesh = None

        self.bpy = bpy
        self.bmesh = bmesh
        self.gin = gin
        self.Vector = Vector
        self.BVHTree = BVHTree
        self.init = init
        self.AssetFactory = AssetFactory
        self.butil = butil
        self.FixedSeed = FixedSeed

    @property
    def environment(self) -> dict[str, Any]:
        return {
            "blender": self.bpy.app.version_string,
            "background": bool(self.bpy.app.background),
            "bmesh_available": self.bmesh is not None,
        }

    def configure(
        self,
        *,
        render_engine: str,
        resolution: tuple[int, int],
        samples: int,
    ) -> None:
        """Apply base gin config and initialize a clean preview scene."""

        self.gin.clear_config()
        self.init.apply_gin_configs(
            [
                "infinigen_examples/configs_indoor",
                "infinigen_examples/configs_nature",
            ],
            skip_unknown=True,
        )
        self.butil.clear_scene()

        scene = self.bpy.context.scene
        scene.render.engine = render_engine
        scene.render.resolution_x, scene.render.resolution_y = resolution
        scene.render.resolution_percentage = 100
        scene.render.image_settings.file_format = "PNG"
        scene.render.image_settings.color_mode = "RGBA"
        scene.render.film_transparent = False
        scene.render.use_file_extension = True
        scene.frame_set(1)

        if render_engine == "CYCLES":
            scene.cycles.samples = samples
            scene.cycles.device = "CPU"
        elif hasattr(scene, "eevee") and hasattr(scene.eevee, "taa_render_samples"):
            scene.eevee.taa_render_samples = samples

        world = scene.world
        if world is None:
            world = self.bpy.data.worlds.new("__runner_world")
            scene.world = world
        world.use_nodes = True
        background = world.node_tree.nodes.get("Background")
        if background is not None:
            background.inputs["Color"].default_value = (
                0.035,
                0.035,
                0.035,
                1,
            )
            background.inputs["Strength"].default_value = 0.35

    def import_factory(
        self, reference: str | None = None, *, source_path: Path | None = None
    ) -> type:
        """Import a local asset module and select a concrete AssetFactory subclass."""
        import importlib
        import importlib.util
        import sys
        import uuid

        if source_path is not None:
            source_path = source_path.resolve(strict=True)
            if source_path.suffix != ".py":
                raise RuntimeError("asset source must be a Python file")
            name = "_inf_agent_asset_" + uuid.uuid4().hex
            definition = importlib.util.spec_from_file_location(
                name, source_path, submodule_search_locations=[str(source_path.parent)]
            )
            if definition is None or definition.loader is None:
                raise RuntimeError(f"cannot load asset source: {source_path}")
            module = importlib.util.module_from_spec(definition)
            sys.modules[name] = module
            sys.path.insert(0, str(source_path.parent))
            try:
                definition.loader.exec_module(module)
            finally:
                sys.path.remove(str(source_path.parent))
        else:
            if not reference or "." not in reference:
                raise RuntimeError("factory reference must use module.Class")
            module_name, _, reference = reference.rpartition(".")
            module = importlib.import_module(module_name)
        if reference:
            factory = getattr(module, reference, None)
        else:
            candidates = [
                value
                for value in vars(module).values()
                if inspect.isclass(value)
                and value is not self.AssetFactory
                and issubclass(value, self.AssetFactory)
                and value.__module__ == module.__name__
                and not inspect.isabstract(value)
            ]
            candidates = [
                x
                for x in candidates
                if not any(
                    x is not other and issubclass(other, x) for other in candidates
                )
            ]
            if len(candidates) != 1:
                raise RuntimeError(
                    "specify --factory when asset.py does not define exactly one leaf AssetFactory"
                )
            factory = candidates[0]
        if (
            not inspect.isclass(factory)
            or factory is self.AssetFactory
            or not issubclass(factory, self.AssetFactory)
            or inspect.isabstract(factory)
        ):
            raise RuntimeError(
                "selected factory must be a concrete AssetFactory subclass"
            )
        return factory

    def build_asset(
        self,
        factory_class: type,
        *,
        seed: int,
        instance_index: int,
        spec: dict[str, Any],
    ) -> Any:
        """Run the same factory lifecycle used by ``generate_asset_simple``."""

        signature = inspect.signature(factory_class)
        parameters = signature.parameters
        accepts_kwargs = any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD
            for parameter in parameters.values()
        )
        kwargs: dict[str, Any] = {}
        if "spec" in parameters or accepts_kwargs:
            kwargs["spec"] = spec
        if "dimensions" in parameters or accepts_kwargs:
            kwargs["dimensions"] = spec.get("dimensions")

        factory = factory_class(seed, **kwargs)
        with self.FixedSeed(seed):
            asset = factory.spawn_asset(instance_index)
            factory.finalize_assets(asset)

        if not isinstance(asset, self.bpy.types.Object):
            raise RuntimeError("generated factory must return one bpy.types.Object")
        if asset.name not in self.bpy.data.objects:
            raise RuntimeError(
                "generated factory returned an object no longer linked to Blender data"
            )
        self.bpy.context.view_layer.update()
        return asset

    @staticmethod
    def _hierarchy(root: Any) -> list[Any]:
        return [root, *list(root.children_recursive)]

    def _visible_meshes(self, root: Any) -> list[Any]:
        meshes = []
        for obj in self._hierarchy(root):
            if obj.type != "MESH" or obj.hide_render:
                continue
            try:
                visible = obj.visible_get()
            except (AttributeError, RuntimeError):
                visible = not obj.hide_viewport
            if visible:
                meshes.append(obj)
        return meshes

    def _evaluated_mesh_islands(
        self,
        obj: Any,
        evaluated: Any,
        mesh: Any,
        registrations: dict[int, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Split an evaluated mesh into face-connected semantic islands."""

        vertex_faces: dict[int, list[int]] = {}
        for polygon in mesh.polygons:
            for vertex_index in polygon.vertices:
                vertex_faces.setdefault(int(vertex_index), []).append(polygon.index)
        adjacency = [set() for _ in mesh.polygons]
        for linked_faces in vertex_faces.values():
            for face_index in linked_faces:
                adjacency[face_index].update(linked_faces)
                adjacency[face_index].discard(face_index)

        attribute = mesh.attributes.get(PART_INDEX_ATTRIBUTE)
        identity_available = (
            attribute is not None
            and attribute.domain == "FACE"
            and attribute.data_type == "INT"
            and len(attribute.data) == len(mesh.polygons)
        )
        world_vertices = [
            evaluated.matrix_world @ vertex.co.copy() for vertex in mesh.vertices
        ]
        islands: list[dict[str, Any]] = []
        unseen = set(range(len(mesh.polygons)))
        while unseen:
            pending = [unseen.pop()]
            faces: list[int] = []
            while pending:
                current = pending.pop()
                faces.append(current)
                neighbors = adjacency[current] & unseen
                unseen.difference_update(neighbors)
                pending.extend(neighbors)
            faces.sort()
            polygons = [tuple(mesh.polygons[index].vertices) for index in faces]
            edge_uses: dict[tuple[int, int], int] = {}
            face_normals: list[tuple[float, float, float]] = []
            face_centers: list[Any] = []
            for polygon in polygons:
                for start, end in zip(polygon, polygon[1:] + polygon[:1]):
                    edge = tuple(sorted((start, end)))
                    edge_uses[edge] = edge_uses.get(edge, 0) + 1
                normal = (
                    world_vertices[polygon[1]] - world_vertices[polygon[0]]
                ).cross(world_vertices[polygon[2]] - world_vertices[polygon[0]])
                if normal.length:
                    normal.normalize()
                face_normals.append(tuple(float(normal[axis]) for axis in range(3)))
                center = self.Vector((0.0, 0.0, 0.0))
                for index in polygon:
                    center += world_vertices[index]
                face_centers.append(center / len(polygon))
            used_vertices = sorted({index for polygon in polygons for index in polygon})
            points = [world_vertices[index] for index in used_vertices]
            minimum = [min(point[axis] for point in points) for axis in range(3)]
            maximum = [max(point[axis] for point in points) for axis in range(3)]
            indices = (
                sorted({int(attribute.data[index].value) for index in faces})
                if identity_available
                else []
            )
            registration = registrations.get(indices[0]) if len(indices) == 1 else None
            island_id = f"{obj.name_full}:island_{len(islands) + 1:03d}"
            islands.append(
                {
                    "island_id": island_id,
                    "name": island_id,
                    "object_name": obj.name_full,
                    "face_count": len(faces),
                    "vertex_count": len(used_vertices),
                    "registration_indices": indices,
                    "registration_id": (
                        registration.get("registration_id") if registration else None
                    ),
                    "part_id": registration.get("part_id") if registration else None,
                    "min": [float(value) for value in minimum],
                    "max": [float(value) for value in maximum],
                    "bbox": {
                        "min": [round(float(value), 6) for value in minimum],
                        "max": [round(float(value), 6) for value in maximum],
                    },
                    "vertices": [world_vertices[index] for index in used_vertices],
                    "face_centers": face_centers,
                    "closed": bool(edge_uses)
                    and all(count == 2 for count in edge_uses.values()),
                    "face_normals": face_normals,
                    "bvh": self.BVHTree.FromPolygons(world_vertices, polygons),
                }
            )
        return islands

    @staticmethod
    def _separation_upper_bound(
        first: dict[str, Any],
        second: dict[str, Any],
        overlap_pairs: list[tuple[int, int]],
    ) -> float | None:
        """Find a conservative mesh-projection translation that separates a pair."""

        if not first.get("face_normals") or not second.get("face_normals"):
            return None
        directions = [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)]
        for left_face, right_face in overlap_pairs[:256]:
            for item, index in ((first, left_face), (second, right_face)):
                normals = item["face_normals"]
                if 0 <= index < len(normals):
                    directions.append(normals[index])
        upper = math.inf
        for direction in directions:
            length = math.sqrt(sum(value * value for value in direction))
            if length <= 1e-12:
                continue
            axis = tuple(value / length for value in direction)
            first_projection = [
                sum(point[index] * axis[index] for index in range(3))
                for point in first["vertices"]
            ]
            second_projection = [
                sum(point[index] * axis[index] for index in range(3))
                for point in second["vertices"]
            ]
            displacement = min(
                max(first_projection) - min(second_projection),
                max(second_projection) - min(first_projection),
            )
            upper = min(upper, max(0.0, displacement))
        return None if math.isinf(upper) else upper

    def _point_inside_closed_bvh(
        self, bvh: Any, point: Any, *, epsilon: float, ray_distance: float
    ) -> bool | None:
        """Use ray parity only for topologically closed evaluated mesh islands."""

        direction = self.Vector((0.613, 0.707, 0.354)).normalized()
        origin = self.Vector(point)
        hits = 0
        for _ in range(128):
            location, _, _, _ = bvh.ray_cast(origin, direction, ray_distance)
            if location is None:
                return bool(hits % 2)
            hits += 1
            origin = location + direction * (epsilon * 2.0)
        return None

    def _penetration_evidence(
        self,
        first: dict[str, Any],
        second: dict[str, Any],
        overlap_pairs: list[tuple[int, int]],
        *,
        tolerance: float,
        asset_diagonal: float,
    ) -> dict[str, Any]:
        """Bound real mesh penetration; never present AABB overlap as depth."""

        upper = self._separation_upper_bound(first, second, overlap_pairs)
        lower = 0.0
        samples = 0
        epsilon = max(asset_diagonal * 1e-6, 1e-6)
        if upper is None or upper > tolerance:
            for source, target in ((first, second), (second, first)):
                if not target.get("closed"):
                    continue
                points = [*source["vertices"], *source.get("face_centers", [])]
                stride = max(1, len(points) // 256)
                for point in points[::stride]:
                    hit = target["bvh"].find_nearest(point)
                    if hit is None or hit[0] is None or float(hit[3]) <= epsilon * 2:
                        continue
                    samples += 1
                    inside = self._point_inside_closed_bvh(
                        target["bvh"],
                        point,
                        epsilon=epsilon,
                        ray_distance=asset_diagonal * 4.0 + 1.0,
                    )
                    if inside is True:
                        lower = max(lower, float(hit[3]))
        if upper is not None and lower > upper + epsilon:
            status = "UNRESOLVED"
        elif lower > tolerance:
            status = "EXCEEDS_TOLERANCE"
        elif not overlap_pairs and lower == 0.0:
            status = "NONE"
        elif upper is not None and upper <= tolerance:
            status = "WITHIN_TOLERANCE"
        else:
            status = "UNRESOLVED"
        return {
            "penetration_depth_m": round(lower, 6),
            "penetration_upper_bound_m": (None if upper is None else round(upper, 6)),
            "penetration_status": status,
            "penetration_method": "mesh_inside_samples_and_directional_separation_bounds",
            "penetration_sample_count": samples,
        }

    def _mesh_connectivity(
        self,
        objects: list[dict[str, Any]],
        *,
        asset_diagonal: float,
        semantic_pairs: set[frozenset[str]] | None = None,
    ) -> dict[str, Any]:
        """Build a bidirectional evaluated-mesh contact graph.

        This is geometry evidence only: it detects obvious separated objects
        without assigning semantic part names or requiring registration tags.
        """

        count = len(objects)
        tolerance = max(float(asset_diagonal) * 0.005, 0.001)
        penetration_tolerance = max(float(asset_diagonal) * 0.01, 0.001)
        semantic_pairs = semantic_pairs or set()
        adjacency = [set() for _ in range(count)]
        nearest_surface = [math.inf] * count
        nearest_aabb = [math.inf] * count
        possible_pairs = count * (count - 1) // 2

        def aabb_distance(first: dict[str, Any], second: dict[str, Any]) -> float:
            squared = 0.0
            for axis in range(3):
                gap = max(
                    float(first["min"][axis]) - float(second["max"][axis]),
                    float(second["min"][axis]) - float(first["max"][axis]),
                    0.0,
                )
                squared += gap * gap
            return math.sqrt(squared)

        # A sweep-and-prune spatial index limits expensive BVH work to AABBs
        # that can possibly satisfy the unchanged surface-distance threshold.
        ordered = sorted(range(count), key=lambda index: objects[index]["min"][0])
        active: list[int] = []
        candidate_pairs: list[tuple[int, int, float]] = []
        for right in ordered:
            right_minimum = float(objects[right]["min"][0])
            active = [
                left
                for left in active
                if float(objects[left]["max"][0]) + tolerance >= right_minimum
            ]
            for left in active:
                distance = aabb_distance(objects[left], objects[right])
                identity = frozenset(
                    {
                        str(objects[left].get("registration_id")),
                        str(objects[right].get("registration_id")),
                    }
                )
                if distance <= tolerance or identity in semantic_pairs:
                    candidate_pairs.append((left, right, distance))
            active.append(right)

        # Preserve useful nearest-object evidence even for broad-phase rejects.
        # AABB distance is a conservative lower bound and is labelled separately.
        indexed_candidates = {(left, right) for left, right, _ in candidate_pairs}
        for left in range(count):
            for right in range(left + 1, count):
                distance = aabb_distance(objects[left], objects[right])
                nearest_aabb[left] = min(nearest_aabb[left], distance)
                nearest_aabb[right] = min(nearest_aabb[right], distance)
                identity = frozenset(
                    {
                        str(objects[left].get("registration_id")),
                        str(objects[right].get("registration_id")),
                    }
                )
                if (
                    identity in semantic_pairs
                    and (left, right) not in indexed_candidates
                ):
                    candidate_pairs.append((left, right, distance))
                    indexed_candidates.add((left, right))

        overlap_queries = 0
        nearest_queries = 0
        adaptive_sample_counts: list[int] = []
        contacts: list[dict[str, Any]] = []

        def adaptive_samples(item: dict[str, Any], gap: float) -> list[Any]:
            points = item["vertices"]
            if gap <= tolerance * 0.25:
                budget = 1024
            elif gap <= tolerance * 0.75:
                budget = 768
            else:
                budget = 512
            if len(points) <= budget:
                selected = points
            else:
                stride = max(1, len(points) // budget)
                selected = points[::stride]
                if selected[-1] is not points[-1]:
                    selected = [*selected, points[-1]]
            adaptive_sample_counts.append(len(selected))
            return selected

        for left, right, aabb_gap in candidate_pairs:
            first, second = objects[left], objects[right]
            overlap_queries += 1
            overlap_pairs = first["bvh"].overlap(second["bvh"])
            overlap_count = len(overlap_pairs)
            distance = 0.0 if overlap_count else math.inf
            if not overlap_count:
                for point in adaptive_samples(first, aabb_gap):
                    nearest_queries += 1
                    hit = second["bvh"].find_nearest(point)
                    if hit is not None:
                        distance = min(distance, float(hit[3]))
                for point in adaptive_samples(second, aabb_gap):
                    nearest_queries += 1
                    hit = first["bvh"].find_nearest(point)
                    if hit is not None:
                        distance = min(distance, float(hit[3]))
            nearest_surface[left] = min(nearest_surface[left], distance)
            nearest_surface[right] = min(nearest_surface[right], distance)
            if distance <= tolerance:
                adjacency[left].add(right)
                adjacency[right].add(left)
            penetration = (
                self._penetration_evidence(
                    first,
                    second,
                    overlap_pairs,
                    tolerance=penetration_tolerance,
                    asset_diagonal=asset_diagonal,
                )
                if overlap_count
                or all(
                    min(float(first["max"][axis]), float(second["max"][axis]))
                    > max(float(first["min"][axis]), float(second["min"][axis]))
                    for axis in range(3)
                )
                else {
                    "penetration_depth_m": 0.0,
                    "penetration_upper_bound_m": 0.0,
                    "penetration_status": "NONE",
                    "penetration_method": "no_intersecting_triangles",
                    "penetration_sample_count": 0,
                }
            )
            contacts.append(
                {
                    "left_island_id": first["island_id"],
                    "right_island_id": second["island_id"],
                    "left_registration_id": first.get("registration_id"),
                    "right_registration_id": second.get("registration_id"),
                    "left_part_id": first.get("part_id"),
                    "right_part_id": second.get("part_id"),
                    "aabb_distance_m": round(aabb_gap, 6),
                    "surface_distance_m": (
                        None if math.isinf(distance) else round(distance, 6)
                    ),
                    "within_tolerance": distance <= tolerance,
                    "overlap_triangle_pairs": overlap_count,
                    **penetration,
                }
            )

        components: list[list[int]] = []
        unseen = set(range(count))
        while unseen:
            pending = [unseen.pop()]
            component: list[int] = []
            while pending:
                current = pending.pop()
                component.append(current)
                neighbors = adjacency[current] & unseen
                unseen.difference_update(neighbors)
                pending.extend(neighbors)
            components.append(sorted(component))
        for component_index, component in enumerate(components):
            for index in component:
                objects[index]["contact_component"] = component_index
        isolated = [
            objects[index]["island_id"]
            for index, edges in enumerate(adjacency)
            if count > 1 and not edges
        ]
        return {
            "method": "evaluated_mesh_island_aabb_indexed_adaptive_contact_graph",
            "mesh_aware": True,
            "semantic_dependencies": True,
            "island_count": count,
            "contact_tolerance": round(tolerance, 6),
            "penetration_tolerance_m": round(penetration_tolerance, 6),
            "connected_component_count": len(components),
            "connected": count > 0 and len(components) == 1,
            "isolated_islands": isolated,
            "isolated_objects": isolated,
            "components": [
                [objects[index]["island_id"] for index in component]
                for component in components
            ],
            "contacts": contacts,
            "nearest_surface_distance_by_island": {
                item["island_id"]: (
                    0.0
                    if count == 1
                    else round(nearest_surface[index], 6)
                    if not math.isinf(nearest_surface[index])
                    else None
                )
                for index, item in enumerate(objects)
            },
            "nearest_aabb_distance_by_island": {
                item["island_id"]: (
                    0.0
                    if count == 1
                    else None
                    if math.isinf(nearest_aabb[index])
                    else round(nearest_aabb[index], 6)
                )
                for index, item in enumerate(objects)
            },
            "performance": {
                "possible_pair_count": possible_pairs,
                "candidate_pair_count": len(candidate_pairs),
                "broad_phase_rejection_count": (possible_pairs - len(candidate_pairs)),
                "bvh_overlap_query_count": overlap_queries,
                "nearest_query_count": nearest_queries,
                "adaptive_sample_count": sum(adaptive_sample_counts),
                "spatial_index": "x_axis_sweep_and_prune",
                "sampling": "gap_adaptive_bidirectional_vertices_512_768_1024",
            },
        }

    def _negative_space_metrics(
        self,
        openings: list[dict[str, Any]],
        islands: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Sample an entrance corridor, rejecting solids and unresolved volumes.

        Through probes have two exterior endpoints; cavity entrances need
        only one exterior endpoint and may terminate in a blind cavity. All
        evaluated asset islands can obstruct the corridor, not just its owner. This is sampled clearance,
        not a proof that every point in the swept cylinder is empty.
        """
        results = []

        def inside_bbox(point, minimum, maximum):
            return all(minimum[i] <= point[i] <= maximum[i] for i in range(3))

        def intersects_bbox(start, segment, minimum, maximum):
            lower, upper = 0.0, 1.0
            for axis in range(3):
                value = float(segment[axis])
                if abs(value) <= 1e-12:
                    if not minimum[axis] <= start[axis] <= maximum[axis]:
                        return False
                    continue
                first = (minimum[axis] - start[axis]) / value
                second = (maximum[axis] - start[axis]) / value
                lower, upper = (
                    max(lower, min(first, second)),
                    min(upper, max(first, second)),
                )
                if lower > upper:
                    return False
            return upper - lower > 1e-6

        for opening in openings:
            owner_id = opening.get("owner_registration_id")
            owners = [
                item for item in islands if item.get("registration_id") == owner_id
            ]
            record = {
                "feature_id": opening.get("feature_id", "unknown"),
                "owner_part_id": opening.get("owner_part_id"),
                "owner_registration_id": owner_id,
                "kind": opening.get("kind", "through_opening"),
                "obstruction_scope": "all_asset_islands",
                "bbox_span_valid": False,
                "sample_count": 0,
                "collision_count": 0,
                "status": "UNRESOLVED",
                "passed": False,
                "reason": "owner geometry or finite non-zero opening segment is unavailable",
            }
            results.append(record)
            try:
                start, end = (
                    self.Vector(opening["world_start"]),
                    self.Vector(opening["world_end"]),
                )
                radius = float(opening.get("clearance_radius_m", 0.0))
                segment = end - start
                length = float(segment.length)
                valid = all(math.isfinite(v) for v in (*start, *end, radius, length))
            except (KeyError, TypeError, ValueError):
                continue
            if not owners or not valid or length <= 1e-9 or radius < 0:
                continue
            minimum = [min(item["min"][axis] for item in owners) for axis in range(3)]
            maximum = [max(item["max"][axis] for item in owners) for axis in range(3)]
            intersects = intersects_bbox(start, segment, minimum, maximum)
            exterior = [
                not inside_bbox(point, minimum, maximum) for point in (start, end)
            ]
            kind = record["kind"]
            entrance = all(exterior) if kind == "through_opening" else any(exterior)
            record["bbox_span_valid"] = (
                intersects
                and entrance
                and kind in ("through_opening", "cavity_entrance")
            )
            direction = segment.normalized()
            axis = self.Vector((0, 1, 0) if abs(direction.z) > 0.9 else (0, 0, 1))
            u = direction.cross(axis).normalized()
            v = direction.cross(u).normalized()
            offsets = [self.Vector((0, 0, 0))]
            if radius > 0:
                offsets += [u * radius, -u * radius, v * radius, -v * radius]
            diagonal = (self.Vector(maximum) - self.Vector(minimum)).length
            epsilon = max(diagonal * 1e-7, 1e-8)
            unresolved = False
            for offset in offsets:
                origin = start + offset
                collision = False
                for island in islands:
                    hit = island["bvh"].ray_cast(origin, direction, length)[0]
                    if hit is not None:
                        collision = True
                        break
                    # A segment entirely within a solid hits no surface. Closed
                    # volume classification is therefore required as well.
                    relevant = intersects_bbox(
                        origin, segment, island["min"], island["max"]
                    )
                    if not relevant:
                        continue
                    if not island.get("closed"):
                        unresolved = True
                        continue
                    ray_distance = (
                        max(
                            length,
                            (
                                self.Vector(island["max"]) - self.Vector(island["min"])
                            ).length,
                        )
                        * 4
                        + 1
                    )
                    for fraction in (0.0, 0.5, 1.0):
                        point = origin + segment * fraction
                        nearest = island["bvh"].find_nearest(point)
                        if nearest[0] is not None and nearest[3] <= epsilon:
                            collision = True
                            break
                        inside = self._point_inside_closed_bvh(
                            island["bvh"],
                            point,
                            epsilon=epsilon,
                            ray_distance=ray_distance,
                        )
                        if inside is None:
                            unresolved = True
                        elif inside:
                            collision = True
                            break
                    if collision:
                        break
                record["collision_count"] += int(collision)
            record["sample_count"] = len(offsets)
            if record["collision_count"]:
                record.update(
                    status="BLOCKED",
                    reason="opening probe intersects a surface or lies inside solid asset geometry",
                )
            elif not record["bbox_span_valid"]:
                record["reason"] = (
                    "probe must span owner bounds: two exterior endpoints for through_opening, one for cavity_entrance"
                )
            elif unresolved or any(not item.get("closed") for item in owners):
                record["reason"] = (
                    "opening volume is unresolved for non-closed or ambiguous geometry"
                )
            else:
                record.update(status="CLEAR", passed=True, reason=None)
        return results

    def _mesh_topology_metrics(self, mesh: Any) -> dict[str, Any]:
        """Measure topology with bmesh when present and a Mesh API fallback."""

        if self.bmesh is not None:
            bm = self.bmesh.new()
            try:
                bm.from_mesh(mesh)
                face_aspects = []
                for face in bm.faces:
                    lengths = [edge.calc_length() for edge in face.edges]
                    positive = [length for length in lengths if length > 1e-12]
                    if positive:
                        face_aspects.append(max(positive) / min(positive))
                non_manifold = sum(
                    1
                    for edge in bm.edges
                    if not edge.is_manifold and not edge.is_boundary
                )
                boundary = sum(1 for edge in bm.edges if edge.is_boundary)
                loose = sum(1 for vertex in bm.verts if not vertex.link_edges)
                zero_area = sum(1 for face in bm.faces if face.calc_area() <= 1e-12)
            finally:
                bm.free()
        else:
            edge_faces = [0] * len(mesh.edges)
            vertex_edges = [0] * len(mesh.vertices)
            for edge in mesh.edges:
                for vertex_index in edge.vertices:
                    vertex_edges[vertex_index] += 1
            face_aspects = []
            for face in mesh.polygons:
                lengths = []
                for loop_index in face.loop_indices:
                    edge_index = mesh.loops[loop_index].edge_index
                    edge_faces[edge_index] += 1
                    edge = mesh.edges[edge_index]
                    first, second = edge.vertices
                    length = (mesh.vertices[first].co - mesh.vertices[second].co).length
                    if length > 1e-12:
                        lengths.append(length)
                if lengths:
                    face_aspects.append(max(lengths) / min(lengths))
            non_manifold = sum(count == 0 or count > 2 for count in edge_faces)
            boundary = sum(count == 1 for count in edge_faces)
            loose = sum(count == 0 for count in vertex_edges)
            zero_area = sum(face.area <= 1e-12 for face in mesh.polygons)
        ordered = sorted(face_aspects)

        mesh.calc_loop_triangles()
        triangle_qualities: list[float] = []
        triangle_minimum_angles: list[float] = []
        degenerate_triangles = 0
        for triangle in mesh.loop_triangles:
            points = [mesh.vertices[index].co for index in triangle.vertices]
            edges = [
                (points[1] - points[0]).length,
                (points[2] - points[1]).length,
                (points[0] - points[2]).length,
            ]
            area = (points[1] - points[0]).cross(points[2] - points[0]).length * 0.5
            squared_sum = sum(length * length for length in edges)
            if area <= 1e-12 or squared_sum <= 1e-24:
                degenerate_triangles += 1
                triangle_qualities.append(0.0)
                triangle_minimum_angles.append(0.0)
                continue
            quality = 4.0 * math.sqrt(3.0) * area / squared_sum
            angles = []
            for index in range(3):
                first = points[(index + 1) % 3] - points[index]
                second = points[(index + 2) % 3] - points[index]
                denominator = first.length * second.length
                cosine = float(first.dot(second)) / denominator
                angles.append(math.degrees(math.acos(max(-1.0, min(1.0, cosine)))))
            triangle_qualities.append(max(0.0, min(1.0, quality)))
            triangle_minimum_angles.append(min(angles))

        ordered_quality = sorted(triangle_qualities)
        ordered_angles = sorted(triangle_minimum_angles)

        def percentile(fraction: float) -> float:
            if not ordered:
                return 0.0
            return ordered[min(len(ordered) - 1, int(len(ordered) * fraction))]

        def ordered_percentile(values: list[float], fraction: float) -> float:
            if not values:
                return 0.0
            index = min(len(values) - 1, int((len(values) - 1) * fraction))
            return values[index]

        return {
            "non_manifold_edges": int(non_manifold),
            "boundary_edges": int(boundary),
            "loose_vertices": int(loose),
            "zero_area_faces": int(zero_area),
            "maximum_face_aspect": round(max(face_aspects, default=0.0), 6),
            "face_aspect_p95": round(percentile(0.95), 6),
            "face_aspect_p99": round(percentile(0.99), 6),
            "triangle_count": len(triangle_qualities),
            "degenerate_triangles": degenerate_triangles,
            "thin_triangles": sum(value < 0.1 for value in triangle_qualities),
            "triangle_quality_min": round(min(triangle_qualities, default=0.0), 6),
            "triangle_quality_p01": round(ordered_percentile(ordered_quality, 0.01), 6),
            "triangle_quality_p05": round(ordered_percentile(ordered_quality, 0.05), 6),
            "triangle_minimum_angle_degrees": round(
                min(triangle_minimum_angles, default=0.0), 6
            ),
            "triangle_minimum_angle_p01_degrees": round(
                ordered_percentile(ordered_angles, 0.01), 6
            ),
        }

    def asset_metrics(
        self,
        root: Any,
        *,
        spec: dict[str, Any] | None = None,
        runtime_seconds: float | None = None,
        telemetry: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        """Measure evaluated geometry in world coordinates."""

        metrics_started = time.monotonic()
        meshes = self._visible_meshes(root)
        depsgraph = self.bpy.context.evaluated_depsgraph_get()
        registry_errors: list[str] = []
        try:
            raw_registry = load_registry(root)
        except (TypeError, ValueError) as error:
            raw_registry = None
            registry_errors.append(str(error))
        if raw_registry is None:
            registrations: list[dict[str, Any]] = []
            attachments: list[dict[str, Any]] = []
            openings: list[dict[str, Any]] = []
            anchors: list[dict[str, Any]] = []
            material_regions: list[dict[str, Any]] = []
        else:
            registrations = raw_registry.get("registrations", [])
            attachments = raw_registry.get("attachments", [])
            openings = raw_registry.get("openings", [])
            anchors = raw_registry.get("anchors", [])
            material_regions = raw_registry.get("material_regions", [])
            if raw_registry.get("part_index_attribute") != PART_INDEX_ATTRIBUTE:
                registry_errors.append(
                    "part registry declares the wrong face attribute"
                )
            if not isinstance(registrations, list) or not registrations:
                registry_errors.append("part registry has no registrations")
                registrations = []
            if not isinstance(attachments, list):
                registry_errors.append("part registry attachments must be a list")
                attachments = []
            if not isinstance(openings, list):
                registry_errors.append("part registry openings must be a list")
                openings = []
            if not isinstance(anchors, list):
                registry_errors.append("part registry anchors must be a list")
                anchors = []
            if not isinstance(material_regions, list):
                registry_errors.append("part registry material regions must be a list")
                material_regions = []
        # Resolve author-time root-local probes after the factory lifecycle has
        # placed the asset. Keep metadata world coordinates aligned with meshes.
        self.bpy.context.view_layer.update()
        openings = [dict(item) for item in openings]
        for opening in openings:
            if "root_start" in opening and "root_end" in opening:
                opening["world_start"] = list(
                    root.matrix_world @ self.Vector(opening["root_start"])
                )
                opening["world_end"] = list(
                    root.matrix_world @ self.Vector(opening["root_end"])
                )
        registration_indices = [
            item.get("registration_index")
            for item in registrations
            if isinstance(item, dict)
        ]
        if any(
            not isinstance(index, int) or index <= 0 for index in registration_indices
        ):
            registry_errors.append(
                "part registration indices must be positive integers"
            )
        if len(set(registration_indices)) != len(registration_indices):
            registry_errors.append("part registration indices must be unique")
        registrations_by_index = {
            item["registration_index"]: item
            for item in registrations
            if isinstance(item, dict)
            and isinstance(item.get("registration_index"), int)
        }
        semantic_pairs = {
            frozenset(
                {
                    str(item.get("child_registration_id")),
                    str(item.get("parent_registration_id")),
                }
            )
            for item in attachments
            if isinstance(item, dict)
            and isinstance(item.get("child_registration_id"), str)
            and isinstance(item.get("parent_registration_id"), str)
        }
        minimum = [math.inf, math.inf, math.inf]
        maximum = [-math.inf, -math.inf, -math.inf]
        vertex_count = 0
        face_count = 0
        materials: set[str] = set()
        object_bounds: list[dict[str, Any]] = []
        object_mesh_metrics: list[dict[str, Any]] = []
        connectivity_geometry: list[dict[str, Any]] = []
        unmaterialized_meshes: list[str] = []
        uncovered_material_faces = 0
        part_material_faces: dict[str, dict[str, int]] = {}
        for obj in meshes:
            evaluated = obj.evaluated_get(depsgraph)
            material_slots = list(obj.material_slots)
            assigned_materials = [
                slot.material for slot in material_slots if slot.material is not None
            ]
            observed_instances = 1
            instance_evidence = []
            for modifier in obj.modifiers:
                if modifier.type == "ARRAY":
                    count = max(1, int(modifier.count))
                    observed_instances *= count
                    instance_evidence.append(
                        {"source": modifier.name, "kind": "array", "count": count}
                    )
            object_minimum = [math.inf, math.inf, math.inf]
            object_maximum = [-math.inf, -math.inf, -math.inf]
            for corner in evaluated.bound_box:
                world_corner = evaluated.matrix_world @ self.Vector(corner)
                for axis in range(3):
                    minimum[axis] = min(minimum[axis], world_corner[axis])
                    maximum[axis] = max(maximum[axis], world_corner[axis])
                    object_minimum[axis] = min(object_minimum[axis], world_corner[axis])
                    object_maximum[axis] = max(object_maximum[axis], world_corner[axis])
            object_bounds.append(
                {
                    "name": obj.name_full,
                    "min": [round(value, 6) for value in object_minimum],
                    "max": [round(value, 6) for value in object_maximum],
                }
            )
            evaluated_mesh = None
            try:
                evaluated_mesh = evaluated.to_mesh()
                vertex_count += len(evaluated_mesh.vertices)
                face_count += len(evaluated_mesh.polygons)
                mesh_metrics = {
                    "name": obj.name_full,
                    "raw_vertices": len(obj.data.vertices),
                    "raw_edges": len(obj.data.edges),
                    "raw_faces": len(obj.data.polygons),
                    "evaluated_vertices": len(evaluated_mesh.vertices),
                    "evaluated_edges": len(evaluated_mesh.edges),
                    "evaluated_faces": len(evaluated_mesh.polygons),
                    **self._mesh_topology_metrics(evaluated_mesh),
                    "observed_instances": observed_instances,
                    "instance_evidence": instance_evidence,
                    "materials": sorted(
                        material.name_full for material in assigned_materials
                    ),
                    "bbox_min": [round(value, 6) for value in object_minimum],
                    "bbox_max": [round(value, 6) for value in object_maximum],
                }
                uncovered = sum(
                    1
                    for polygon in evaluated_mesh.polygons
                    if polygon.material_index >= len(material_slots)
                    or material_slots[polygon.material_index].material is None
                )
                mesh_metrics["uncovered_material_faces"] = uncovered
                uncovered_material_faces += uncovered
                part_attribute = evaluated_mesh.attributes.get(PART_INDEX_ATTRIBUTE)
                if part_attribute is not None and part_attribute.domain == "FACE":
                    for polygon in evaluated_mesh.polygons:
                        index = int(part_attribute.data[polygon.index].value)
                        registration = registrations_by_index.get(index)
                        if registration is None:
                            continue
                        part_id = str(registration["part_id"])
                        material = (
                            material_slots[polygon.material_index].material
                            if polygon.material_index < len(material_slots)
                            else None
                        )
                        name = (
                            material.name_full
                            if material is not None
                            else "__unassigned__"
                        )
                        counts = part_material_faces.setdefault(part_id, {})
                        counts[name] = counts.get(name, 0) + 1
                if not assigned_materials:
                    unmaterialized_meshes.append(obj.name_full)
                object_mesh_metrics.append(mesh_metrics)
                if evaluated_mesh.vertices and evaluated_mesh.polygons:
                    connectivity_geometry.extend(
                        self._evaluated_mesh_islands(
                            obj,
                            evaluated,
                            evaluated_mesh,
                            registrations_by_index,
                        )
                    )
            finally:
                if evaluated_mesh is not None:
                    evaluated.to_mesh_clear()
            for material in assigned_materials:
                materials.add(material.name_full)

        if meshes:
            dimensions = [maximum[index] - minimum[index] for index in range(3)]
            bbox = {
                "min": [round(value, 6) for value in minimum],
                "max": [round(value, 6) for value in maximum],
                "width": round(dimensions[0], 6),
                "depth": round(dimensions[1], 6),
                "height": round(dimensions[2], 6),
            }
            connectivity_started = time.monotonic()
            if telemetry is not None:
                telemetry["evaluate"] = telemetry.get("evaluate", 0.0) + (
                    connectivity_started - metrics_started
                )
            structural = self._mesh_connectivity(
                connectivity_geometry,
                asset_diagonal=math.sqrt(sum(value * value for value in dimensions)),
                semantic_pairs=semantic_pairs,
            )
            negative_spaces = self._negative_space_metrics(
                openings, connectivity_geometry
            )
            if telemetry is not None:
                telemetry["connectivity"] = telemetry.get("connectivity", 0.0) + (
                    time.monotonic() - connectivity_started
                )
        else:
            bbox = {
                "min": None,
                "max": None,
                "width": 0.0,
                "depth": 0.0,
                "height": 0.0,
            }
            structural = None
            negative_spaces = self._negative_space_metrics(openings, [])
            if telemetry is not None:
                telemetry["evaluate"] = telemetry.get("evaluate", 0.0) + (
                    time.monotonic() - metrics_started
                )
        part_registry = {
            "available": raw_registry is not None,
            "valid": raw_registry is not None and not registry_errors,
            "errors": registry_errors,
            "registrations": registrations,
            "attachments": attachments,
            "openings": openings,
            "anchors": anchors,
            "material_regions": material_regions,
        }
        evaluated_islands = [
            {
                key: value
                for key, value in item.items()
                if key
                not in {
                    "bvh",
                    "vertices",
                    "face_centers",
                    "face_normals",
                    "min",
                    "max",
                    "name",
                }
            }
            for item in connectivity_geometry
        ]
        return {
            "object_count": len(self._hierarchy(root)),
            "mesh_count": len(meshes),
            "vertex_count": vertex_count,
            "face_count": face_count,
            "build_runtime_seconds": (
                None
                if runtime_seconds is None
                else round(max(0.0, float(runtime_seconds)), 6)
            ),
            "material_count": len(materials),
            "materials": sorted(materials),
            "unmaterialized_meshes": sorted(unmaterialized_meshes),
            "uncovered_material_faces": uncovered_material_faces,
            "objects": object_mesh_metrics,
            "bbox": bbox,
            "structural": structural,
            "part_registry": part_registry,
            "part_material_faces": part_material_faces,
            "evaluated_mesh_islands": evaluated_islands,
            "negative_spaces": negative_spaces,
        }

    def _point_at(self, obj: Any, target: Any) -> None:
        direction = self.Vector(target) - obj.location
        obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

    def _camera_space_bbox(
        self,
        camera: Any,
        minimum: Any,
        maximum: Any,
    ) -> dict[str, Any]:
        """Project all eight world AABB corners into camera-local space."""

        self.bpy.context.view_layer.update()
        inverse = camera.matrix_world.inverted()
        points = [
            inverse
            @ self.Vector(
                (
                    maximum.x if mask & 1 else minimum.x,
                    maximum.y if mask & 2 else minimum.y,
                    maximum.z if mask & 4 else minimum.z,
                )
            )
            for mask in range(8)
        ]
        local_minimum = [min(point[axis] for point in points) for axis in range(3)]
        local_maximum = [max(point[axis] for point in points) for axis in range(3)]
        return {
            "min": [round(float(value), 6) for value in local_minimum],
            "max": [round(float(value), 6) for value in local_maximum],
            "width": float(local_maximum[0] - local_minimum[0]),
            "height": float(local_maximum[1] - local_minimum[1]),
            "depth": float(local_maximum[2] - local_minimum[2]),
        }

    def _projected_bbox_evidence(
        self,
        camera: Any,
        minimum: Any,
        maximum: Any,
    ) -> dict[str, Any]:
        camera_bbox = self._camera_space_bbox(camera, minimum, maximum)
        frame = camera.data.view_frame(scene=self.bpy.context.scene)
        left, right = min(p.x for p in frame), max(p.x for p in frame)
        bottom, top = min(p.y for p in frame), max(p.y for p in frame)
        view_width, view_height = right - left, top - bottom
        horizontal = camera_bbox["width"] / view_width
        vertical = camera_bbox["height"] / view_height
        return {
            "camera_space_bbox": camera_bbox,
            "view_width": round(view_width, 6),
            "view_height": round(view_height, 6),
            "horizontal_fraction": round(horizontal, 6),
            "vertical_fraction": round(vertical, 6),
            "area_fraction": round(
                min(1.0, max(0.0, horizontal)) * min(1.0, max(0.0, vertical)),
                6,
            ),
        }

    def _fit_orthographic_camera(
        self,
        camera: Any,
        minimum: Any,
        maximum: Any,
        *,
        margin: float = 1.2,
        minimum_scale: float = 0.05,
    ) -> dict[str, Any]:
        camera_bbox = self._camera_space_bbox(camera, minimum, maximum)
        scene = self.bpy.context.scene
        scale = max(float(camera.data.ortho_scale), 1e-9)
        frame = camera.data.view_frame(scene=scene)
        unit_width = (max(p.x for p in frame) - min(p.x for p in frame)) / scale
        unit_height = (max(p.y for p in frame) - min(p.y for p in frame)) / scale
        required = max(
            camera_bbox["width"] / unit_width, camera_bbox["height"] / unit_height
        )
        camera.data.ortho_scale = max(required * margin, minimum_scale)
        # Center even shifted cameras using Blender's actual frame, not a
        # guessed sensor-fit/aspect convention.
        frame = camera.data.view_frame(scene=scene)
        frame_center = sum(frame, self.Vector((0, 0, 0))) / len(frame)
        box_center = [
            (camera_bbox["min"][i] + camera_bbox["max"][i]) / 2 for i in range(2)
        ]
        correction = self.Vector(
            (box_center[0] - frame_center.x, box_center[1] - frame_center.y, 0)
        )
        camera.location += camera.matrix_world.to_quaternion() @ correction
        return self._projected_bbox_evidence(camera, minimum, maximum)

    def _read_binary_mask(self, path: Path) -> dict[str, Any]:
        image = self.bpy.data.images.load(str(path), check_existing=False)
        try:
            width, height = int(image.size[0]), int(image.size[1])
            pixels = list(image.pixels[:])
            foreground = 0
            minimum_x, minimum_y = width, height
            maximum_x = maximum_y = -1
            for index in range(width * height):
                offset = index * 4
                luminance = (
                    float(pixels[offset])
                    + float(pixels[offset + 1])
                    + float(pixels[offset + 2])
                ) / 3.0
                if luminance <= 0.5:
                    continue
                foreground += 1
                x, y = index % width, index // width
                minimum_x, maximum_x = min(minimum_x, x), max(maximum_x, x)
                minimum_y, maximum_y = min(minimum_y, y), max(maximum_y, y)
            return {
                "foreground_pixels": foreground,
                "total_pixels": width * height,
                "coverage": round(foreground / (width * height), 6),
                "pixel_bbox": (
                    None
                    if foreground == 0
                    else [minimum_x, minimum_y, maximum_x, maximum_y]
                ),
            }
        finally:
            self.bpy.data.images.remove(image)

    def _render_focus_masks(
        self,
        *,
        target_names: str | list[str],
        output_dir: Path,
        stem: str,
    ) -> dict[str, Any]:
        """Render visible and target-only masks for a semantic part group."""

        scene = self.bpy.context.scene
        names = {target_names} if isinstance(target_names, str) else set(target_names)
        targets = {
            obj.name_full
            for obj in scene.objects
            if obj.type == "MESH" and obj.name_full in names
        }
        if targets != names or not targets:
            return {
                "available": False,
                "reason": "target mesh group is unavailable",
            }
        mesh_objects = [obj for obj in scene.objects if obj.type == "MESH"]
        original_engine = scene.render.engine
        original_filepath = scene.render.filepath
        original_film = scene.render.film_transparent
        original_colors = {obj.name_full: tuple(obj.color) for obj in mesh_objects}
        original_hidden = {obj.name_full: bool(obj.hide_render) for obj in mesh_objects}
        shading = scene.display.shading
        shading_values = {
            name: getattr(shading, name)
            for name in (
                "light",
                "color_type",
                "show_shadows",
                "show_cavity",
                "show_specular_highlight",
                "background_type",
                "background_color",
            )
            if hasattr(shading, name)
        }
        visible_path = output_dir / f"{stem}_mask_visible.png"
        potential_path = output_dir / f"{stem}_mask_potential.png"
        try:
            scene.render.engine = "BLENDER_WORKBENCH"
            scene.render.film_transparent = False
            if hasattr(shading, "light"):
                shading.light = "FLAT"
            if hasattr(shading, "color_type"):
                shading.color_type = "OBJECT"
            if hasattr(shading, "show_shadows"):
                shading.show_shadows = False
            if hasattr(shading, "show_cavity"):
                shading.show_cavity = False
            if hasattr(shading, "show_specular_highlight"):
                shading.show_specular_highlight = False
            if hasattr(shading, "background_type"):
                shading.background_type = "VIEWPORT"
            if hasattr(shading, "background_color"):
                shading.background_color = (0.0, 0.0, 0.0)
            for obj in mesh_objects:
                obj.color = (
                    (1.0, 1.0, 1.0, 1.0)
                    if obj.name_full in targets
                    else (
                        0.0,
                        0.0,
                        0.0,
                        1.0,
                    )
                )

            scene.render.filepath = str(visible_path)
            self.bpy.ops.render.render(write_still=True)
            visible = self._read_binary_mask(visible_path)

            for obj in mesh_objects:
                if obj.name_full not in targets:
                    obj.hide_render = True
            scene.render.filepath = str(potential_path)
            self.bpy.ops.render.render(write_still=True)
            potential = self._read_binary_mask(potential_path)
        finally:
            for obj in mesh_objects:
                obj.color = original_colors[obj.name_full]
                obj.hide_render = original_hidden[obj.name_full]
            for name, value in shading_values.items():
                setattr(shading, name, value)
            scene.render.engine = original_engine
            scene.render.filepath = original_filepath
            scene.render.film_transparent = original_film
        potential_pixels = int(potential["foreground_pixels"])
        visible_pixels = int(visible["foreground_pixels"])
        visibility_ratio = (
            min(1.0, visible_pixels / potential_pixels) if potential_pixels else 0.0
        )
        return {
            "available": True,
            "visible": {"filename": visible_path.name, **visible},
            "potential": {"filename": potential_path.name, **potential},
            "visibility_ratio": round(visibility_ratio, 6),
            "occlusion_ratio": round(1.0 - visibility_ratio, 6),
        }

    def _ground_material(self) -> Any:
        material = self.bpy.data.materials.new("__runner_ground_material")
        material.use_nodes = True
        principled = material.node_tree.nodes.get("Principled BSDF")
        if principled is not None:
            principled.inputs["Base Color"].default_value = (
                0.12,
                0.12,
                0.12,
                1,
            )
            principled.inputs["Roughness"].default_value = 0.75
        return material

    def setup_preview(self, metrics: dict[str, Any]) -> None:
        """Create an automatically framed camera and neutral three-point light."""

        bbox = metrics["bbox"]
        if bbox["min"] is None:
            raise RuntimeError("cannot set up preview camera for an asset without mesh")

        minimum = self.Vector(bbox["min"])
        maximum = self.Vector(bbox["max"])
        center = (minimum + maximum) * 0.5
        size = maximum - minimum
        diagonal = max(size.length, 0.1)

        self.bpy.ops.object.camera_add()
        camera = self.bpy.context.object
        camera.name = "__runner_camera"
        camera.data.type = "ORTHO"
        camera.data.ortho_scale = max(diagonal * 1.15, 0.25)
        camera.location = center + self.Vector((1.8, -2.4, 1.6)) * diagonal
        self._point_at(camera, center)
        self._fit_orthographic_camera(camera, minimum, maximum)
        self.bpy.context.scene.camera = camera

        # Calibrated against dark wood, brown organic material, navy fabric and
        # white reference surfaces at the preview size. The former 900/500/700 W
        # rig clipped all three colored assets to near-white. Scale energy and
        # emitter size together so exposure stays comparable across asset sizes.
        light_scale = diagonal / 0.3
        light_specs = [
            ("__runner_key", (2.5, -3.0, 4.0), 900.0, 4.0),
            ("__runner_fill", (-3.0, -1.5, 2.0), 500.0, 3.0),
            ("__runner_rim", (1.5, 2.5, 3.0), 700.0, 3.0),
        ]
        for name, direction, energy, area_size in light_specs:
            data = self.bpy.data.lights.new(name=name, type="AREA")
            data.energy = energy * 0.03 * light_scale**2
            data.shape = "DISK"
            data.size = area_size * light_scale
            light = self.bpy.data.objects.new(name, data)
            self.bpy.context.collection.objects.link(light)
            light.location = center + self.Vector(direction) * diagonal
            self._point_at(light, center)

        ground_size = max(size.x, size.y, diagonal) * 4.0
        self.bpy.ops.mesh.primitive_plane_add(
            size=ground_size,
            location=(
                center.x,
                center.y,
                minimum.z - max(diagonal * 0.005, 0.001),
            ),
        )
        ground = self.bpy.context.object
        ground.name = "__runner_ground"
        ground.data.materials.append(self._ground_material())

    def _select_asset(self, root: Any) -> None:
        self.bpy.ops.object.select_all(action="DESELECT")
        for obj in self._hierarchy(root):
            obj.hide_set(False)
            obj.select_set(True)
        self.bpy.context.view_layer.objects.active = root

    def export_glb(
        self, root: Any, path: Path, *, texture_resolution=2048, bake_samples=4
    ) -> dict:
        from inf_agent.execution.material_export import (
            MaterialExportSettings,
            export_glb,
        )

        return export_glb(
            self.bpy,
            self._visible_meshes(root),
            path,
            MaterialExportSettings(texture_resolution, bake_samples),
        )

    def save_blend(self, path: Path) -> None:
        result = self.bpy.ops.wm.save_as_mainfile(
            filepath=str(path), check_existing=False
        )
        if "FINISHED" not in result:
            raise RuntimeError(f"blend save did not finish: {result}")

    @staticmethod
    def _file_sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    def reopen_final_artifacts(
        self, *, glb_path: Path | None = None, blend_path: Path | None = None
    ) -> dict[str, Any]:
        """Open current files and measure usable target meshes, excluding the rig."""
        report = {
            "schema_version": "1.1",
            "success": True,
            "backend": "blender",
            "errors": [],
        }

        def measure(objects):
            meshes = [obj for obj in objects if obj.type == "MESH"]
            depsgraph = self.bpy.context.evaluated_depsgraph_get()
            vertices = faces = 0
            for obj in meshes:
                evaluated = obj.evaluated_get(depsgraph)
                mesh = evaluated.to_mesh()
                try:
                    vertices += len(mesh.vertices)
                    faces += len(mesh.polygons)
                finally:
                    evaluated.to_mesh_clear()
            if not meshes or vertices < 3 or faces < 1:
                raise RuntimeError(
                    "reopened artifact contains no usable target mesh faces"
                )
            return {"mesh_objects": len(meshes), "vertices": vertices, "faces": faces}

        for kind, path in (("glb", glb_path), ("blend", blend_path)):
            if path is None:
                continue
            try:
                if kind == "glb":
                    self.bpy.ops.wm.read_factory_settings(use_empty=True)
                    result = self.bpy.ops.import_scene.gltf(filepath=str(path))
                    objects = list(self.bpy.context.scene.objects)
                else:
                    result = self.bpy.ops.wm.open_mainfile(filepath=str(path))
                    name = self.bpy.context.scene.get("inf_agent_asset_root")
                    root = (
                        self.bpy.context.scene.objects.get(name)
                        if isinstance(name, str)
                        else None
                    )
                    if root is None or root.name.startswith("__runner_"):
                        raise RuntimeError(
                            "BLEND target asset root is missing; presentation geometry is not an asset"
                        )
                    objects = self._visible_meshes(root)
                if "FINISHED" not in result:
                    raise RuntimeError(
                        f"{kind.upper()} reopen did not finish: {result}"
                    )
                report[kind] = {
                    "sha256": self._file_sha256(path),
                    "reopened": True,
                    **measure(objects),
                }
            except Exception as error:
                report["success"] = False
                report["errors"].append(
                    f"{kind.upper()} reopen: {type(error).__name__}: {error}"
                )
        return report

    def render_preview(self, path: Path) -> None:
        self.bpy.context.scene.render.filepath = str(path)
        result = self.bpy.ops.render.render(write_still=True)
        if "FINISHED" not in result:
            raise RuntimeError(f"preview render did not finish: {result}")

    def render_review_views(
        self, metrics: dict[str, Any], output_dir: Path
    ) -> dict[str, float]:
        """Render semantic front/up evidence plus an opposite perspective."""

        bbox = metrics["bbox"]
        minimum = self.Vector(bbox["min"])
        maximum = self.Vector(bbox["max"])
        center = (minimum + maximum) * 0.5
        diagonal = max((maximum - minimum).length, 0.1)
        camera = self.bpy.context.scene.camera
        if camera is None:
            raise RuntimeError("preview camera is not configured")
        axis_vectors = {
            "+X": self.Vector((1.0, 0.0, 0.0)),
            "-X": self.Vector((-1.0, 0.0, 0.0)),
            "+Y": self.Vector((0.0, 1.0, 0.0)),
            "-Y": self.Vector((0.0, -1.0, 0.0)),
            "+Z": self.Vector((0.0, 0.0, 1.0)),
            "-Z": self.Vector((0.0, 0.0, -1.0)),
        }
        review_axes = metrics.get("review_axes")
        front_axis = (
            review_axes.get("front_axis") if isinstance(review_axes, dict) else None
        )
        up_axis = review_axes.get("up_axis") if isinstance(review_axes, dict) else None
        front = axis_vectors.get(front_axis, self.Vector((0.0, -1.0, 0.0)))
        up = axis_vectors.get(up_axis, self.Vector((0.0, 0.0, 1.0)))
        if abs(front.dot(up)) > 1e-6:
            raise RuntimeError("front_axis and up_axis must be orthogonal")
        side = front.cross(up).normalized()
        timings: dict[str, float] = {}
        offsets = {
            "front": front * 3.0 + up * 0.35,
            "side": side * 3.0 + up * 0.35,
            "top": up * 3.0,
            "opposite_perspective": -front * 2.2 + side * 1.7 + up * 1.4,
        }
        planned_ids = global_view_ids(
            {"review_view_plan": metrics.get("review_view_plan", [])}
        )
        if "bottom" in planned_ids or "bottom" in metrics.get("review_view_ids", []):
            offsets["bottom"] = -up * 3.0
        ground = self.bpy.data.objects.get("__runner_ground")
        for name, offset in offsets.items():
            camera.location = center + self.Vector(offset) * diagonal
            self._point_at(camera, center)
            self._fit_orthographic_camera(camera, minimum, maximum)
            started = time.monotonic()
            if name == "bottom" and ground is not None:
                ground.hide_render = True
            try:
                self.render_preview(output_dir / f"preview_{name}.png")
            finally:
                if name == "bottom" and ground is not None:
                    ground.hide_render = False
            timings[name] = time.monotonic() - started
        return timings

    def render_object_focus_views(
        self, metrics: dict[str, Any], output_dir: Path, *, limit: int = 8
    ) -> list[dict[str, Any]]:
        """Render bounded object-range views with geometry-backed framing facts."""

        camera = self.bpy.context.scene.camera
        if camera is None:
            raise RuntimeError("preview camera is not configured")
        selections = focus_selections(metrics, limit=limit)
        if not selections:
            metrics["focus_views"] = []
            return []

        original_location = camera.location.copy()
        original_rotation = camera.rotation_euler.copy()
        original_scale = camera.data.ortho_scale
        original_clip_start = float(camera.data.clip_start)
        records = []
        try:
            for view_id, selected, target_parts in selections:
                objects = selected
                if not objects:
                    continue
                minimum = self.Vector(
                    tuple(
                        min(item["bbox_min"][axis] for item in objects)
                        for axis in range(3)
                    )
                )
                maximum = self.Vector(
                    tuple(
                        max(item["bbox_max"][axis] for item in objects)
                        for axis in range(3)
                    )
                )
                center = (minimum + maximum) * 0.5
                diagonal = (maximum - minimum).length
                camera.location = center + self.Vector((1.5, -2.0, 1.2)) * max(
                    diagonal, 0.03
                )
                self._point_at(camera, center)
                camera.data.clip_start = min(
                    original_clip_start,
                    max(1e-5, diagonal * 0.01),
                )
                projection = self._fit_orthographic_camera(
                    camera,
                    minimum,
                    maximum,
                    minimum_scale=min(0.05, max(0.001, diagonal * 0.2)),
                )
                ortho_scale = float(camera.data.ortho_scale)
                filename = f"preview_{view_id}.png"
                render_started = time.monotonic()
                self.render_preview(output_dir / filename)
                render_seconds = time.monotonic() - render_started
                mask_started = time.monotonic()
                masks = self._render_focus_masks(
                    target_names=[item["name"] for item in objects],
                    output_dir=output_dir,
                    stem=Path(filename).stem,
                )
                mask_seconds = time.monotonic() - mask_started
                records.append(
                    {
                        "id": view_id,
                        "filename": filename,
                        "target_object": objects[0]["name"],
                        "target_objects": [item["name"] for item in objects],
                        "target_part_ids": target_parts,
                        "target_bbox": {
                            "min": [round(float(value), 6) for value in minimum],
                            "max": [round(float(value), 6) for value in maximum],
                        },
                        "camera_target": [round(value, 6) for value in center],
                        "ortho_scale": round(ortho_scale, 6),
                        "target_coverage_estimate": projection["area_fraction"],
                        "projected_bbox": projection,
                        "mask_evidence": masks,
                        "render_seconds": round(render_seconds, 6),
                        "mask_render_seconds": round(mask_seconds, 6),
                    }
                )
        finally:
            camera.location = original_location
            camera.rotation_euler = original_rotation
            camera.data.ortho_scale = original_scale
            camera.data.clip_start = original_clip_start
        metrics["focus_views"] = records
        return records
