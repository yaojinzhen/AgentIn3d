"""Observable execution, design and reliability behavior of the simplified workflow."""

from __future__ import annotations
import concurrent.futures
import contextlib
import copy
import hashlib
import io
import json
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image

from inf_agent.cli import main
from inf_agent.execution.blender import BlenderSession
from inf_agent.execution.process import ProcessError, ProcessRequest, run_process
from inf_agent.execution.resource_policy import (
    ResourceLimitError,
    ResourcePolicy,
    enforce_complexity_budget,
)
from inf_agent.execution.service import run_workspace, validate_run
from inf_agent.knowledge.resolver import read_knowledge
from inf_agent.knowledge.verification import inspect_source
from inf_agent.quality import evaluate_proportions
from inf_agent.workspace.contracts import (
    ContractError,
    load_json,
    normalize_design,
    write_json_atomic,
)
from inf_agent.workspace.manager import (
    allocate_run,
    create_workspace,
    read_workspace,
    workspace_status,
)


class TemporaryCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="inf_agent_core_")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.workspace = self.root / "asset"

    def start(self):
        create_workspace(self.workspace, prompt="a blue object")
        (self.workspace / "asset.py").write_text(
            "import math\nTAU = math.tau * 1.0\n", encoding="utf-8"
        )
        return self.workspace


def valid_metrics():
    return {
        "mesh_count": 1,
        "object_count": 1,
        "vertex_count": 8,
        "face_count": 6,
        "material_count": 1,
        "unmaterialized_meshes": [],
        "uncovered_material_faces": 0,
        "bbox": {"width": 1.0, "depth": 1.0, "height": 1.0},
        "objects": [
            {
                "name": "body",
                "bbox_min": [0, 0, 0],
                "bbox_max": [1, 1, 1],
                "evaluated_vertices": 8,
                "evaluated_faces": 6,
                "evaluated_edges": 12,
                "non_manifold_edges": 0,
                "zero_area_faces": 0,
                "loose_vertices": 0,
            }
        ],
        "structural": {"connected": True, "contacts": []},
    }


def fake_run(request, **kwargs):
    """Test process wiring with explicitly mock reopen evidence, never real bpy."""
    from artifact_fixtures import triangle, glb_bytes
    from inf_agent.execution.view_plan import expected_outputs
    from inf_agent.execution.artifact_validation import (
        validate_glb,
        ArtifactValidationError,
    )

    config = load_json(Path(request.command[-1]))
    output, options = Path(config["output_dir"]), config["parameters"]
    if "inf_agent.execution.reopen_artifacts" in request.command:
        report = dict(
            schema_version="1.1", success=True, backend="mock_fixture", errors=[]
        )
        for kind, name in (("blend", "scene.blend"), ("glb", "asset.glb")):
            if not options["save_blend" if kind == "blend" else "export_glb"]:
                continue
            path = output / name
            try:
                if kind == "blend" and path.read_bytes() != b"BLENDER-v402fixture":
                    raise ValueError("mock fixture BLEND is not intact")
                if kind == "glb":
                    validate_glb(path)
                report[kind] = dict(
                    sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    mesh_objects=1,
                    vertices=3,
                    faces=1,
                    reopened=True,
                )
            except (OSError, ValueError, ArtifactValidationError) as error:
                report["success"] = False
                report["errors"].append(str(error))
        write_json_atomic(output / "artifact_reopen.json", report)
        return subprocess.CompletedProcess(
            request.command, 0 if report["success"] else 1
        )
    metrics = valid_metrics()
    outputs = expected_outputs(
        config["design"],
        metrics,
        render=options["render"] == "image",
        save_blend=options["save_blend"],
        export_glb=options["export_glb"],
    )
    metrics["expected_outputs"] = outputs
    metrics["focus_views"] = [
        dict(id=item["id"], target_part_ids=item["target_part_ids"])
        for item in outputs
        if item["kind"] == "png" and "target_part_ids" in item
    ]
    write_json_atomic(output / "metadata.json", {"asset": metrics})
    write_json_atomic(output / "validation.json", {"success": True, "errors": []})
    (output / "run.log").write_text("asset run succeeded\n", encoding="utf-8")
    if options["save_blend"]:
        (output / "scene.blend").write_bytes(b"BLENDER-v402fixture")
    for item in outputs:
        if item["kind"] in ("png", "mask"):
            path = output / item["path"]
            path.parent.mkdir(exist_ok=True)
            Image.new(
                "RGB",
                tuple(options["resolution"]),
                "white" if item["kind"] == "mask" else "blue",
            ).save(path)
    if options["export_glb"]:
        (output / "asset.glb").write_bytes(glb_bytes(*triangle()))
    return subprocess.CompletedProcess(request.command, 0)


