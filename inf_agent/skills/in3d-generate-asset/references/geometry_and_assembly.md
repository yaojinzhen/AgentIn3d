# Geometry and assembly contract

Read this before authoring a multi-part asset or any identity-bearing opening.
Declare optional constraints in design.json. Preview/export evaluate resulting meshes, not object names or claims. A simple single-body object may omit this registry.

## Register every semantic part instance

```python
from inf_agent.geometry import AssemblyBuilder, LocalFrame

assembly = AssemblyBuilder()
body_instance = assembly.register(
    "body", body, role="primary_shell", local_frame=LocalFrame()
)
handle_instance = assembly.register(
    "handle", handle, role="grip", parent_part_id="body"
)
```

One registration represents one counted part instance. Use distinct instance
ids when a required part permits multiple instances. Do not register an Empty,
collection, or one whole joined object as several parts. Convert curves to
meshes and finish topology-changing operations before registration, or confirm
that evaluated faces preserve the `inf_agent_part_index` FACE attribute.

The validator splits every evaluated object into face-connected islands. It
rejects unregistered or mixed-identity islands, registrations with no island,
and multiple islands for one registration unless the exact exception is
declared. Use `assembly.join_objects(...)`; ordinary `bpy.ops.object.join()`
does not prove that face identity survived.

## Build attachments from local frames

```python
assembly.anchor(
    body_instance, "body_handle_anchor",
    LocalFrame(origin=(0.18, 0.0, 0.12)),
)
assembly.anchor(
    handle_instance, "handle_mount_anchor",
    LocalFrame(origin=(-0.04, 0.0, 0.0)),
)
assembly.attach(
    "handle_to_body", handle_instance, body_instance,
    kind="welded",
    child_anchor_id="handle_mount_anchor",
    parent_anchor_id="body_handle_anchor",
)
```

The default alignment makes the declared anchor frames coincide in world
space. Parent hierarchy alone is not an attachment. `contact`, `welded`,
`hinged`, and `inserted` require measured surface contact. Excessive
intersection is a separate penetration failure. Each attachment is measured against
its exact child/parent registration pair. A touching sibling cannot satisfy it;
penetration exceptions also apply only to the declared instance pair.

For a carrier surface, `assembly.surface_anchor(registration_id, anchor_id,
face_index=<triangle>, barycentric=(u, v, w))` derives a stable local frame
from the triangle rather than copying world coordinates. Use it where a
dependent part follows a shell. When a constraint declares require_anchors: true, both
child and parent anchors are required; the validator checks
their registration ownership as well as measured contact.

After assigning Blender materials to faces, record each declared semantic region
and its owning parts with `assembly.material_region(region_id, part_ids,
material_name)`. `part_ids` must contain the literal part-id strings passed to
`assembly.register`, such as `["crane"]`, not its returned registration handle.
The validator counts evaluated faces by part identity and
material name. A declared region fails if any named part has no face using
that material. This verifies assignment, while the Agent image inspection judges whether
the shader actually looks like ceramic, wood, metal, etc.

A `spaced` attachment passes only when design.json has a `non_contact`
exemption, the child required_parts entry contains `non_contact:<attachment_id>`, and
design.json specifies finite non-negative `minimum_gap_m`/`maximum_gap_m` bounds
that contain the measured instance gap. `assembly.attach` must repeat the same
bounds; registry values cannot widen the design requirement. Never use this to excuse an accidental assembly gap.

## Prove openings with collision-free probes

Dark materials, decals, and inset disks do not prove a hole. Model real empty
space and declare a local segment through it after part placement. Finalization
stores the segment relative to the root, so later Factory placement of the whole
asset keeps the probe aligned:

```python
assembly.opening(
    "handle_opening", handle_instance,
    start=(0.0, -0.03, 0.0), end=(0.0, 0.03, 0.0),
    clearance_radius=0.006,
)
```

The default `kind="through_opening"` needs both endpoints outside the owner AABB
and a segment crossing its interior. For a blind cavity, declare
`kind="cavity_entrance"` in both design.json and `assembly.opening`: one endpoint
must be outside, while the other may end in the empty cavity. Use endpoints beyond
the bounds, not exactly on their faces. Internal short segments prove neither kind.

The center ray and four radius-offset rays must be clear of every evaluated asset
island, including other parts that block the owner opening. Closed-volume queries
also reject samples inside a solid. `CLEAR`, `BLOCKED`, and `UNRESOLVED` distinguish
sampled clearance, actual obstruction, and insufficient span/topology evidence;
only `CLEAR` passes. Non-closed owner geometry cannot prove an empty volume.
This is a sampled corridor check, not a continuous clearance or hole-topology proof;
inspect the relevant preview as well.

## Finalize and diagnose

Call `assembly.finalize(root)` after placement. For joined meshes, use
`root = assembly.join_objects(parts, name="...")`; that method also finalizes
the registry. The returned root must own or contain every registered mesh.

On preview failure, inspect `objective_validation.json` →
`layers.geometry_and_assembly`. Fix the measured missing registration, part
count, island, attachment gap, parent, penetration, opening, or connectivity.
Materials, face counts and files do not prove a declared assembly constraint is satisfied.

For result-file roles and diagnostic paths, see the maintained `inf_agent/docs/OUTPUT_FORMAT.md`.
