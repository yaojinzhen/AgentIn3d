"""Run current workspace code and return artifacts plus objective diagnostics."""

from __future__ import annotations
import subprocess
import sys
from pathlib import Path
from typing import Any

from inf_agent.execution.diagnostics import objective_failure_domains
from inf_agent.execution.artifact_validation import validate_final_artifacts
from inf_agent.execution.asset_health import evaluate_asset_health
from inf_agent.execution.process import ProcessError, ProcessRequest, run_process
from inf_agent.execution.resource_policy import ResourcePolicy, validate_render_request
from inf_agent.execution.view_plan import expected_outputs
from inf_agent.workspace.run_input import normalize_run_config, validate_metadata
from inf_agent.workspace.contracts import (
    SCHEMA_VERSION,
    ContractError,
    load_json,
    part_manifest_from_design,
    write_json_atomic,
)
from inf_agent.workspace.manager import allocate_run, read_workspace
from inf_agent.workspace.snapshot import prepare_snapshot, write_snapshot

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read_raw_report(path):
    try:
        report = load_json(path)
        if (
            not isinstance(report.get("success"), bool)
            or not isinstance(report.get("errors", []), list)
            or any(not isinstance(x, str) for x in report.get("errors", []))
        ):
            raise ContractError(
                "execution report requires success bool and error strings"
            )
        if report["success"] and report.get("errors"):
            raise ContractError("successful execution report contains errors")
        error = report.get("error")
        if error is not None and (
            not isinstance(error, dict)
            or any(not isinstance(error.get(k), str) for k in ("type", "message"))
        ):
            raise ContractError("execution report error requires type/message strings")
        return report, "VALID"
    except ContractError as error:
        status = "INVALID" if path.exists() else "MISSING"
        return {
            "success": False,
            "errors": [f"{status.lower()} execution report: {error}"],
        }, status


def _refresh_reopen(run_dir, config):
    options = config["parameters"]
    required = [
        run_dir / filename
        for enabled, filename in (
            (options["save_blend"], "scene.blend"),
            (options["export_glb"], "asset.glb"),
        )
        if enabled
    ]
    report_path = run_dir / "artifact_reopen.json"
    if not required:
        return
    report_path.unlink(missing_ok=True)
    if not all(path.is_file() for path in required):
        write_json_atomic(
            report_path,
            dict(
                schema_version="1.1",
                success=False,
                errors=["requested 3D artifact is missing"],
                backend="not_run",
            ),
        )
        return
    failure = None
    try:
        with (run_dir / "reopen.log").open("w", encoding="utf-8") as stream:
            completed = run_process(
                ProcessRequest(
                    command=(
                        sys.executable,
                        "-B",
                        "-m",
                        "inf_agent.execution.reopen_artifacts",
                        "--run-dir",
                        str(run_dir),
                        "--config",
                        str(run_dir / "input/config.json"),
                    ),
                    cwd=REPO_ROOT,
                    writable_dir=run_dir,
                    resource_policy=ResourcePolicy(**config.get("limits", {})),
                ),
                stdout=stream,
                stderr=subprocess.STDOUT,
            )
        if completed.returncode != 0:
            failure = f"artifact reopen process exited with code {completed.returncode}; see reopen.log"
    except (ProcessError, OSError) as error:
        failure = str(error)
    try:
        report = load_json(report_path)
    except ContractError:
        report = dict(
            schema_version="1.1",
            success=False,
            errors=["artifact reopen process produced no readable report"],
            backend="not_available",
        )
    if failure:
        report["success"] = False
        report["process_error"] = failure
        report["errors"] = [
            *(
                report.get("errors", [])
                if isinstance(report.get("errors"), list)
                else []
            ),
            failure,
        ]
    write_json_atomic(report_path, report)


def validate_run(run_dir: Path | str) -> dict[str, Any]:
    """Check current files with fresh reopen; geometric design facts remain stored metrics."""
    run_dir = Path(run_dir).resolve()
    value = normalize_run_config(load_json(run_dir / "input/config.json"))
    metadata = (
        validate_metadata(load_json(run_dir / "metadata.json"))
        if (run_dir / "metadata.json").is_file()
        else {}
    )
    raw, raw_status = _read_raw_report(run_dir / "validation.json")
    process = (
        load_json(run_dir / "process_status.json")
        if (run_dir / "process_status.json").is_file()
        else None
    )
    if process is not None and (
        not isinstance(process.get("success"), bool)
        or (
            process.get("success") is False
            and not isinstance(process.get("message"), str)
        )
    ):
        raise ContractError("process_status.success: expected bool")
    parameters, design = value["parameters"], value["design"]
    render, export = parameters["render"] == "image", parameters["export_glb"]
    execution_ok = raw.get("success") is True and (
        process is None or process["success"]
    )
    execution_errors = list(raw.get("errors", []))
    if process is not None and not process["success"]:
        execution_errors.append(process.get("message", "asset process failed"))
    outputs = expected_outputs(
        design,
        metadata.get("asset", {}),
        render=render,
        export_glb=export,
        save_blend=parameters["save_blend"],
    )
    health = evaluate_asset_health(
        metrics=metadata.get("asset", {}),
        output_dir=run_dir,
        request=value["request"],
        asset_spec=design,
        part_manifest=part_manifest_from_design(design),
        mode="final" if export else "preview",
        execution_ok=execution_ok,
        execution_errors=execution_errors,
        render=render,
        export_glb=export,
        save_blend=parameters["save_blend"],
        expected_outputs=outputs,
    )
    _refresh_reopen(run_dir, value)
    artifacts = validate_final_artifacts(
        run_dir,
        expected_resolution=tuple(parameters["resolution"]),
        expected_outputs=outputs,
    )
    stored_outputs = metadata.get("asset", {}).get("expected_outputs")
    if stored_outputs is not None and stored_outputs != outputs:
        artifacts["success"] = False
        artifacts["errors"].append(
            "stored render output plan differs from the current configuration or measured object selections; render again"
        )
    health["layers"]["artifact_validation"] = artifacts
    health["measurement_source"] = "stored_run_metadata"
    health["artifact_measurement_source"] = "current_files_and_fresh_runtime_reopen"
    health["success"] = health["success"] and artifacts["success"]
    health["errors"] = list(dict.fromkeys([*health["errors"], *artifacts["errors"]]))
    error = raw.get("error") or metadata.get("error")
    if error is None and not execution_ok:
        error = dict(
            type="ProcessError"
            if process and not process["success"]
            else "ExecutionReportError",
            message="; ".join(execution_errors),
        )
    health["layers"]["execution_health"]["error_type"] = (
        error.get("type") if isinstance(error, dict) else None
    )
    write_json_atomic(run_dir / "objective_validation.json", health)
    paths = {"blend": run_dir / "scene.blend", "glb": run_dir / "asset.glb"}
    result = {
        "schema_version": SCHEMA_VERSION,
        "run": run_dir.as_posix(),
        "execution_success": execution_ok,
        "objective_success": health["success"],
        "visual_status": "NOT_CHECKED",
        "failure_domains": objective_failure_domains(health),
        "error": error,
        "process": process,
        "execution_report_status": raw_status,
        "artifacts": {
            name: path.as_posix() for name, path in paths.items() if path.is_file()
        },
        "previews": [
            p.as_posix()
            for p in sorted((run_dir / "previews").glob("*.png"))
            if not p.stem.endswith(("_mask_visible", "_mask_potential"))
        ],
        "validation": (run_dir / "objective_validation.json").as_posix(),
        "errors": health["errors"],
        "warnings": health["warnings"],
    }
    write_json_atomic(run_dir / "result.json", result)
    return result