class WorkspaceTests(TemporaryCase):
    def test_same_prompt_can_create_independent_workspaces(self):
        self.start()
        create_workspace(self.root / "second", prompt="a blue object")
        self.assertTrue((self.root / "second/asset.py").is_file())
        self.assertFalse((self.root / ".workspace_registry.json").exists())

    def test_existing_workspace_is_not_overwritten(self):
        self.start()
        source = (self.workspace / "asset.py").read_bytes()
        with self.assertRaises(ContractError):
            create_workspace(self.workspace, prompt="replacement")
        self.assertEqual((self.workspace / "asset.py").read_bytes(), source)

    def test_invalid_dimensions_do_not_create_workspace(self):
        for value in [float("inf"), float("nan"), -1, True]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                create_workspace(
                    self.workspace, prompt="object", dimensions={"width": value}
                )
            self.assertFalse(self.workspace.exists())

    def test_invalid_reference_does_not_create_workspace(self):
        image = self.root / "bad.png"
        image.write_bytes(b"bad image")
        with self.assertRaises(ValueError):
            create_workspace(self.workspace, prompt="object", image=image)
        self.assertFalse(self.workspace.exists())

    def test_extra_files_and_revised_request_are_allowed(self):
        self.start()
        (self.workspace / "notes.txt").write_text("notes")
        request = load_json(self.workspace / "request.json")
        request["prompt"] = "a revised object"
        write_json_atomic(self.workspace / "request.json", request)
        self.assertEqual(
            read_workspace(self.workspace)[1]["prompt"].strip(), "a revised object"
        )

    def test_simple_asset_has_no_required_part_registry(self):
        self.start()
        _, _, design = read_workspace(self.workspace)
        self.assertEqual(design["required_parts"], [])

    def test_concurrent_run_allocation_never_reuses_directories(self):
        self.start()
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            paths = list(pool.map(lambda _: allocate_run(self.workspace), range(16)))
        self.assertEqual(len(set(paths)), 16)


class DesignTests(unittest.TestCase):
    def test_normalization_does_not_modify_caller(self):
        design = {"required_parts": [{"part_id": "body"}]}
        original = copy.deepcopy(design)
        normalized = normalize_design(design)
        self.assertEqual(design, original)
        self.assertEqual(normalized["required_parts"][0]["minimum_count"], 1)

    def test_declared_constraints_need_real_references(self):
        for design in [
            {"front_axis": "+Z", "up_axis": "+Z"},
            {
                "required_parts": [
                    {"part_id": "body", "minimum_count": 2, "maximum_count": 1}
                ]
            },
            {"required_parts": [{"part_id": "body"}, {"part_id": "body"}]},
            {
                "attachment_constraints": [
                    {
                        "attachment_id": "join",
                        "part_id": "missing",
                        "parent_part_id": "body",
                    }
                ]
            },
            {"review_view_plan": [{"view_id": "../../other", "target_part_ids": []}]},
            {
                "required_openings_or_negative_spaces": [
                    {"feature_id": "hole", "owner_part_id": "missing"}
                ]
            },
            {"expected_bbox_or_ratio_ranges": {"width_to_height": [2, 1]}},
        ]:
            with self.subTest(design=design), self.assertRaises(ContractError):
                normalize_design(design)

    def test_parent_cycles_are_rejected(self):
        with self.assertRaisesRegex(ContractError, "cycle"):
            normalize_design(
                {
                    "required_parts": [
                        {"part_id": "a", "parent_part_id": "b"},
                        {"part_id": "b", "parent_part_id": "a"},
                    ]
                }
            )

    def test_dimension_ratios_remain_measured(self):
        result = evaluate_proportions(
            {"expected_bbox_or_ratio_ranges": {"width_to_height": [0.8, 1.2]}},
            {"width": 2, "depth": 1, "height": 1},
        )
        self.assertFalse(result["passed"])


