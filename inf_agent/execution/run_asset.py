"""Internal subprocess entry point for one current-format run configuration."""

from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path
from inf_agent.execution.runner import RunConfig, execute_run
from inf_agent.execution.resource_policy import ResourcePolicy, ResourceLimitError
from inf_agent.workspace.input_validation import InputValidationError
from inf_agent.workspace.contracts import load_json, ContractError
from inf_agent.workspace.run_input import normalize_run_config


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", newline="\n")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        value = normalize_run_config(load_json(args.config))
    except (ContractError, InputValidationError, ResourceLimitError) as error:
        print(
            json.dumps({"success": False, "error": f"{type(error).__name__}: {error}"}),
            file=sys.stderr,
        )
        return 2
    value["parameters"]["resolution"] = tuple(value["parameters"]["resolution"])
    result = execute_run(
        RunConfig(
            repo_root=Path(value["repo_root"]),
            spec_path=args.config,
            output_dir=Path(value["output_dir"]),
            factory_class=value.get("factory_class"),
            resource_policy=ResourcePolicy(**value.get("limits", {})),
            **{
                key: value["parameters"][key]
                for key in (
                    "seed",
                    "instance_index",
                    "render",
                    "save_blend",
                    "export_glb",
                    "render_engine",
                    "resolution",
                    "samples",
                    "texture_resolution",
                    "bake_samples",
                )
            },
        )
    )
    print(
        json.dumps(
            {"execution_success": result.success, "output": str(result.output_dir)}
        )
    )
    return 0 if result.success else 1


def _exit(code: int) -> None:
    """Exit standalone bpy workers after completed GLTF writes, preserving status."""

    sys.stdout.flush()
    sys.stderr.flush()
    bpy = sys.modules.get("bpy")
    if (
        sys.platform in {"win32", "linux"}
        and bpy is not None
        and not bpy.app.binary_path
        and "io_scene_gltf2" in sys.modules
    ):
        # The GLTF file has already been closed and runner JSON/log writes are
        # atomic before main returns. Only skip the faulty addon interpreter
        # teardown used by the standalone bpy wheel. Linux 4.2.0 also segfaults
        # after successful GLTF round trips during normal interpreter shutdown.
        os._exit(code)
    raise SystemExit(code)


if __name__ == "__main__":
    _exit(main())
