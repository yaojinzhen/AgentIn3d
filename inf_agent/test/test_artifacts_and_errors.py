"""Regression cases for current artifacts and controlled failure boundaries."""

import contextlib
import copy
import io
import json
import struct
import subprocess
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from test_core_workflow import TemporaryCase, fake_run
from inf_agent.cli import main
from inf_agent.execution.artifact_validation import (
    ArtifactValidationError,
    validate_glb,
)
from inf_agent.execution.service import run_workspace, validate_run
from inf_agent.workspace.contracts import (
    ContractError,
    load_json,
    normalize_design,
    write_json_atomic,
)
from inf_agent.workspace.manager import read_workspace


class ArtifactAndErrorTests(TemporaryCase):
    def run_fixture(self, **kwargs):
        self.start()
        with patch("inf_agent.execution.service.run_process", side_effect=fake_run):
            return run_workspace(self.workspace, resolution=(64, 64), **kwargs)

    def revalidate(self, run):
        with patch("inf_agent.execution.service.run_process", side_effect=fake_run):
            return validate_run(run)

    def test_header_only_blend_is_not_usable(self):
        result = self.run_fixture(render=False)
        Path(result["artifacts"]["blend"]).write_bytes(b"BLENDER-v402")
        self.assertFalse(self.revalidate(result["run"])["objective_success"])

    def test_missing_opposite_view_is_required(self):
        result = self.run_fixture()
        (Path(result["run"]) / "previews/opposite_perspective.png").unlink()
        self.assertFalse(self.revalidate(result["run"])["objective_success"])

    def test_required_bottom_is_not_optional(self):
        result = self.run_fixture()
        config_path = Path(result["run"]) / "input/config.json"
        config = load_json(config_path)
        config["design"]["review_view_plan"] = [{"view_id": "bottom"}]
        write_json_atomic(config_path, config)
        self.assertFalse(self.revalidate(result["run"])["objective_success"])

    def test_auto_focus_and_mask_files_cannot_be_omitted(self):
        result = self.run_fixture()
        run = Path(result["run"])
        meta = load_json(run / "metadata.json")
        meta["asset"]["objects"][0].update(
            name="body", bbox_min=[0, 0, 0], bbox_max=[1, 1, 1]
        )
        meta["asset"]["focus_views"] = [dict(id="focus_01", target_part_ids=[])]
        write_json_atomic(run / "metadata.json", meta)
        (run / "previews/focus_01_mask_visible.png").unlink()
        self.assertFalse(self.revalidate(run)["objective_success"])

    def test_child_exception_survives_parent_nonzero_exit(self):
        self.start()

        def fail(request, **kwargs):
            config = load_json(Path(request.command[-1]))
            output = Path(config["output_dir"])
            (output / "run.log").write_text("build failed\n")
            error = dict(
                type="ModuleNotFoundError",
                message="No module named missing_asset_helper",
            )
            write_json_atomic(output / "metadata.json", dict(asset={}, error=error))
            write_json_atomic(
                output / "validation.json",
                dict(
                    success=False,
                    errors=[
                        "ModuleNotFoundError: No module named missing_asset_helper"
                    ],
                    error=error,
                ),
            )
            return subprocess.CompletedProcess(request.command, 1)

        with patch("inf_agent.execution.service.run_process", side_effect=fail):
            result = run_workspace(self.workspace, render=False)
        self.assertTrue(
            any("missing_asset_helper" in error for error in result["errors"])
        )
        raw = load_json(Path(result["run"]) / "validation.json")
        self.assertEqual(raw["error"]["type"], "ModuleNotFoundError")

    def test_design_wrong_types_are_contract_errors(self):
        base = dict(
            required_parts=[
                dict(part_id="body"),
                dict(part_id="cap", parent_part_id="body"),
            ],
            attachment_constraints=[
                dict(attachment_id="mount", part_id="cap", parent_part_id="body")
            ],
        )
        mutations = [
            lambda d: d["required_parts"][1].update(parent_part_id=[]),
            lambda d: d["attachment_constraints"][0].update(kind=[]),
            lambda d: d["attachment_constraints"][0].update(require_anchors="false"),
            lambda d: d.update(
                expected_bbox_or_ratio_ranges={"width_to_height": [1, 10**400]}
            ),
            lambda d: d.update(material_regions=[dict(region_id="m", part_ids=[[]])]),
        ]
        for mutate in mutations:
            case = copy.deepcopy(base)
            mutate(case)
            with self.subTest(case=str(case)[:100]), self.assertRaises(ContractError):
                normalize_design(case)
        for value in ([], False, "bad"):
            with self.subTest(value=value), self.assertRaises(ContractError):
                normalize_design(value)

    def test_missing_config_keys_return_json_exit_two(self):
        result = self.run_fixture(render=False)
        config_path = Path(result["run"]) / "input/config.json"
        config = load_json(config_path)
        del config["parameters"]
        write_json_atomic(config_path, config)
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            code = main(["validate", "--run", result["run"]])
        self.assertEqual(code, 2)
        self.assertIn("parameters", json.loads(err.getvalue())["error"])

    def test_invalid_reference_type_is_rejected(self):
        self.start()
        path = self.workspace / "request.json"
        request = load_json(path)
        request["reference_image"] = {"path": "image.png"}
        write_json_atomic(path, request)
        with self.assertRaises(ContractError):
            read_workspace(self.workspace)

    def test_empty_glb_primitives_are_invalid(self):
        path = self.root / "empty.glb"
        document = dict(
            asset={"version": "2.0"},
            scene=0,
            scenes=[{"nodes": [0]}],
            nodes=[{"mesh": 0}],
            meshes=[{"primitives": []}],
        )
        data = json.dumps(document).encode()
        data += b" " * (-len(data) % 4)
        path.write_bytes(
            struct.pack("<4sII", b"glTF", 2, 20 + len(data))
            + struct.pack("<II", len(data), 0x4E4F534A)
            + data
        )
        with self.assertRaises(ArtifactValidationError):
            validate_glb(path)

    def test_missing_or_corrupt_child_report_is_diagnosed_without_rewriting_it(self):
        result = self.run_fixture(render=False)
        run = Path(result["run"])
        report = run / "validation.json"
        for payload, status in [
            (None, "MISSING"),
            (b"{broken", "INVALID"),
            (b'{"success":"yes"}', "INVALID"),
        ]:
            with self.subTest(status=status, payload=payload):
                if payload is None:
                    report.unlink(missing_ok=True)
                else:
                    report.write_bytes(payload)
                failed = self.revalidate(run)
                self.assertFalse(failed["execution_success"])
                self.assertEqual(failed["execution_report_status"], status)
                if payload is not None:
                    self.assertEqual(report.read_bytes(), payload)

    def test_process_failure_preserves_an_existing_original_exception(self):
        from inf_agent.execution.process import ProcessError

        self.start()
        original = {}

        def timeout(request, **kwargs):
            if "inf_agent.execution.reopen_artifacts" in request.command:
                return fake_run(request, **kwargs)
            fake_run(request, **kwargs)
            run = Path(load_json(Path(request.command[-1]))["output_dir"])
            original.update(
                success=False,
                errors=["RuntimeError: original build error"],
                error=dict(type="RuntimeError", message="original build error"),
            )
            write_json_atomic(run / "validation.json", original)
            raise ProcessError("process wall timeout after 1 seconds")

        with patch("inf_agent.execution.service.run_process", side_effect=timeout):
            result = run_workspace(self.workspace, render=False)
        self.assertEqual(load_json(Path(result["run"]) / "validation.json"), original)
        self.assertEqual(result["error"]["message"], "original build error")
        self.assertIn("timeout", result["process"]["message"])

    def test_success_report_cannot_override_nonzero_process_exit(self):
        self.start()

        def exit_after_write(request, **kwargs):
            done = fake_run(request, **kwargs)
            if "inf_agent.execution.run_asset" in request.command:
                return subprocess.CompletedProcess(request.command, 7)
            return done

        with patch(
            "inf_agent.execution.service.run_process", side_effect=exit_after_write
        ):
            result = run_workspace(self.workspace, render=False)
        self.assertFalse(result["execution_success"])
        self.assertTrue(load_json(Path(result["run"]) / "validation.json")["success"])
        self.assertEqual(result["process"]["returncode"], 7)

    def test_no_render_is_explicitly_not_requested(self):
        result = self.run_fixture(render=False)
        artifacts = load_json(Path(result["run"]) / "objective_validation.json")[
            "layers"
        ]["artifact_validation"]
        self.assertEqual(artifacts["render_status"], "NOT_REQUESTED")
        self.assertFalse(
            any(
                item["kind"] in ("png", "mask")
                for item in artifacts["expected_outputs"]
            )
        )

    def test_invalid_config_and_metadata_shapes_return_json_errors(self):
        result = self.run_fixture(render=False)
        run = Path(result["run"])
        config = load_json(run / "input/config.json")
        mutations = [
            lambda d: d.update(parameters=None),
            lambda d: d.update(request=None),
            lambda d: d["parameters"].update(export_glb="false"),
            lambda d: d["parameters"].update(resolution=None),
            lambda d: d["parameters"].update(samples=None),
            lambda d: d["limits"].update(max_samples=10**400),
            lambda d: d["request"].update(forbidden_items=None),
            lambda d: d["request"].update(reference_image=[]),
        ]

        def expect_input_error():
            err = io.StringIO()
            with (
                contextlib.redirect_stdout(io.StringIO()),
                contextlib.redirect_stderr(err),
            ):
                code = main(["validate", "--run", str(run)])
            self.assertEqual(code, 2)
            self.assertFalse(json.loads(err.getvalue())["success"])

        for mutate in mutations:
            current = copy.deepcopy(config)
            mutate(current)
            write_json_atomic(run / "input/config.json", current)
            with self.subTest(config=str(current)[:100]):
                expect_input_error()
        write_json_atomic(run / "input/config.json", config)
        metadata = load_json(run / "metadata.json")
        for asset in (
            None,
            [],
            dict(objects=[None]),
            dict(bbox={"width": []}),
            dict(part_registry={"registrations": [{"part_id": []}]}),
        ):
            write_json_atomic(run / "metadata.json", dict(asset=asset))
            with self.subTest(asset=asset):
                expect_input_error()
        write_json_atomic(run / "metadata.json", metadata)

    def test_png_set_masks_and_dimensions_are_checked_independently(self):
        from inf_agent.execution.artifact_validation import validate_final_artifacts
        from inf_agent.execution.view_plan import expected_outputs
        from test_core_workflow import valid_metrics

        for custom in (False, True):
            design = normalize_design(
                dict(
                    required_parts=[dict(part_id="body")],
                    review_view_plan=[dict(view_id="bottom")]
                    + (
                        [dict(view_id="detail", target_part_ids=["body"])]
                        if custom
                        else []
                    ),
                )
            )
            metrics = valid_metrics()
            metrics["evaluated_mesh_islands"] = [
                dict(object_name="body", part_id="body")
            ]
            outputs = expected_outputs(
                design, metrics, render=True, save_blend=False, export_glb=False
            )
            output = self.root / ("custom" if custom else "auto")
            for item in outputs:
                path = output / item["path"]
                path.parent.mkdir(parents=True, exist_ok=True)
                Image.new("RGB", (64, 64), "white").save(path)

            def validate():
                return validate_final_artifacts(
                    output, expected_resolution=(64, 64), expected_outputs=outputs
                )

            self.assertTrue(validate()["success"])
            for item in outputs:
                path = output / item["path"]
                data = path.read_bytes()
                with self.subTest(custom=custom, path=path.name):
                    path.unlink()
                    self.assertFalse(validate()["success"])
                    path.write_bytes(data[:24])
                    self.assertFalse(validate()["success"])
                    Image.new("RGB", (32, 64), "white").save(path)
                    self.assertFalse(validate()["success"])
                    path.write_bytes(data)
            mask = next(
                output / item["path"]
                for item in outputs
                if item["kind"] == "mask" and item["mask"] == "visible"
            )
            Image.new("RGB", (64, 64), "black").save(mask)
            failure = validate()
            self.assertTrue(failure["files_usable"])
            self.assertFalse(failure["focus_evidence"]["success"])

    def test_glb_triangle_and_invalid_geometry_references(self):
        from artifact_fixtures import triangle, glb_bytes

        document, binary = triangle()
        path = self.root / "triangle.glb"
        path.write_bytes(glb_bytes(document, binary))
        proof = validate_glb(path)
        self.assertTrue(proof["parsed"])
        self.assertTrue(proof["semantic_valid"])
        mutations = [
            lambda d: d["meshes"][0].update(primitives=[]),
            lambda d: d["nodes"][0].update(mesh=5),
            lambda d: d["scenes"][0].update(nodes=[9]),
            lambda d: d["nodes"][0].update(children=[0]),
            lambda d: d["bufferViews"][0].update(byteLength=400),
            lambda d: d["accessors"][0].update(count=100),
            lambda d: d["accessors"][0].update(byteOffset=4),
            lambda d: d["meshes"][0]["primitives"][0]["attributes"].update(POSITION=8),
            lambda d: d["scenes"][0].update(nodes=[]),
            lambda d: d["buffers"][0].update(byteLength=400),
        ]
        for mutate in mutations:
            case = copy.deepcopy(document)
            mutate(case)
            path.write_bytes(glb_bytes(case, binary))
            with (
                self.subTest(document=case),
                self.assertRaises(ArtifactValidationError),
            ):
                validate_glb(path)
        for corrupted in (
            binary[:36] + struct.pack("<3H", 0, 1, 8) + binary[42:],
            struct.pack("<f", float("nan")) + binary[4:],
        ):
            path.write_bytes(glb_bytes(document, corrupted))
            with self.assertRaises(ArtifactValidationError):
                validate_glb(path)

    def test_transparent_or_spatially_inconsistent_masks_are_not_evidence(self):
        from inf_agent.execution.artifact_validation import validate_final_artifacts

        output = self.root / "masks"
        output.mkdir()
        outputs = [
            dict(
                id="detail_mask_" + mask,
                path=mask + ".png",
                kind="mask",
                view_id="detail",
                mask=mask,
            )
            for mask in ("visible", "potential")
        ]
        Image.new("RGB", (64, 64), "white").save(output / "potential.png")
        Image.new("RGBA", (64, 64), (255, 255, 255, 0)).save(output / "visible.png")

        def check():
            return validate_final_artifacts(
                output, expected_resolution=(64, 64), expected_outputs=outputs
            )

        self.assertFalse(check()["success"])
        for mask, box in [("visible", (0, 0, 16, 16)), ("potential", (32, 32, 48, 48))]:
            image = Image.new("RGB", (64, 64), "black")
            image.paste("white", box)
            image.save(output / (mask + ".png"))
        report = check()
        self.assertFalse(report["success"])
        self.assertGreater(
            report["focus_evidence"]["views"][0]["visible_outside_potential_pixels"], 0
        )

    def test_corrupt_reopen_report_cannot_crash_the_parent(self):
        result = self.run_fixture(render=False)

        def corrupt(request, **kwargs):
            config = load_json(Path(request.command[-1]))
            write_json_atomic(
                Path(config["output_dir"]) / "artifact_reopen.json",
                dict(schema_version="1.1", success=False, errors=None),
            )
            return subprocess.CompletedProcess(request.command, 0)

        with patch("inf_agent.execution.service.run_process", side_effect=corrupt):
            failed = validate_run(result["run"])
        self.assertFalse(failed["objective_success"])
        self.assertIn("artifacts", failed["failure_domains"])

    def test_runner_config_errors_use_json_exit_two(self):
        from inf_agent.execution.run_asset import main as runner_main

        result = self.run_fixture(render=False)
        path = Path(result["run"]) / "input/config.json"
        config = load_json(path)
        config["parameters"]["save_blend"] = "false"
        write_json_atomic(path, config)
        error = io.StringIO()
        with contextlib.redirect_stderr(error):
            code = runner_main(["--config", str(path)])
        self.assertEqual(code, 2)
        self.assertIn("save_blend", json.loads(error.getvalue())["error"])

    def test_cli_does_not_mask_unexpected_internal_errors(self):
        with patch(
            "inf_agent.cli.run_workspace",
            side_effect=RuntimeError("internal programming error"),
        ):
            with self.assertRaisesRegex(RuntimeError, "internal programming error"):
                main(["preview", "--workspace", str(self.workspace)])