class WorkflowTests(TemporaryCase):
    @patch("inf_agent.execution.service.run_process", side_effect=fake_run)
    def test_more_than_three_runs_can_export_without_review_or_receipts(self, process):
        self.start()
        results = [
            run_workspace(self.workspace, seed=i, export_glb=True, render=False)
            for i in range(5)
        ]
        self.assertEqual(
            sum(
                "inf_agent.execution.run_asset" in call.args[0].command
                for call in process.call_args_list
            ),
            5,
        )
        self.assertTrue(all(x["objective_success"] for x in results), results)
        self.assertEqual(len({x["run"] for x in results}), 5)
        self.assertTrue(
            all(
                "glb" in x["artifacts"] and x["visual_status"] == "NOT_CHECKED"
                for x in results
            )
        )
        self.assertEqual(workspace_status(self.workspace)["run_count"], 5)

    @patch("inf_agent.execution.service.run_process", side_effect=fake_run)
    def test_preview_has_decodable_views_without_semantic_manifests(self, process):
        self.start()
        result = run_workspace(self.workspace, resolution=(64, 64))
        self.assertTrue(result["objective_success"], result)
        self.assertEqual(len(result["previews"]), 6)
        self.assertNotIn("glb", result["artifacts"])

    @patch("inf_agent.execution.service.run_process", side_effect=fake_run)
    def test_source_and_design_changes_are_snapshotted_each_run(self, process):
        self.start()
        first = run_workspace(self.workspace, render=False)
        (self.workspace / "asset.py").write_text("VALUE = 2\n")
        write_json_atomic(
            self.workspace / "design.json",
            {"expected_bbox_or_ratio_ranges": {"width_to_height": [0.9, 1.1]}},
        )
        second = run_workspace(self.workspace, render=False)
        self.assertTrue(second["objective_success"], second)
        self.assertNotEqual(
            (Path(first["run"]) / "input/source/asset.py").read_bytes(),
            (Path(second["run"]) / "input/source/asset.py").read_bytes(),
        )
        self.assertEqual(
            load_json(Path(first["run"]) / "input/config.json")["design"][
                "expected_bbox_or_ratio_ranges"
            ],
            {},
        )

    @patch("inf_agent.execution.service.run_process", side_effect=fake_run)
    def test_corrupt_export_is_detected_on_revalidation(self, process):
        self.start()
        result = run_workspace(self.workspace, export_glb=True, render=False)
        Path(result["artifacts"]["glb"]).write_bytes(b"corrupt")
        self.assertFalse(validate_run(result["run"])["objective_success"])

    @patch("inf_agent.execution.service.run_process", side_effect=fake_run)
    def test_corrupt_png_is_detected_even_with_valid_metrics(self, process):
        self.start()
        result = run_workspace(self.workspace, resolution=(64, 64))
        (Path(result["run"]) / "previews/front.png").write_bytes(b"bad PNG")
        self.assertFalse(validate_run(result["run"])["objective_success"])

    @patch("inf_agent.execution.service.run_process", side_effect=fake_run)
    def test_objective_failure_does_not_hide_existing_export_paths(self, process):
        self.start()
        result = run_workspace(self.workspace, export_glb=True, render=False)
        metadata_path = Path(result["run"]) / "metadata.json"
        metadata = load_json(metadata_path)
        metadata["asset"]["material_count"] = 0
        write_json_atomic(metadata_path, metadata)
        failed = validate_run(result["run"])
        self.assertFalse(failed["objective_success"])
        self.assertIn("glb", failed["artifacts"])
        self.assertIn("material_semantics", failed["failure_domains"])

    def test_process_failure_keeps_result_and_next_run_can_continue(self):
        self.start()
        with patch(
            "inf_agent.execution.service.run_process",
            side_effect=ProcessError("timeout"),
        ):
            failed = run_workspace(self.workspace, render=False)
        self.assertFalse(failed["execution_success"])
        self.assertTrue((Path(failed["run"]) / "result.json").is_file())
        with patch("inf_agent.execution.service.run_process", side_effect=fake_run):
            result = run_workspace(self.workspace, render=False)
        self.assertTrue(result["objective_success"], result)

    @patch("inf_agent.execution.service.run_process", side_effect=fake_run)
    def test_measured_health_checks_still_reject_bad_geometry_and_dimensions(
        self, process
    ):
        self.start()
        result = run_workspace(self.workspace, render=False)
        metadata_path = Path(result["run"]) / "metadata.json"
        original = load_json(metadata_path)
        cases = [
            ("loose_vertices", 1),
            ("zero_area_faces", 6),
            ("non_manifold_edges", 12),
        ]
        for name, value in cases:
            with self.subTest(metric=name):
                metadata = copy.deepcopy(original)
                metadata["asset"]["objects"][0][name] = value
                write_json_atomic(metadata_path, metadata)
                self.assertFalse(validate_run(result["run"])["objective_success"])
        write_json_atomic(metadata_path, original)
        config_path = Path(result["run"]) / "input/config.json"
        config = load_json(config_path)
        config["request"]["explicit_dimensions_m"] = {"width": 2.0}
        write_json_atomic(config_path, config)
        self.assertFalse(validate_run(result["run"])["objective_success"])

    def test_resource_limits_are_checked_before_allocating_a_run(self):
        self.start()
        with self.assertRaises(ResourceLimitError):
            run_workspace(self.workspace, samples=1000)
        self.assertFalse((self.workspace / "runs").exists())


