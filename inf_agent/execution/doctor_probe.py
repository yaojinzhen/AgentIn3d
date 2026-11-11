"""Minimal Blender capability probe used by host doctor."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def run_probe(output_dir: Path) -> dict[str, object]:
    import bpy

    output_dir.mkdir(parents=True, exist_ok=True)
    write_probe = output_dir / "staging_write_probe.txt"
    write_probe.write_text("ok", encoding="utf-8")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_cube_add(size=1.0)
    cube = bpy.context.object
    cube.name = "DoctorProbeCube"
    material = bpy.data.materials.new("DoctorProbeMaterial")
    cube.data.materials.append(material)
    blend_path = output_dir / "doctor_scene.blend"
    glb_path = output_dir / "doctor_asset.glb"
    saved = bpy.ops.wm.save_as_mainfile(filepath=str(blend_path), check_existing=False)
    exported = bpy.ops.export_scene.gltf(
        filepath=str(glb_path),
        export_format="GLB",
        use_selection=False,
        export_apply=True,
    )
    bpy.ops.wm.read_factory_settings(use_empty=True)
    imported = bpy.ops.import_scene.gltf(filepath=str(glb_path))
    glb_meshes = sum(obj.type == "MESH" for obj in bpy.data.objects)
    opened = bpy.ops.wm.open_mainfile(filepath=str(blend_path))
    blend_meshes = sum(obj.type == "MESH" for obj in bpy.data.objects)
    checks = {
        "staging_write": write_probe.read_text(encoding="utf-8") == "ok",
        "blend_saved": "FINISHED" in saved and blend_path.is_file(),
        "glb_exported": "FINISHED" in exported and glb_path.is_file(),
        "glb_reopened": "FINISHED" in imported and glb_meshes >= 1,
        "blend_reopened": "FINISHED" in opened and blend_meshes >= 1,
    }
    return {
        "schema_version": "1.1",
        "success": all(checks.values()),
        "checks": checks,
        "blender_version": bpy.app.version_string,
        "background": bool(bpy.app.background),
        "artifacts": {
            "blend_bytes": blend_path.stat().st_size if blend_path.is_file() else 0,
            "glb_bytes": glb_path.stat().st_size if glb_path.is_file() else 0,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    report_path = args.output / "doctor_probe.json"
    try:
        report = run_probe(args.output.resolve())
    except Exception as error:
        report = {
            "schema_version": "1.1",
            "success": False,
            "checks": {},
            "error": f"{type(error).__name__}: {error}",
        }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return 0 if report["success"] else 1


if __name__ == "__main__":
    from inf_agent.execution.run_asset import _exit

    _exit(main())
