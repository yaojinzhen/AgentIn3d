# Input and design

The current input is `<workspace>/request.json`: prompt, optional reference image,
explicit dimensions and forbidden items. `start` creates it from ordinary user input.
Inspect the actual image; image proportions do not establish real-world scale.
Technical choices and user revisions may be edited without a new request identity.
Each run snapshots the input/design and main source that it executes.

Use `design.md` as a concise reasoning aid when useful: identity, silhouette, visible
features, construction mechanism, attachments, materials and variation scale,
native reference and preview risks. There is no fixed byte limit. Avoid making
optional details into requirements or approximating continuous surfaces by many
small primitives. Use `design.json` only when explicit measurable constraints,
orientation or part-focused diagnostics are helpful; see [design_contracts.md](design_contracts.md).
