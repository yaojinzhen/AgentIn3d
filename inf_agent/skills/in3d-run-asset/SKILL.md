---
name: in3d-run-asset
description: Execute, export, validate, or diagnose an existing current-format Infinigen asset workspace. Use when asset.py exists and geometry or material authoring is not requested; use in3d-generate-asset for modeling changes.
---

# Run an In3D asset

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

Use the existing workspace and the repository's root `.venv` to execute its current `asset.py`.
The user guide at `inf_agent/docs/USER_GUIDE.md` documents current-format inputs and outputs.
No old generated-result format is supported.

See `inf_agent/docs/OUTPUT_FORMAT.md` for result files,
status semantics and exact diagnostic field paths.

```bash
./.venv/bin/python -m inf_agent.cli status --workspace <workspace>
./.venv/bin/python -m inf_agent.cli preview --workspace <workspace> [--factory <ClassName>]
./.venv/bin/python -m inf_agent.cli export --workspace <workspace> [--factory <ClassName>]
./.venv/bin/python -m inf_agent.cli validate --run <run-directory>
```

Preview saves a Blender file and multiview images; export also writes GLB.
Export preserves the procedural BLEND and bakes linked Principled inputs into
embedded GLB textures (default 2048 pixels, 4 bake samples). See
`inf_agent/docs/GLB_EXPORT.md` and inspect `material_export.json`.
Both check current 3D files in an independent Blender process. `validate` repeats
that reopen and checks every requested view/mask; it uses stored geometry facts
for the design checks. Preview and export each execute a new run of the current source. Existing runs are
kept independently, and no prior self-check, knowledge receipt, repair plan,
review identity or acceptance state is required. Each workspace defaults to
20 allocated preview/export runs, including failures. `validate` and `status`
do not consume runs. Stop at the limit; use an explicit `--limits` max_runs
override only when the user requests a larger budget.

Inspect the actual output images if visual verification is part of the request.
Report `execution_success`, `objective_success`, artifact paths, and any concrete
defect. A valid file or healthy mesh does not prove visual likeness. Missing image
inspection must be reported as unverified visual quality, not a passing visual claim.

For failures, preserve `result.error` as the original type/message and inspect
`result.process` separately for exit/timeout details. Missing or corrupt artifacts
are output failures; they do not by themselves justify changing geometry.

For failures, use [references/execution_and_diagnostics.md](references/execution_and_diagnostics.md).
Use `doctor` explicitly when environment capabilities are in doubt. Do not silently
change Python environments. Route requested geometry/material changes to the
generation Skill; ordinary execution does not require authoring protocol files.
