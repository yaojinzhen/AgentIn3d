"""Actual current-file validation: no mocked Blender reopen or image evidence."""

import os
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from test_asset_workflow_blender import CUBE, TORUS
from inf_agent.execution.blender import BlenderSession
from inf_agent.execution.service import run_workspace, validate_run
from inf_agent.workspace.contracts import load_json, write_json_atomic
from inf_agent.workspace.manager import create_workspace


@unittest.skipUnless(
    os.environ.get("INF_AGENT_BLENDER_TESTS") == "1",
    "set INF_AGENT_BLENDER_TESTS=1 for actual Blender",
)
class ArtifactIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="inf_agent_artifact_integrity_")
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name) / "asset"
        create_workspace(self.workspace, prompt="a blue object")
        (self.workspace / "asset.py").write_text(CUBE, encoding="utf-8")

    def test_preview_blend_is_reopened_and_current_corruption_is_rejected(self):
        result = run_workspace(self.workspace, render=False)
        self.assertTrue(result["objective_success"], result)
        run = Path(result["run"])
        proof = load_json(run / "artifact_reopen.json")
        self.assertEqual(proof["backend"], "blender")
        self.assertGreater(proof["blend"]["faces"], 0)
        self.assertNotIn("glb", proof)
        original = (run / "scene.blend").read_bytes()
        for payload in (b"BLENDER-v402", original[:128]):
            with self.subTest(bytes=len(payload)):
                (run / "scene.blend").write_bytes(payload)
                failed = validate_run(run)
                self.assertTrue(failed["execution_success"])
                self.assertFalse(failed["objective_success"])
                self.assertIn("artifacts", failed["failure_domains"])
        (run / "scene.blend").write_bytes(original)
        self.assertTrue(validate_run(run)["objective_success"])

    def test_ground_only_blend_cannot_replace_target_asset(self):
        result = run_workspace(self.workspace, render=False)
        self.assertTrue(result["objective_success"], result)
        run = Path(result["run"])
        session = BlenderSession()
        bpy = session.bpy
        bpy.ops.wm.open_mainfile(filepath=str(run / "scene.blend"))
        name = bpy.context.scene["inf_agent_asset_root"]
        target = bpy.data.objects[name]
        for obj in [*target.children_recursive, target]:
            bpy.data.objects.remove(obj, do_unlink=True)
        self.assertIsNotNone(bpy.data.objects.get("__runner_ground"))
        bpy.ops.wm.save_as_mainfile(filepath=str(run / "scene.blend"))
        failed = validate_run(run)
        self.assertFalse(failed["objective_success"])
        self.assertTrue(
            any("target asset root" in error for error in failed["errors"]), failed
        )

    def test_all_declared_views_and_masks_are_required_current_files(self):
        (self.workspace / "asset.py").write_text(TORUS, encoding="utf-8")
        write_json_atomic(
            self.workspace / "design.json",
            dict(
                required_parts=[dict(part_id="body")],
                required_openings_or_negative_spaces=[
                    dict(feature_id="center_hole", owner_part_id="body")
                ],
                material_regions=[
                    dict(
                        region_id="blue_body",
                        part_ids=["body"],
                        semantics="blue plastic",
                    )
                ],
                review_view_plan=[
                    dict(view_id="bottom"),
                    dict(view_id="hole_detail", target_part_ids=["body"]),
                ],
            ),
        )
        result = run_workspace(self.workspace, resolution=(64, 64), samples=1)
        self.assertTrue(result["objective_success"], result)
        run = Path(result["run"])
        health = load_json(run / "objective_validation.json")["layers"][
            "artifact_validation"
        ]
        self.assertTrue(health["focus_evidence"]["success"])
        self.assertEqual(len(health["expected_outputs"]), 10)
        for filename in (
            "opposite_perspective.png",
            "bottom.png",
            "hole_detail.png",
            "hole_detail_mask_visible.png",
            "hole_detail_mask_potential.png",
        ):
            with self.subTest(filename=filename):
                path = run / "previews" / filename
                original = path.read_bytes()
                path.unlink()
                failed = validate_run(run)
                self.assertFalse(failed["objective_success"])
                self.assertIn("artifacts", failed["failure_domains"])
                path.write_bytes(original)
        mask = run / "previews/hole_detail_mask_visible.png"
        Image.new("RGB", (64, 64), "black").save(mask)
        failed = validate_run(run)
        self.assertFalse(failed["objective_success"])
        proof = load_json(run / "objective_validation.json")["layers"][
            "artifact_validation"
        ]
        self.assertTrue(proof["files_usable"])
        self.assertFalse(proof["focus_evidence"]["success"])

    def test_actual_module_not_found_keeps_structured_root_cause(self):
        (self.workspace / "asset.py").write_text(
            "import missing_asset_test_dependency\n" + CUBE, encoding="utf-8"
        )
        failed = run_workspace(self.workspace, render=False)
        self.assertFalse(failed["execution_success"])
        self.assertEqual(failed["error"]["type"], "ModuleNotFoundError")
        self.assertIn("missing_asset_test_dependency", failed["error"]["message"])
        self.assertIn("environment", failed["failure_domains"])
        raw = load_json(Path(failed["run"]) / "validation.json")
        self.assertEqual(raw["error"], failed["error"])
        self.assertEqual(failed["process"]["returncode"], 1)
