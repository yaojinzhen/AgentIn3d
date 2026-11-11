"""Stable orchestration for agent-generated static assets.

The runner follows the compact flow used by
``infinigen_examples.generate_asset_simple``:

1. validate inputs and resolve one factory;
2. configure one clean Blender scene;
3. call ``spawn_asset`` and ``finalize_assets``;
4. frame the asset and write requested outputs;
5. record raw execution metadata and logs for the parent validator.

Blender operations live in :mod:`inf_agent.execution.blender`. Objective asset
health is deliberately evaluated by the parent execution service, not here.
"""

from __future__ import annotations

import logging
import platform
import sys
import time
import traceback
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO

from inf_agent.execution.blender import BlenderSession
from inf_agent.execution.source_context import asset_source_context
from inf_agent.execution.resource_policy import (
    DEFAULT_RESOURCE_POLICY,
    ResourceLimitError,
    ResourcePolicy,
    enforce_artifact_budget,
    enforce_complexity_budget,
    validate_render_request,
    write_build_started_report,
)
from inf_agent.execution.telemetry import TelemetryRecorder
from inf_agent.execution.view_plan import expected_outputs
from inf_agent.workspace.run_input import normalize_run_config
from inf_agent.workspace.contracts import (
    ContractError,
    load_json,
    SCHEMA_VERSION,
    part_manifest_from_design,
    write_json_atomic,
)

RUNNER_SCHEMA_VERSION = SCHEMA_VERSION
RAW_RUNNER_SCHEMA_VERSION = SCHEMA_VERSION


DEFAULT_RESOLUTION = (512, 512)
DEFAULT_SAMPLES = 64


class RunnerError(RuntimeError):
    """Raised for runner configuration or factory routing errors."""


@dataclass(frozen=True)
class RunConfig:
    """Resolved settings for one non-overwriting asset run."""

    repo_root: Path
    spec_path: Path
    output_dir: Path
    factory_class: str | None = None
    seed: int = 0
    instance_index: int = 0
    render: str = "image"
    save_blend: bool = True
    export_glb: bool = True
    render_engine: str = "BLENDER_EEVEE_NEXT"
    resolution: tuple[int, int] = DEFAULT_RESOLUTION
    samples: int = DEFAULT_SAMPLES
    texture_resolution: int = 2048
    bake_samples: int = 4
    resource_policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY


@dataclass(frozen=True)
class RunResult:
    """Structured outcome returned to callers and the CLI."""

    success: bool
    output_dir: Path
    metadata: dict[str, Any]
    validation: dict[str, Any]


class _Tee:
    """Mirror stdout/stderr into the stable run log."""

    def __init__(self, primary: TextIO, log_file: TextIO):
        self.primary = primary
        self.log_file = log_file

    def write(self, value: str) -> int:
        self.primary.write(value)
        self.log_file.write(value)
        self.log_file.flush()
        return len(value)

    def flush(self) -> None:
        self.primary.flush()
        self.log_file.flush()

    def isatty(self) -> bool:
        return False

    @property
    def encoding(self) -> str:
        return "utf-8"


def resolve_input_path(value: Path, repo_root: Path) -> Path:
    if value.is_absolute():
        return value.resolve()
    cwd_candidate = value.resolve()
    if cwd_candidate.exists():
        return cwd_candidate
    return (repo_root / value).resolve()


def _prepare_output_dir(path: Path) -> None:
    if path.exists():
        if not path.is_dir():
            raise RunnerError(f"output path is not a directory: {path}")
        if any(item.name not in {"input", "process.log"} for item in path.iterdir()):
            raise RunnerError(
                "output directory is not empty; refusing to overwrite "
                f"a prior run: {path}"
            )
        return
    path.mkdir(parents=True)


