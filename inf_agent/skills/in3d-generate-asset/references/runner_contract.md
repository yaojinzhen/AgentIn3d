# Factory and runner conventions

Start the CLI with the resolved repository's root `.venv` interpreter from
`SKILL.md`. The runner, doctor and file-reopen subprocesses use that same
`sys.executable`, with the repository root as cwd. Missing `.venv` or dependencies
are installation failures; keep the interpreter fixed and refer to root `README.md`.

`asset.py` defines or exposes an Infinigen `AssetFactory` subclass. Direct and
indirect inheritance, native subclasses, computed constants and ordinary Python
module code are supported. Use `--factory <ClassName>` if selection is ambiguous;
otherwise the runner selects the single locally defined leaf subclass.

```python
from infinigen.core.placement.factory import AssetFactory

class ExampleFactory(AssetFactory):
    def create_asset(self, **params):
        root = ...  # build actual geometry and assign materials
        return root
```

Use the real base-class and native signatures. The runner instantiates the Factory
with the seed, passes `spec` / `dimensions` when accepted, and calls `spawn_asset`
and `finalize_assets` with controlled randomness. The root must be a linked Blender
Object containing visible, nonempty mesh geometry. Use meters; explicit width,
depth and height are final world-axis bounds.

Asset code owns geometry and materials; normally let the runner own cameras,
lights, rendering and exports so previews stay consistent. It executes trusted
local Python with the current user's permissions, as described in
`inf_agent/docs/USER_GUIDE.md`.

Use a close native Factory when applicable, or choose revolve, sweep, mesh/loft,
Geometry Nodes or controlled deformation based on the shape. Preserve real holes,
physical contact and material scale. Infinigen's default material path rejects Bump
nodes; Blender 4 removed `mesh.use_auto_smooth` / `mesh.auto_smooth_angle`. Optional
`lint` points out these known incompatibilities without a source approval protocol.

Each run preserves its main source and input configuration, captures logs and
metrics, renders multiple views and optional part-focus masks, and saves BLEND.
Export also writes GLB and independently reopens GLB/BLEND. Declared workspace-local dependencies are copied beside the source; use
`request.local_dependencies` and file-relative resource paths. Infinigen, Blender
and other external dependencies still use the root `.venv`. See the
`inf_agent/docs/OUTPUT_FORMAT.md` for result and snapshot file roles.


GLB export uses evaluated copies and Infinigen UV/baking/material helpers. The
original scene and procedural nodes are preserved for BLEND and preview. Constant
PBR values pass directly; linked inputs are baked. Read
`inf_agent/docs/GLB_EXPORT.md` for settings and supported shader surfaces.