class KnowledgeAndSourceTests(TemporaryCase):
    def test_read_does_not_need_a_task_or_write_receipts(self):
        docs = self.root / "inf_agent/modeling_docs"
        docs.mkdir(parents=True)
        (docs / "leaf.md").write_text("# full leaf\n" + "x" * 4000)
        result = read_knowledge(self.root, document="leaf.md")
        self.assertGreater(len(result["content"]), 4000)
        with self.assertRaises(ContractError):
            read_knowledge(self.root, document="../../outside.md")

    def test_exact_nested_symbol_is_read_without_importing_blender(self):
        (self.root / "module.py").write_text(
            "class A:\n    def wanted(self):\n        return 42\n    def other(self):\n        pass\n"
        )
        result = read_knowledge(self.root, symbol="module:A.wanted")
        self.assertIn("return 42", result["content"])
        self.assertNotIn("other", result["content"])

    def test_optional_lint_reports_api_pitfalls(self):
        source = self.root / "asset.py"
        source.write_text("mesh.use_auto_smooth = True\n")
        result = inspect_source(source)
        self.assertTrue(result["success"])
        self.assertTrue(result["warnings"])
        source.write_text("def broken(:\n")
        self.assertFalse(inspect_source(source)["success"])

    def test_factory_can_be_indirect_and_have_arbitrary_name_and_constants(self):
        class Base:
            pass

        fake = types.ModuleType("inf_agent_test_factory")
        fake.AssetFactory = Base
        session = BlenderSession.__new__(BlenderSession)
        session.AssetFactory = Base
        source = self.root / "asset.py"
        source.write_text(
            "import math\nfrom inf_agent_test_factory import AssetFactory\nTAU = math.tau * 1.0\nclass InternalBase(AssetFactory):\n    pass\nclass FruitFactoryApple(InternalBase):\n    pass\n"
        )
        with patch.dict(sys.modules, {"inf_agent_test_factory": fake}):
            selected = session.import_factory(source_path=source)
        self.assertEqual(selected.__name__, "FruitFactoryApple")