def _write_run_reports(
    *,
    config: RunConfig,
    metadata: dict[str, Any],
    validation: dict[str, Any],
    started: float,
    telemetry: TelemetryRecorder,
) -> None:
    metadata["finished_at_utc"] = _utc_now()
    metadata["duration_seconds"] = round(time.monotonic() - started, 3)
    _write_json_atomic(config.output_dir / "validation.json", validation)
    metadata["outputs"] = _output_records(config.output_dir, config.repo_root)
    metrics = metadata.get("asset", {})
    artifact_bytes = {
        path.relative_to(config.output_dir).as_posix(): path.stat().st_size
        for path in config.output_dir.rglob("*")
        if path.is_file() and path.name != "metadata.json"
    }
    telemetry_report = telemetry.snapshot(
        object_count=metrics.get("object_count", 0),
        face_count=metrics.get("face_count", 0),
        vertex_count=metrics.get("vertex_count", 0),
        artifact_bytes=artifact_bytes,
    )
    telemetry_report["blender_initialize_breakdown_seconds"] = metadata.get(
        "blender_initialize_breakdown_seconds", {}
    )
    metadata["telemetry"] = telemetry_report
    if isinstance(metrics, dict):
        metrics["telemetry"] = telemetry_report
    _write_json_atomic(config.output_dir / "metadata.json", metadata)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    try:
        write_json_atomic(path, value)
    except ContractError as error:
        raise RunnerError(f"cannot write runner JSON: {error}") from error