def run_workspace(
    workspace: Path | str,
    *,
    factory: str | None = None,
    seed: int = 0,
    instance_index: int = 0,
    render: bool = True,
    export_glb: bool = False,
    resolution: tuple[int, int] = (512, 512),
    samples: int = 32,
    limits: dict | None = None,
    texture_resolution: int = 2048,
    bake_samples: int = 4,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    from inf_agent.execution.material_export import MaterialExportSettings

    MaterialExportSettings(texture_resolution, bake_samples)
    workspace, request, design = read_workspace(workspace)
    if limits is not None and not isinstance(limits, dict):
        raise ContractError("limits: expected an object")
    try:
        policy = ResourcePolicy(**({} if limits is None else limits))
    except (TypeError, ValueError) as error:
        raise ContractError(f"limits: {error}") from error
    if (
        not isinstance(seed, int)
        or isinstance(seed, bool)
        or not 0 <= seed <= 2**32 - 1
    ):
        raise ContractError("seed: expected an integer in [0, 2**32-1]")
    if (
        not isinstance(instance_index, int)
        or isinstance(instance_index, bool)
        or instance_index < 0
    ):
        raise ContractError("instance_index: expected a non-negative integer")
    if not isinstance(render, bool) or not isinstance(export_glb, bool):
        raise ContractError("render/export_glb: expected bools")
    if factory is not None and not isinstance(factory, str):
        raise ContractError("factory: expected a string or null")
    validate_render_request(resolution, samples, policy=policy)
    source = workspace / "asset.py"
    if not source.is_file():
        raise ContractError(f"asset.py is missing: {source}")
    compile(source.read_text(encoding="utf-8"), str(source), "exec")
    plan = prepare_snapshot(workspace, request)
    run = allocate_run(workspace, max_runs=policy.max_runs)
    inputs = run / "input"
    snapshot, request, input_context = write_snapshot(plan, inputs, request)
    config = {
        "schema_version": SCHEMA_VERSION,
        "asset_id": workspace.name,
        "repo_root": repo_root.resolve().as_posix(),
        "output_dir": run.as_posix(),
        "source_path": snapshot.as_posix(),
        "input_context": input_context,
        "factory_class": factory,
        "request": request,
        "design": design,
        "limits": policy.to_dict(),
        "parameters": {
            "seed": seed,
            "instance_index": instance_index,
            "render": "image" if render else "none",
            "save_blend": True,
            "export_glb": export_glb,
            "render_engine": "BLENDER_EEVEE_NEXT",
            "resolution": list(resolution),
            "samples": samples,
            "texture_resolution": texture_resolution,
            "bake_samples": bake_samples,
        },
    }
    config_path = inputs / "config.json"
    write_json_atomic(config_path, config)
    failure = None
    returncode = None
    failure_type = None
    try:
        with (run / "process.log").open("w", encoding="utf-8") as stream:
            completed = run_process(
                ProcessRequest(
                    command=(
                        sys.executable,
                        "-B",
                        "-m",
                        "inf_agent.execution.run_asset",
                        "--config",
                        str(config_path),
                    ),
                    cwd=repo_root.resolve(),
                    writable_dir=run,
                    build_marker=run / ".build_started",
                    resource_policy=policy,
                ),
                stdout=stream,
                stderr=subprocess.STDOUT,
            )
        returncode = completed.returncode
        if completed.returncode != 0:
            failure_type = "NonzeroExit"
            failure = f"asset process exited with code {completed.returncode}; see process.log"
    except (ProcessError, OSError) as error:
        failure_type = type(error).__name__
        failure = str(error)
    write_json_atomic(
        run / "process_status.json",
        dict(
            success=failure is None,
            returncode=returncode,
            type=failure_type,
            message=failure,
            log="process.log",
        ),
    )
    return validate_run(run)
