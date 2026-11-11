"""Actual Blender regression probes; no fake geometry or camera projection oracle."""

import itertools
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from inf_agent.execution.blender import BlenderSession
from inf_agent.geometry import AssemblyBuilder


@unittest.skipUnless(
    os.environ.get("INF_AGENT_BLENDER_TESTS") == "1",
    "set INF_AGENT_BLENDER_TESTS=1 for actual Blender",
)
class GeometryAndNodeApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.session = BlenderSession()

    def setUp(self):
        self.s = self.session
        self.s.configure(
            render_engine="BLENDER_EEVEE_NEXT", resolution=(64, 64), samples=1
        )
        self.bpy = self.s.bpy

    def cube(self, size=1, location=(0, 0, 0)):
        self.bpy.ops.mesh.primitive_cube_add(size=size, location=location)
        return self.bpy.context.object

    def probe(
        self, obj, start, end, radius=0.002, blocker=None, kind="through_opening"
    ):
        self.bpy.context.view_layer.update()
        assembly = AssemblyBuilder()
        owner = assembly.register("body", obj)
        if blocker is not None:
            blocker.parent = obj
            assembly.register("blocker", blocker, parent_part_id="body")
        assembly.opening(
            "hole", owner, start=start, end=end, clearance_radius=radius, kind=kind
        )
        assembly.finalize(obj)
        return self.s.asset_metrics(obj)["negative_spaces"][0]

    def test_solid_internal_short_probe_fails(self):
        measured = self.probe(self.cube(), (-0.01, 0, 0), (0.01, 0, 0))
        self.assertFalse(measured["passed"], measured)
        self.assertEqual(measured["status"], "BLOCKED")

    def test_ring_opening_and_blocker_are_distinguished(self):
        for blocked in (False, True):
            with self.subTest(blocked=blocked):
                self.setUp()
                self.bpy.ops.mesh.primitive_torus_add(
                    major_radius=0.8, minor_radius=0.2
                )
                ring = self.bpy.context.object
                blocker = self.cube(size=0.2) if blocked else None
                measured = self.probe(ring, (0, 0, -0.3), (0, 0, 0.3), 0.05, blocker)
                self.assertEqual(measured["passed"], not blocked, measured)
                self.assertEqual(measured["status"], "BLOCKED" if blocked else "CLEAR")

    def test_probe_follows_final_root_placement_including_join(self):
        import math

        for joined in (False, True):
            with self.subTest(joined=joined):
                self.setUp()
                self.bpy.ops.mesh.primitive_torus_add(
                    major_radius=0.8, minor_radius=0.2, location=(0, 0, 0.2)
                )
                ring = self.bpy.context.object
                assembly = AssemblyBuilder()
                owner = assembly.register("body", ring)
                assembly.opening(
                    "hole",
                    owner,
                    start=(0, 0, -0.3),
                    end=(0, 0, 0.3),
                    clearance_radius=0.05,
                )
                if joined:
                    extra = self.cube(size=0.1, location=(0.8, 0, 0.6))
                    assembly.register("extra", extra)
                    ring = assembly.join_objects([ring, extra])
                else:
                    assembly.finalize(ring)
                ring.location = (3, -2, 1)
                ring.rotation_euler = (math.pi / 2, 0, 0)
                measured = self.s.asset_metrics(ring)["negative_spaces"][0]
                self.assertTrue(measured["passed"], measured)

    def test_blind_cavity_entrance_does_not_require_through_hole(self):
        body = self.cube(size=2)
        cutter = self.cube(size=1.5, location=(0, 0, 0.75))
        mod = body.modifiers.new("cavity", "BOOLEAN")
        mod.operation = "DIFFERENCE"
        mod.object = cutter
        cutter.hide_render = True
        self.bpy.context.view_layer.objects.active = body
        self.bpy.ops.object.modifier_apply(modifier=mod.name)
        measured = self.probe(
            body, (0, 0, 1.2), (0, 0, 0.2), radius=0.1, kind="cavity_entrance"
        )
        self.assertTrue(measured["passed"], measured)
        measured = self.probe(body, (0, 0, 1.2), (0, 0, 0.2), radius=0.1)
        self.assertFalse(measured["passed"], measured)

    def test_insufficient_and_degenerate_or_open_surface_probes_do_not_pass(self):
        self.bpy.ops.mesh.primitive_torus_add(major_radius=0.8, minor_radius=0.2)
        ring = self.bpy.context.object
        for start, end in [((0, 0, -0.01), (0, 0, 0.01)), ((0, 0, 0), (0, 0, 0))]:
            with self.subTest(start=start, end=end):
                # Bypass author-time validation to exercise the measurement boundary.
                assembly = AssemblyBuilder()
                owner = assembly.register("body", ring)
                opening = dict(
                    feature_id="hole",
                    owner_part_id="body",
                    owner_registration_id=owner,
                    world_start=list(start),
                    world_end=list(end),
                    clearance_radius_m=0.01,
                )
                registry = assembly.registry.as_dict()
                registry["openings"] = [opening]
                import json
                from inf_agent.geometry.assembly import REGISTRY_PROPERTY

                ring[REGISTRY_PROPERTY] = json.dumps(registry)
                result = self.s.asset_metrics(ring)["negative_spaces"][0]
                self.assertFalse(result["passed"], result)
                self.assertEqual(result["status"], "UNRESOLVED")
        self.setUp()
        self.bpy.ops.mesh.primitive_plane_add(size=1)
        result = self.probe(self.bpy.context.object, (0, 0, -1), (0, 0, 1))
        self.assertFalse(result["passed"])

    def assert_framed(self, camera, low, high):
        from bpy_extras.object_utils import world_to_camera_view

        self.bpy.context.view_layer.update()
        points = [
            world_to_camera_view(self.bpy.context.scene, camera, self.s.Vector(p))
            for p in itertools.product(*zip(low, high))
        ]
        for p in points:
            self.assertGreaterEqual(p.x, 0.079)
            self.assertLessEqual(p.x, 0.921)
            self.assertGreaterEqual(p.y, 0.079)
            self.assertLessEqual(p.y, 0.921)
            self.assertGreater(p.z, 0)
        return points

    def test_camera_fit_uses_actual_blender_frame(self):
        self.bpy.ops.object.camera_add(location=(5, -8, 4))
        camera = self.bpy.context.object
        camera.data.type = "ORTHO"
        self.s._point_at(camera, self.s.Vector((0, 0, 0)))
        scene = self.bpy.context.scene
        for width, height, px, py, fit in [
            (512, 128, 1, 1, "AUTO"),
            (128, 512, 1, 1, "AUTO"),
            (256, 256, 1, 1, "AUTO"),
            (128, 256, 2, 1, "HORIZONTAL"),
            (256, 128, 1, 2, "VERTICAL"),
        ]:
            for high in [(1, 1, 1), (6, 0.2, 0.1)]:
                with self.subTest(
                    size=(width, height), pixels=(px, py), fit=fit, high=high
                ):
                    scene.render.resolution_x, scene.render.resolution_y = width, height
                    scene.render.pixel_aspect_x, scene.render.pixel_aspect_y = px, py
                    camera.data.sensor_fit = fit
                    camera.data.shift_x, camera.data.shift_y = 0.15, -0.2
                    low = tuple(-v for v in high)
                    evidence = self.s._fit_orthographic_camera(
                        camera, self.s.Vector(low), self.s.Vector(high)
                    )
                    points = self.assert_framed(camera, low, high)
                    self.assertAlmostEqual(
                        max(p.x for p in points) - min(p.x for p in points),
                        evidence["horizontal_fraction"],
                        places=5,
                    )
                    self.assertAlmostEqual(
                        max(p.y for p in points) - min(p.y for p in points),
                        evidence["vertical_fraction"],
                        places=5,
                    )
                    self.assertLessEqual(
                        evidence["horizontal_fraction"], 1 / 1.2 + 1e-5
                    )
                    self.assertLessEqual(evidence["vertical_fraction"], 1 / 1.2 + 1e-5)

    def test_main_review_and_focus_views_all_refit(self):
        self.bpy.context.scene.render.resolution_x = 128
        self.bpy.context.scene.render.resolution_y = 512
        obj = self.cube()
        obj.scale = (5, 0.3, 0.1)
        self.bpy.context.view_layer.update()
        metrics = self.s.asset_metrics(obj)
        low, high = metrics["bbox"]["min"], metrics["bbox"]["max"]
        self.s.setup_preview(metrics)
        camera = self.bpy.context.scene.camera
        self.assert_framed(camera, low, high)
        metrics["review_axes"] = dict(front_axis="+Z", up_axis="+X")
        metrics["review_view_ids"] = ["bottom"]
        views = []

        def check(path):
            views.append(path.name)
            self.assert_framed(camera, low, high)

        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(self.s, "render_preview", side_effect=check),
            patch.object(self.s, "_render_focus_masks", return_value={}),
        ):
            self.s.render_review_views(metrics, Path(tmp))
            self.s.render_object_focus_views(metrics, Path(tmp))
        self.assertEqual(len(views), 6)

    def test_repeated_instances_use_real_contact_pair(self):
        from inf_agent.geometry.validation import evaluate_geometry_contract

        body = self.cube()
        first = self.cube(size=0.5, location=(0.75, 0, 0))
        second = self.cube(size=0.5, location=(1.25, 0, 0))
        first.parent = second.parent = body
        self.bpy.context.view_layer.update()
        assembly = AssemblyBuilder()
        parent = assembly.register("body", body)
        assembly.register("handle", first, parent_part_id="body")
        child = assembly.register("handle", second, parent_part_id="body")
        assembly.attach("mount", child, parent, kind="contact")
        assembly.finalize(body)
        metrics = self.s.asset_metrics(body)
        spec = dict(
            required_parts=[
                dict(part_id="body", minimum_count=1, maximum_count=1),
                dict(part_id="handle", minimum_count=2, maximum_count=2),
            ],
            attachment_constraints=[
                dict(
                    attachment_id="mount",
                    part_id="handle",
                    parent_part_id="body",
                    kind="contact",
                )
            ],
        )
        manifest = dict(
            parts=[
                dict(part_id="body", parent_part_id=None),
                dict(part_id="handle", parent_part_id="body"),
            ]
        )
        report = evaluate_geometry_contract(
            asset_spec=spec, part_manifest=manifest, metrics=metrics
        )
        self.assertTrue(metrics["structural"]["connected"])
        self.assertFalse(report["passed"])
        attachment = report["attachments"][0]
        self.assertFalse(attachment["touching"])
        self.assertAlmostEqual(attachment["gap_m"], 0.5, places=5)

    def test_documented_node_types_accept_actual_assignment(self):
        # Execute the actual maintained example rather than a copied version.
        doc = (
            Path(__file__).resolve().parents[1]
            / "modeling_docs/api_reference/node_api/socket_attrs_and_compatibility.md"
        )
        text = doc.read_text(encoding="utf-8").split("### 最小类型示例", 1)[1]
        code = text.split("```python", 1)[1].split("```", 1)[0]
        namespace = {}
        exec(compile(code, str(doc), "exec"), namespace)
        field_types = (
            "FLOAT",
            "INT",
            "FLOAT_VECTOR",
            "FLOAT_COLOR",
            "BOOLEAN",
            "QUATERNION",
            "FLOAT4X4",
        )
        for name, values in [
            ("named", field_types),
            ("captured", field_types),
            ("random", ("FLOAT", "INT", "FLOAT_VECTOR", "BOOLEAN")),
            ("mix", ("FLOAT", "VECTOR", "RGBA")),
        ]:
            node = namespace[name]
            for value in values:
                node.data_type = value
                self.assertEqual(node.data_type, value)
        with self.assertRaises(TypeError):
            namespace["named"].data_type = "RGBA"
        with self.assertRaises(TypeError):
            namespace["mix"].data_type = "FLOAT_VECTOR"
        with self.assertRaises(TypeError):
            namespace["mix"].data_type = "ROTATION"
        geometry_mix = namespace["geo"].nodes.new("ShaderNodeMix")
        for value in ("FLOAT", "VECTOR", "RGBA", "ROTATION"):
            geometry_mix.data_type = value
            self.assertEqual(geometry_mix.data_type, value)
        self.bpy.data.node_groups.remove(namespace["geo"])
        self.bpy.data.node_groups.remove(namespace["shader"])


if __name__ == "__main__":
    unittest.main()