def _path_reference(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _empty_metrics() -> dict[str, Any]:
    return {
        "object_count": 0,
        "mesh_count": 0,
        "vertex_count": 0,
        "face_count": 0,
        "material_count": 0,
        "materials": [],
        "unmaterialized_meshes": [],
        "uncovered_material_faces": 0,
        "objects": [],
        "bbox": {"min": None, "max": None, "width": 0.0, "depth": 0.0, "height": 0.0},
        "structural": None,
    }


def _metadata_template(config: RunConfig) -> dict[str, Any]:
    return {
        "schema_version": RUNNER_SCHEMA_VERSION,
        "success": False,
        "started_at_utc": _utc_now(),
        "finished_at_utc": None,
        "duration_seconds": None,
        "asset_id": None,
        "factory": None,
        "seed": config.seed,
        "instance_index": config.instance_index,
        "spec_path": _path_reference(config.spec_path, config.repo_root),
        "output_dir": _path_reference(config.output_dir, config.repo_root),
        "render": {
            "mode": config.render,
            "engine": config.render_engine,
            "resolution": list(config.resolution),
            "samples": config.samples,
        },
        "outputs": {},
        "asset": _empty_metrics(),
        "environment": {
            "python": platform.python_version(),
            "blender": None,
            "background": None,
        },
        "error": None,
        "telemetry": None,
    }


def _output_records(output_dir: Path, repo_root: Path) -> dict[str, Any]:
    return {
        name: {
            "path": _path_reference(output_dir / filename, repo_root),
            "exists": (output_dir / filename).is_file(),
            "bytes": (output_dir / filename).stat().st_size
            if (output_dir / filename).is_file()
            else 0,
        }
        for name, filename in (
            ("scene_blend", "scene.blend"),
            ("asset_glb", "asset.glb"),
            ("preview_png", "previews/perspective.png"),
            ("preview_front_png", "previews/front.png"),
            ("preview_side_png", "previews/side.png"),
            ("preview_top_png", "previews/top.png"),
            ("run_log", "run.log"),
            ("resource_budget", "resource_budget.json"),
        )
    }


def _load_runner_spec(path: Path) -> dict[str, Any]:
    value = normalize_run_config(load_json(path))
    source = Path(value.get("source_path", ""))
    if not source.is_absolute() or not source.is_file() or source.suffix != ".py":
        raise RunnerError("run input source_path must point to a Python source file")
    value["asset_spec"] = value["design"]
    value["part_manifest"] = part_manifest_from_design(value["asset_spec"])
    request = value.get("request", {})
    from inf_agent.workspace.input_validation import normalize_dimensions

    dimensions = normalize_dimensions(request.get("explicit_dimensions_m"))
    value["dimensions"] = {"explicit": bool(dimensions), **dimensions}
    return value


def execute_run(config: RunConfig) -> RunResult:
    """Execute one factory and always emit structured reports after setup."""

    config = replace(
        config,
        repo_root=config.repo_root.resolve(),
        spec_path=config.spec_path.resolve(),
        output_dir=config.output_dir.resolve(),
    )
    try:
        validate_render_request(
            config.resolution,
            config.samples,
            policy=config.resource_policy,
        )
    except ResourceLimitError as error:
        raise RunnerError(str(error)) from error
    _prepare_output_dir(config.output_dir)

    metadata = _metadata_template(config)
    metrics = _empty_metrics()
    spec: dict[str, Any] = {"dimensions": {"explicit": False}}
    execution_error: str | None = None
    started = time.monotonic()
    telemetry = TelemetryRecorder()
    log_path = config.output_dir / "run.log"

    with log_path.open("w", encoding="utf-8", newline="\n") as log_file:
        stdout = _Tee(sys.stdout, log_file)
        stderr = _Tee(sys.stderr, log_file)
        with (
            redirect_stdout(stdout),
            redirect_stderr(stderr),
            ExitStack() as source_context,
        ):
            logging.basicConfig(
                level=logging.INFO,
                format=(
                    "[%(asctime)s.%(msecs)03d] [%(name)s] [%(levelname)s] | %(message)s"
                ),
                datefmt="%H:%M:%S",
                stream=stdout,
                force=True,
            )
            logger = logging.getLogger("inf_agent.execution.runner")

            try:
                logger.info("Starting generated asset run")
                if str(config.repo_root) not in sys.path:
                    sys.path.insert(0, str(config.repo_root))
                if not config.spec_path.is_file():
                    raise RunnerError(f"asset spec does not exist: {config.spec_path}")

                spec = _load_runner_spec(config.spec_path)
                source_context.enter_context(
                    asset_source_context(Path(spec["source_path"]).parent)
                )
                metadata["input_context"] = spec.get("input_context")
                metadata["asset_id"] = spec["asset_id"]
                reference = config.factory_class
                metadata["source_path"] = spec["source_path"]

                with telemetry.phase("blender_initialize"):
                    session = BlenderSession()
                    metadata["environment"].update(session.environment)
                    metadata["blender_initialize_breakdown_seconds"] = getattr(
                        session, "import_timings_seconds", {}
                    )
                with telemetry.phase("configure"):
                    session.configure(
                        render_engine=config.render_engine,
                        resolution=config.resolution,
                        samples=config.samples,
                    )
                with telemetry.phase("factory_import"):
                    factory_class = session.import_factory(
                        reference, source_path=Path(spec["source_path"])
                    )
                    metadata["factory"] = factory_class.__name__
                write_build_started_report(
                    output_dir=config.output_dir,
                    resolution=config.resolution,
                    samples=config.samples,
                    policy=config.resource_policy,
                )
                build_marker = config.output_dir / ".build_started"
                build_marker.touch()
                build_started = time.monotonic()
                try:
                    with telemetry.phase("build"):
                        asset = session.build_asset(
                            factory_class,
                            seed=config.seed,
                            instance_index=config.instance_index,
                            spec=spec,
                        )
                finally:
                    build_marker.unlink(missing_ok=True)
                build_runtime_seconds = time.monotonic() - build_started
                metric_timings: dict[str, float] = {}
                metrics = session.asset_metrics(
                    asset,
                    spec=spec,
                    runtime_seconds=build_runtime_seconds,
                    telemetry=metric_timings,
                )
                for phase_name, seconds in metric_timings.items():
                    telemetry.add(phase_name, seconds)
                metadata["asset"] = metrics
                budget_report = enforce_complexity_budget(
                    output_dir=config.output_dir,
                    metrics=metrics,
                    build_seconds=build_runtime_seconds,
                    resolution=config.resolution,
                    samples=config.samples,
                    policy=config.resource_policy,
                )
                if metrics["mesh_count"] == 0:
                    raise RunnerError(
                        "generated asset has no visible mesh in its returned hierarchy"
                    )

                metrics["review_axes"] = {
                    "front_axis": spec["asset_spec"]["front_axis"],
                    "up_axis": spec["asset_spec"]["up_axis"],
                }
                metrics["review_required_part_ids"] = [
                    item["part_id"] for item in spec["asset_spec"]["required_parts"]
                ]
                metrics["review_view_ids"] = [
                    item["view_id"] for item in spec["asset_spec"]["review_view_plan"]
                ]
                metrics["review_view_plan"] = spec["asset_spec"]["review_view_plan"]

                metrics["expected_outputs"] = expected_outputs(
                    spec["asset_spec"],
                    metrics,
                    render=config.render == "image",
                    save_blend=config.save_blend,
                    export_glb=config.export_glb,
                )
                with telemetry.phase("configure_preview"):
                    session.setup_preview(metrics)
                if config.export_glb:
                    logger.info("Exporting asset.glb")
                    with telemetry.phase("export"):
                        metadata["material_export"] = session.export_glb(
                            asset,
                            config.output_dir / "asset.glb",
                            texture_resolution=config.texture_resolution,
                            bake_samples=config.bake_samples,
                        )
                    enforce_artifact_budget(
                        config.output_dir,
                        budget_report,
                        policy=config.resource_policy,
                    )
                if config.save_blend:
                    logger.info("Saving scene.blend")
                    with telemetry.phase("save"):
                        session.bpy.context.scene["inf_agent_asset_root"] = (
                            asset.name_full
                        )
                        session.save_blend(config.output_dir / "scene.blend")
                    enforce_artifact_budget(
                        config.output_dir,
                        budget_report,
                        policy=config.resource_policy,
                    )
                if config.render == "image":
                    logger.info("Rendering preview.png")
                    with telemetry.phase("render.preview"):
                        session.render_preview(config.output_dir / "preview.png")
                    enforce_artifact_budget(
                        config.output_dir,
                        budget_report,
                        policy=config.resource_policy,
                    )
                    logger.info("Rendering front, side, and top review views")
                    view_timings = session.render_review_views(
                        metrics, config.output_dir
                    )
                    for view_name, seconds in view_timings.items():
                        telemetry.add(f"render.{view_name}", seconds)
                    enforce_artifact_budget(
                        config.output_dir,
                        budget_report,
                        policy=config.resource_policy,
                    )
                    logger.info("Rendering bounded object-range review views")
                    focus_records = session.render_object_focus_views(
                        metrics,
                        config.output_dir,
                        limit=max(8, len(metrics["review_view_plan"])),
                    )
                    for record in focus_records:
                        telemetry.add(
                            f"render.{record['id']}",
                            record.get("render_seconds", 0.0),
                        )
                        telemetry.add(
                            f"render.{record['id']}.masks",
                            record.get("mask_render_seconds", 0.0),
                        )
                    enforce_artifact_budget(
                        config.output_dir,
                        budget_report,
                        policy=config.resource_policy,
                    )
                if config.render == "image":
                    previews = config.output_dir / "previews"
                    previews.mkdir(exist_ok=True)
                    for path in list(config.output_dir.glob("preview*.png")):
                        view = (
                            "perspective"
                            if path.stem == "preview"
                            else path.stem.removeprefix("preview_")
                        )
                        path.replace(previews / f"{view}.png")
                    for path in list(config.output_dir.glob("focus_*.png")):
                        path.replace(previews / path.name)

                    def update_image_references(value):
                        if isinstance(value, dict):
                            return {
                                key: update_image_references(item)
                                for key, item in value.items()
                            }
                        if isinstance(value, list):
                            return [update_image_references(item) for item in value]
                        if isinstance(value, str) and value.endswith(".png"):
                            old_name = Path(value).name
                            new_name = (
                                "perspective.png"
                                if old_name == "preview.png"
                                else old_name.removeprefix("preview_")
                            )
                            return str(previews / new_name)
                        return value

                    metrics["focus_views"] = update_image_references(
                        metrics.get("focus_views", [])
                    )
                logger.info(
                    "Generated %s mesh objects with %s evaluated vertices",
                    metrics["mesh_count"],
                    metrics["vertex_count"],
                )
            except Exception as error:
                execution_error = f"{type(error).__name__}: {error}"
                metadata["error"] = {
                    "type": type(error).__name__,
                    "message": str(error),
                }
                logger.error("Generated asset run failed")
                traceback.print_exc()

            validation = {
                "schema_version": RAW_RUNNER_SCHEMA_VERSION,
                "success": execution_error is None,
                "errors": [] if execution_error is None else [execution_error],
                "error": metadata.get("error"),
                "warnings": [],
                "note": "Raw execution status only; parent asset_health is authoritative.",
            }
            metadata["success"] = validation["success"]

            if validation["success"]:
                logger.info("Generated asset run succeeded")
            else:
                logger.error("Generated asset run did not pass validation")
            stdout.flush()
            stderr.flush()
            _write_run_reports(
                config=config,
                metadata=metadata,
                validation=validation,
                started=started,
                telemetry=telemetry,
            )
            # The root handler owns a tee that references this soon-to-close
            # run log. Close it while the file is still valid so interpreter
            # shutdown and later in-process runs cannot flush a stale stream.
            logging.shutdown()

    return RunResult(
        success=validation["success"],
        output_dir=config.output_dir,
        metadata=metadata,
        validation=validation,
    )
