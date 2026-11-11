"""Opt-in tests of actual current-code Blender construction, render and export."""

import os
import tempfile
import unittest
from pathlib import Path
from inf_agent.execution.service import run_workspace, validate_run
from inf_agent.workspace.contracts import load_json, write_json_atomic
from inf_agent.workspace.manager import create_workspace

CUBE = """import math
import bpy
from infinigen.core.placement.factory import AssetFactory
TAU = math.tau * 1.0
class LocalBase(AssetFactory):
    pass
class FruitFactoryApple(LocalBase):
    def create_asset(self, **params):
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0,0,0.5))
        obj = bpy.context.object
        material = bpy.data.materials.new('Blue')
        material.diffuse_color = (0.03,0.15,0.8,1)
        obj.data.materials.append(material)
        return obj
"""
TORUS = """import bpy
from infinigen.core.placement.factory import AssetFactory
from inf_agent.geometry import AssemblyBuilder
class RingFactory(AssetFactory):
    def create_asset(self, **params):
        bpy.ops.mesh.primitive_torus_add(major_radius=0.8, minor_radius=0.2, major_segments=32, minor_segments=12, location=(0,0,0.2))
        obj = bpy.context.object
        material = bpy.data.materials.new('Blue')
        material.diffuse_color = (0.02,0.12,0.8,1)
        obj.data.materials.append(material)
        assembly = AssemblyBuilder()
        part = assembly.register('body', obj, role='primary_shell')
        assembly.opening('center_hole', part, start=(0,0,-0.25), end=(0,0,0.25), clearance_radius=0.05)
        assembly.material_region('blue_body', ['body'], material.name)
        assembly.finalize(obj)
        return obj
"""


@unittest.skipUnless(
    os.environ.get("INF_AGENT_BLENDER_TESTS") == "1",
    "set INF_AGENT_BLENDER_TESTS=1 for actual Blender",
)
class BlenderCoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="inf_agent_blender_core_")
        self.addCleanup(self.tmp.cleanup)
        self.workspace = Path(self.tmp.name) / "object"
        create_workspace(self.workspace, prompt="a blue static object")

    def source(self, code):
        (self.workspace / "asset.py").write_text(code, encoding="utf-8")

    def test_indirect_factory_exports_and_reopens_without_approval(self):
        self.source(CUBE)
        result = run_workspace(self.workspace, export_glb=True, render=False)
        self.assertTrue(result["objective_success"], result)
        self.assertIn("glb", result["artifacts"])
        proof = load_json(Path(result["run"]) / "artifact_reopen.json")
        self.assertTrue(proof["success"])
        self.assertEqual(result["visual_status"], "NOT_CHECKED")
        repeated = run_workspace(self.workspace, export_glb=True, render=False)
        self.assertTrue(repeated["objective_success"], repeated)
        first = load_json(Path(result["run"]) / "metadata.json")["asset"]
        second = load_json(Path(repeated["run"]) / "metadata.json")["asset"]
        self.assertEqual(first["bbox"], second["bbox"])
        self.assertEqual(first["vertex_count"], second["vertex_count"])

    def test_opening_material_region_and_part_focus_are_measured(self):
        self.source(TORUS)
        design = {
            "required_parts": [{"part_id": "body", "role": "primary_shell"}],
            "required_openings_or_negative_spaces": [
                {"feature_id": "center_hole", "owner_part_id": "body"}
            ],
            "material_regions": [
                {
                    "region_id": "blue_body",
                    "part_ids": ["body"],
                    "semantics": "blue plastic",
                }
            ],
            "review_view_plan": [
                {"view_id": "hole_detail", "target_part_ids": ["body"]}
            ],
        }
        write_json_atomic(self.workspace / "design.json", design)
        result = run_workspace(
            self.workspace, export_glb=True, resolution=(64, 64), samples=1
        )
        self.assertTrue(result["objective_success"], result)
        health = load_json(Path(result["run"]) / "objective_validation.json")
        geometry = health["layers"]["geometry_and_assembly"]
        self.assertTrue(geometry["negative_spaces"][0]["passed"])
        self.assertTrue(geometry["material_regions"][0]["passed"])
        self.assertTrue((Path(result["run"]) / "previews/hole_detail.png").is_file())
        self.assertTrue(validate_run(result["run"])["objective_success"])

    def test_anchored_multipart_assembly_remains_measurable(self):
        self.source("""import bpy
from infinigen.core.placement.factory import AssetFactory
from inf_agent.geometry import AssemblyBuilder, LocalFrame
class AssemblyFactory(AssetFactory):
    def create_asset(self, **params):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0,0,0.5))
        body = bpy.context.object
        bpy.ops.mesh.primitive_cube_add(size=0.4, location=(0,0,1.2))
        cap = bpy.context.object
        cap.parent = body
        material = bpy.data.materials.new('Blue')
        material.diffuse_color = (0.02,0.12,0.8,1)
        for obj in (body,cap):
            obj.data.materials.append(material)
        assembly = AssemblyBuilder()
        parent = assembly.register('body', body)
        child = assembly.register('cap', cap, parent_part_id='body')
        assembly.anchor(parent, 'mount', LocalFrame(origin=(0,0,0.5)))
        assembly.anchor(child, 'base', LocalFrame(origin=(0,0,-0.2)))
        assembly.attach('cap_mount',child,parent,kind='contact',child_anchor_id='base',parent_anchor_id='mount')
        assembly.material_region('blue_parts',['body','cap'],material.name)
        assembly.finalize(body)
        return body
""")
        write_json_atomic(
            self.workspace / "design.json",
            {
                "required_parts": [
                    {"part_id": "body"},
                    {"part_id": "cap", "parent_part_id": "body"},
                ],
                "attachment_constraints": [
                    {
                        "attachment_id": "cap_mount",
                        "part_id": "cap",
                        "parent_part_id": "body",
                        "kind": "contact",
                        "require_anchors": True,
                    }
                ],
                "material_regions": [
                    {"region_id": "blue_parts", "part_ids": ["body", "cap"]}
                ],
            },
        )
        result = run_workspace(self.workspace, render=False)
        self.assertTrue(result["objective_success"], result)
        report = load_json(Path(result["run"]) / "objective_validation.json")["layers"][
            "geometry_and_assembly"
        ]
        self.assertTrue(report["attachments"][0]["passed"])
        self.assertTrue(report["material_regions"][0]["passed"])

    def test_failed_build_can_be_repaired_without_state_recovery(self):
        self.source(
            CUBE.replace(
                "bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0,0,0.5))",
                "raise RuntimeError('intentional build failure')",
            )
        )
        failed = run_workspace(self.workspace, render=False)
        self.assertFalse(failed["execution_success"])
        self.source(CUBE)
        fixed = run_workspace(self.workspace, render=False)
        self.assertTrue(fixed["objective_success"], fixed)


if __name__ == "__main__":
    unittest.main()
