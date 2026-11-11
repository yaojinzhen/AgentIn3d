---
name: in3d-generate-asset
description: Create or repair a procedural static single-object Infinigen/Blender asset from text, a single-subject image, or both. Use when geometry or materials must change; use in3d-run-asset for execution of existing code.
---

# Generate an In3D asset

Resolve the installed Skill directory junction/symlink first. The repository
root is `Path(skill_directory).resolve().parents[2]`. Run CLI commands there;
`inf_agent/...` paths below are relative to that root, while `references/...`
paths are relative to this Skill directory.

Use only the resolved repository's `.venv/Scripts/python.exe` on Windows or
`.venv/bin/python` on Linux/macOS. Verify that executable exists before running
the CLI; if missing, stop execution and point to the root `README.md` installation
instructions. Do not fall back to PATH Python, Conda, another checkout, or `uv run`.
Run with the repository root as cwd. Examples below use Linux/macOS syntax;
in Windows PowerShell replace `./.venv/bin/python` with
`& .\.venv\Scripts\python.exe`. Quote absolute paths containing spaces.
The Agent runtime does not require uv; child processes inherit `sys.executable`.

Build an independently inspectable static object using Infinigen and Blender APIs.
The Agent designs and writes `asset.py`; the execution service runs it and returns
artifacts and objective diagnostics. The user guide at `inf_agent/docs/USER_GUIDE.md`
describes the 1.1 interface.

See `inf_agent/docs/OUTPUT_FORMAT.md` for result files,
status semantics and exact diagnostic field paths.

## Input and workspace

Preserve the user's input and inspect any supplied image. Choose reasonable defaults
for omitted dimensions or finish; ask when an ambiguity changes identity or main
topology. Do not ask the user to author framework schemas.

Create a workspace from the repository root, for example:

```bash
./.venv/bin/python -m inf_agent.cli start --asset-id apple --prompt "a ripe red apple"
```

An optional `--image <path>` stores the reference. `--width`, `--depth`, `--height`
are explicit dimensions in meters. The command creates `request.json` and an
`asset.py` skeleton; it does not run Blender. Use an explicit `--workspace <path>`
when a different directory is appropriate. Existing directories are never overwritten.
For an existing current-format workspace, inspect its input, source, and latest
images with `status --workspace <path>`. Input and technical design may be revised
in place; each subsequent run preserves its own input and source snapshot.

When authoring local helpers or resources, maintain optional
`request.json.local_dependencies` as workspace-relative file/directory paths.
They are copied beside `input/source/asset.py`, preserving package/resource paths;
undeclared helpers are not read from the live workspace. Use `Path(__file__).parent`
for textures/data. Ordinary, package-relative and delayed imports use this snapshot
through construction and finalization; process cwd remains the repository root.
The reference image and any design.md are copied separately into that run's input;
third-party modules still come from the current environment.

## Knowledge and modeling

Query only the knowledge relevant to the construction:

```bash
./.venv/bin/python -m inf_agent.cli query object --query "apple"
./.venv/bin/python -m inf_agent.cli query pattern --query "rounded organic mass"
./.venv/bin/python -m inf_agent.cli query api --query "from_pydata"
./.venv/bin/python -m inf_agent.cli query material --query "fruit skin"
./.venv/bin/python -m inf_agent.cli read --document <path-relative-to-modeling_docs>
./.venv/bin/python -m inf_agent.cli read --symbol <repository.module:Symbol>
```

Pass query `document_path` or any `documents[]` entry directly to `read --document`;
pass `source_symbols[]` entries to `read --symbol`. Headings are separate. Typed
`source_references[]` may instead point to a directory, module or external API.

Read the full relevant leaf and exact source before relying on a nontrivial API,
node socket or native lifecycle. A route excerpt is a starting point. Ordinary
source/document reads work too; there is no required plan, receipt, reading log,
or claim-to-call manifest. Query results are candidates, not proof of suitability.
Use a close native Factory or a narrow adaptation when it fits. Otherwise select
a construction suited to the shape: revolve for axial shells, sweep for path-like
parts, mesh/loft for continuous shells, real negative space for identity-bearing
holes, fields for repetitions, and controlled deformation for organic mass.

Use a brief `design.md` when it helps clarify silhouette, construction, materials,
connections and preview risks. Write optional `design.json` only for measurable
constraints, orientation or semantic focus views; see
[references/design_contracts.md](references/design_contracts.md). Simple single-mesh
objects do not need part manifests or AssemblyBuilder. For multipart construction,
read [references/geometry_and_assembly.md](references/geometry_and_assembly.md).
For Factory and rendering conventions read
[references/runner_contract.md](references/runner_contract.md).

## Preview, repair and export

```bash
./.venv/bin/python -m inf_agent.cli lint --source <workspace>/asset.py
./.venv/bin/python -m inf_agent.cli preview --workspace <workspace> [--factory <ClassName>]
```

`lint` is an optional syntax/API diagnostic. Preview runs the current code and
creates a fresh `runs/<run-id>/`; no identity, approval or prior-check report is
required. Factory naming and indirect inheritance are supported. When the module
defines several candidate factories, select one with `--factory`.

Inspect `objective_validation.json` and the actual perspective, front, side, top,
opposite perspective and relevant part-focus images. Files, part names, node counts
and mesh metrics alone do not prove likeness or requested material appearance.
Follow [references/visual_check_and_repair.md](references/visual_check_and_repair.md)
for quality checks and repair priorities. Edit the design or source and run again;
no repair-plan file or frozen design manifest is required. The default workspace
budget is 20 allocated preview/export runs, including failures; final export
also consumes one run. Check `status.run_budget` and keep room for final export.
Stop at the limit and report the best current result; increase `max_runs` only
when the user asks for more work, using an explicit `--limits` override.
Stop when the requested quality is achieved, the user stops the task,
or a concrete missing capability/input prevents further progress.

Export the current implementation when appropriate:

```bash
./.venv/bin/python -m inf_agent.cli export --workspace <workspace>
./.venv/bin/python -m inf_agent.cli validate --run <run-directory>
```

Export builds a new run, preserves the procedural BLEND and converts linked
Principled material inputs to embedded GLB textures using Infinigen baking helpers.
Defaults are 2048 pixels and 4 bake samples; `--texture-resolution` / `--bake-samples`
can adjust them. Constant PBR materials do not need textures. Inspect
`material_export.json`; unsupported shader surfaces fail explicitly. See
`inf_agent/docs/GLB_EXPORT.md` for supported inputs and conversion boundaries.
Blender independently reopens both files.
Inspect the exported run's images when judging its appearance. Return exact artifact
paths and describe any remaining defect. The service reports `visual_status=NOT_CHECKED`;
your actual image inspection supplies the visual conclusion. It does not need a
separate authenticated reviewer or delivery approval. If image inspection is
unavailable, report that visual quality was not verified.
