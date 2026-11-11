# Optional measurable design

A simple object can omit `design.json`. Defaults are front `-Y`, up `+Z`, with no
semantic parts, material regions or focus requirements. Absolute user dimensions
belong in `request.json.explicit_dimensions_m`; the generated geometry must honor them.

Use this optional shape for a multipart object (only include relevant fields):

```json
{
  "front_axis": "-Y",
  "up_axis": "+Z",
  "expected_bbox_or_ratio_ranges": {"width_to_height": [0.5, 0.9]},
  "required_parts": [
    {"part_id": "body", "role": "primary_shell"},
    {"part_id": "handle", "parent_part_id": "body"}
  ],
  "attachment_constraints": [
    {"attachment_id": "handle_mount", "part_id": "handle", "parent_part_id": "body", "kind": "contact"}
  ],
  "required_openings_or_negative_spaces": [
    {"feature_id": "handle_hole", "owner_part_id": "handle"}
  ],
  "material_regions": [
    {"region_id": "wood_body", "part_ids": ["body"], "semantics": "brown wood"}
  ],
  "review_view_plan": [
    {"view_id": "handle_detail", "target_part_ids": ["body", "handle"]}
  ]
}
```

Part counts default to one; override `minimum_count` / `maximum_count` for repeated
instances. `parent_part_id` describes the semantic relationship. Register the actual
mesh instances with AssemblyBuilder and bind declared attachments, opening probes
and material regions. A second part manifest is derived automatically.

Opening kind defaults to `through_opening` (two exterior probe endpoints).
Use `cavity_entrance` for a blind cavity (one exterior endpoint); repeat the kind in
`assembly.opening`. Both measure sampled empty corridors through the owner bounds,
and other asset parts can obstruct them.

Attachment kinds are `contact`, `welded`, `inserted`, `hinged`, `spaced`. Add
`require_anchors: true` when both sides must use valid explicit anchor frames.
Spaced attachments require finite `minimum_gap_m` / `maximum_gap_m`, a
`geometry_exemptions` entry `{"kind":"non_contact","target_id":"<attachment-id>"}`,
and `"non_contact:<attachment-id>"` in the child part's `exemptions`.
For deliberate penetrations or multi-island parts, use the corresponding
`penetration` / `multi_island` exception in both locations. Explain deliberate
exceptions in the design; they should not conceal accidental gaps or intersections.

Part IDs and view IDs are path-safe names. Axes must be orthogonal. Only declare
constraints supported by user input or justified design choices; there is no evidence
locator schema, modeling-route enum, knowledge manifest or required reading receipt.
Changes take effect on the next run. Code/design declarations are checked against
measured geometry, not treated as proof that a requested feature exists.