class JsonAndResourceTests(TemporaryCase):
    def test_atomic_json_handles_concurrent_writers_without_partial_documents(self):
        path = self.root / "shared.json"
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            list(
                pool.map(
                    lambda i: write_json_atomic(
                        path, {"value": i, "padding": "x" * 1000}
                    ),
                    range(12),
                )
            )
        self.assertIn(load_json(path)["value"], range(12))
        self.assertEqual(list(self.root.glob("*.tmp")), [])

    def test_nonfinite_json_does_not_overwrite_existing_file(self):
        path = self.root / "data.json"
        write_json_atomic(path, {"valid": True})
        with self.assertRaises(ContractError):
            write_json_atomic(path, {"bad": float("nan")})
        self.assertEqual(load_json(path), {"valid": True})
        path.write_text('{"bad":NaN}')
        with self.assertRaises(ContractError):
            load_json(path)

    def test_invalid_limits_are_rejected(self):
        for value in [0, -1, float("inf"), True]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                ResourcePolicy(max_build_seconds=value)

    def test_complexity_budget_still_prevents_expensive_render(self):
        metrics = valid_metrics()
        metrics["objects"][0]["evaluated_vertices"] = 100
        with self.assertRaises(ResourceLimitError):
            enforce_complexity_budget(
                output_dir=self.root,
                metrics=metrics,
                build_seconds=1,
                resolution=(64, 64),
                samples=1,
                policy=ResourcePolicy(max_evaluated_vertices=10),
            )
        self.assertFalse(load_json(self.root / "resource_budget.json")["allowed"])

    def test_wall_timeout_still_terminates_local_process(self):
        with self.assertRaisesRegex(ProcessError, "timeout"):
            run_process(
                ProcessRequest(
                    command=(sys.executable, "-c", "import time;time.sleep(5)"),
                    cwd=self.root,
                    writable_dir=self.root,
                    timeout_seconds=1,
                )
            )

    def test_disk_watchdog_still_stops_output_overrun(self):
        command = (
            sys.executable,
            "-c",
            "from pathlib import Path;import time;Path('overflow').write_bytes(b'x'*128);time.sleep(5)",
        )
        with self.assertRaisesRegex(ProcessError, "disk budget"):
            run_process(
                ProcessRequest(
                    command=command,
                    cwd=self.root,
                    writable_dir=self.root,
                    resource_policy=ResourcePolicy(max_artifact_bytes=64),
                )
            )

    def test_build_watchdog_still_stops_excessive_build(self):
        marker = self.root / ".build_started"
        marker.touch()
        with self.assertRaisesRegex(ProcessError, "build exceeded"):
            run_process(
                ProcessRequest(
                    command=(sys.executable, "-c", "import time;time.sleep(5)"),
                    cwd=self.root,
                    writable_dir=self.root,
                    build_marker=marker,
                    resource_policy=ResourcePolicy(max_build_seconds=0.1),
                )
            )

    def test_cli_start_and_status_are_usable_without_doctor_or_review(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(
                main(
                    ["start", "--workspace", str(self.workspace), "--prompt", "object"]
                ),
                0,
            )
        self.assertTrue(json.loads(output.getvalue())["source"].endswith("asset.py"))
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["status", "--workspace", str(self.workspace)]), 0)
        self.assertEqual(json.loads(output.getvalue())["run_count"], 0)


if __name__ == "__main__":
    unittest.main()
