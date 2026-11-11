# Visual checks and repair

Read the run's `objective_validation.json`, then open the actual images in `previews/`.
Inspect recognizable identity and silhouette, required visible features, assembly
contact, proportions, material appearance, surface quality and multiview consistency.
A visible hole, thickness or edge must be real geometry where the request needs it.
Colored materials should read correctly under the preview lighting; a gray or washed
out render is a concrete issue to investigate. Inspect part-focus views when the
design declares them. Names and source tokens do not establish visible features.

Prioritize identity/silhouette, required features, assembly, proportion, material,
then fine surface detail. Use `failure_domains` and measured diagnostics to locate
problems. Fix the relevant design or source, run again and inspect both the target
and any regression. No repair-plan JSON or immutable design manifest is required. A workspace
defaults to 20 allocated preview/export runs, including failures; keep room for
final export. Inspect status before rerunning and stop at the limit. Repeating a seed or exploring another seed is permitted;
stop when the requested task is satisfied or further work needs user input.

A geometry failure or corrupt export must be reported. Artifact paths can still be
returned to aid inspection; their availability is separate from quality. The runtime
records `visual_status=NOT_CHECKED` and does not judge general likeness. Describe
what you actually observed; when image inspection is unavailable, say so.

`export` reruns the current source into another run. Check that run's images and
objective report before claiming the exported model's visual quality. Files from
older runs remain available; use exact paths so the user can identify the result.

Inspect the imported GLB material appearance as well as BLEND previews;
`inf_agent/docs/GLB_EXPORT.md` describes automatic baking and its limits.
