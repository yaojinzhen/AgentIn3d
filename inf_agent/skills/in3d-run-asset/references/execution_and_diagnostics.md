# Execution and diagnosis

Use the shared `inf_agent/docs/OUTPUT_FORMAT.md` for file roles,
status fields and an executable diagnostic-reading example.

Resolve the installed Skill link and use that repository's root `.venv`, as in
`SKILL.md`; cwd remains the repository root. The commands below use Linux/macOS
syntax; on Windows PowerShell use `& .\.venv\Scripts\python.exe` instead.
If the executable or a dependency is missing, report the expected path and error
and refer to root `README.md`; do not retry under another Python or require uv.

`preview --workspace <path>` and `export --workspace <path>` execute a new run.
`status` returns current input and the latest allocated run (its result may be
missing after interruption). `validate --run` checks stored geometry facts,
fully decodes requested images/masks, and independently reopens current 3D files.
It does not reconstruct the source or remeasure the full design geometry. These operations
have no acceptance or identity workflow. Workspaces must use schema_version="2"; incompatible legacy results are not migrated.

For local modules/resources, inspect `request.json.local_dependencies`: it is an
optional list of workspace-relative files/directories. The run copies these beside
`input/source/asset.py`; it does not fall back to undeclared live workspace files.
Use file-relative resource paths. `input_context` describes copied files and the
current-environment third-party dependency boundary. Reference images and design.md
are captured into the run input; changing originals does not change that snapshot.
A missing helper should be declared when it is a local input, not worked around by
changing global cwd. Details are in the `inf_agent/docs/USER_GUIDE.md`.

Read `result.error` first for the original type/message. `validation.json` is the
unaltered child report; `process_status.json` and `result.process` hold parent
exit/timeout facts separately. A missing or corrupt child report is identified by
`execution_report_status` rather than silently replaced.

Use `process.log` for startup/timeout, `run.log` for Factory/build exceptions,
`reopen.log` / `artifact_reopen.json` for current-file reopen failures, and
`objective_validation.json` for geometry, proportions, materials, views and files.
Artifact failures use the `artifacts` domain; dependency imports use `environment`,
and process/report failures use `process`. Ordinary build exceptions remain
`construction` failures.

In `objective_validation.json → layers.artifact_validation`, `files_usable` and `focus_evidence` distinguish
usable files from visible target pixels. Every expected view and visible/potential
mask must decode at the requested size. Empty/transparent masks or visible pixels
outside the potential mask fail. Successful evidence still does not prove visual
likeness. `--no-render` marks images as NOT_REQUESTED. A failed run remains in its
own directory and does not block the next execution. Query relevant diagnostics:

```bash
./.venv/bin/python -m inf_agent.cli query troubleshoot --query "<actual error or failed domain>"
./.venv/bin/python -m inf_agent.cli doctor
```

Use `--limits <json>` to override implemented rendering, complexity, time and output
limits when the task needs them. Observe the actual failure before changing a limit.
Return concrete output paths and distinguish execution success, objective validity
and visual observations. Modeling changes belong in the generation Skill.


Preview/export share a default workspace allocation limit of 20. Failed and
interrupted allocated runs count; status and validate do not. On limit exhaustion,
inspect existing output and stop; a user-requested larger budget can use a limits
JSON such as {"max_runs": 30}. Do not delete evidence to free slots.

For GLB, inspect material_export.json and the imported asset appearance. Constant
PBR values pass directly; linked Principled inputs are baked in a separate export
scene using Infinigen helpers. Procedural source nodes remain in scene.blend.
Supported settings and limitations: `inf_agent/docs/GLB_EXPORT.md`.
