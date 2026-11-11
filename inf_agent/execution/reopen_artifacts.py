"""Independent runtime probe for the files currently present in one run."""

import argparse
import json
import sys
from pathlib import Path
from inf_agent.execution.blender import BlenderSession
from inf_agent.workspace.contracts import ContractError, load_json, write_json_atomic
from inf_agent.workspace.run_input import normalize_run_config


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        config = normalize_run_config(load_json(args.config))
    except (ContractError, ValueError) as error:
        print(json.dumps(dict(success=False, error=str(error))), file=sys.stderr)
        return 2
    output = args.run_dir.resolve()
    options = config["parameters"]
    try:
        report = BlenderSession().reopen_final_artifacts(
            glb_path=output / "asset.glb" if options["export_glb"] else None,
            blend_path=output / "scene.blend" if options["save_blend"] else None,
        )
    except Exception as error:
        report = dict(
            schema_version="1.1",
            success=False,
            backend="blender",
            errors=[f"{type(error).__name__}: {error}"],
        )
    write_json_atomic(output / "artifact_reopen.json", report)
    return 0 if report["success"] else 1


if __name__ == "__main__":
    from inf_agent.execution.run_asset import _exit

    _exit(main())
