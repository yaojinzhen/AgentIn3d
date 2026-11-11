"""Non-destructive GLB material conversion using Infinigen baking primitives."""

from dataclasses import asdict, dataclass
from pathlib import Path

from inf_agent.workspace.contracts import ContractError, write_json_atomic


@dataclass(frozen=True)
class MaterialExportSettings:
    texture_resolution: int = 2048
    bake_samples: int = 4

    def __post_init__(self):
        for name, minimum, maximum in (
            ("texture_resolution", 64, 4096),
            ("bake_samples", 1, 128),
        ):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not minimum <= value <= maximum
            ):
                raise ContractError(
                    f"{name} must be an integer in [{minimum}, {maximum}]"
                )


# Infinigen's standard channel names are retained for apply_baked_tex.
CHANNELS = {
    "DIFFUSE": "Base Color",
    "ROUGHNESS": "Roughness",
    "METAL": "Metallic",
    "TRANSMISSION": "Transmission Weight",
    "ALPHA": "Alpha",
    "EMISSION": "Emission Color",
    "COAT": "Coat Weight",
    "COAT_ROUGHNESS": "Coat Roughness",
    "SHEEN": "Sheen Weight",
    "SHEEN_ROUGHNESS": "Sheen Roughness",
    "SPECULAR": "Specular IOR Level",
}


def _surface(material):
    """Trace nested Infinigen shader groups without flattening their texture graphs."""
    if not material.use_nodes:
        return None, None, None
    output = next(
        (
            node
            for node in material.node_tree.nodes
            if node.type == "OUTPUT_MATERIAL" and node.is_active_output
        ),
        None,
    )
    if output is None or not output.inputs["Surface"].is_linked:
        raise RuntimeError(
            f"material {material.name!r} has no connected surface output"
        )
    link = output.inputs["Surface"].links[0]
    groups = []
    while True:
        node = link.from_node
        if node.type == "REROUTE":
            link = node.inputs[0].links[0]
        elif node.type == "GROUP":
            groups.append(node)
            group_output = next(
                n
                for n in node.node_tree.nodes
                if n.type == "GROUP_OUTPUT" and n.is_active_output
            )
            target = next(
                socket
                for socket in group_output.inputs
                if socket.identifier == link.from_socket.identifier
            )
            if not target.is_linked:
                raise RuntimeError(
                    f"material {material.name!r} has an unconnected shader group output"
                )
            link = target.links[0]
        else:
            break

    def constant(socket, parents):
        if not socket.is_linked:
            return True, socket.default_value
        upstream = socket.links[0].from_node
        if upstream.type == "GROUP_INPUT" and parents:
            external = next(
                s
                for s in parents[-1].inputs
                if s.identifier == socket.links[0].from_socket.identifier
            )
            return constant(external, parents[:-1])
        return False, None

    # Group interface defaults are ordinary PBR constants, not procedural inputs.
    for socket in node.inputs:
        if socket.is_linked and hasattr(socket, "default_value"):
            found, value = constant(socket, groups)
            if found:
                value = tuple(value) if hasattr(value, "__len__") else value
                node.id_data.links.remove(socket.links[0])
                socket.default_value = value
    return output, node, link.to_socket


def _bake_materials(obj, destination, settings, native, bpy, prefix):
    surfaces = []
    channels = set()
    for material in obj.data.materials:
        if material is None:
            continue
        if not material.use_nodes:
            material.use_nodes = True
            material.node_tree.nodes.get("Principled BSDF").inputs[
                "Base Color"
            ].default_value = material.diffuse_color
        output, shader, target = _surface(material)
        if shader.type != "BSDF_PRINCIPLED":
            raise RuntimeError(
                f"material {material.name!r}: GLB baking requires a Principled surface; "
                "connect the surface to Principled BSDF instead of silently dropping its appearance"
            )
        if output.inputs["Displacement"].is_linked:
            raise RuntimeError(
                f"material {material.name!r}: realize displacement into geometry before GLB export"
            )
        shader.name, output.name = "Principled BSDF", "Material Output"
        properties = {
            socket.name: tuple(socket.default_value)
            if hasattr(socket.default_value, "__len__")
            else socket.default_value
            for socket in shader.inputs
            if hasattr(socket, "default_value")
        }
        linked = {socket.name for socket in shader.inputs if socket.is_linked}
        known = set(CHANNELS.values()) | {"Normal"}
        unsupported = linked - known
        if unsupported:
            raise RuntimeError(
                f"material {material.name!r}: unsupported linked GLB inputs: {sorted(unsupported)}"
            )
        channels.update(key for key, name in CHANNELS.items() if name in linked)
        if "Normal" in linked:
            channels.add("NORMAL")
        surfaces.append((material, output, shader, target, properties))
    if not native.uv_unwrap(
        obj,
        island_margin=2
        * bpy.context.scene.render.bake.margin
        / settings.texture_resolution,
    ):
        raise RuntimeError(f"UV unwrap failed for {obj.name}")

    # Bake normals with the original surface, then evaluate scalar/color inputs
    # through emission. This avoids lighting, metallic and coat contaminating albedo.
    if "NORMAL" in channels:
        native.bake_pass(
            obj,
            destination,
            settings.texture_resolution,
            "NORMAL",
            False,
            prefix,
            color_space="Non-Color",
        )
    for channel in sorted(channels - {"NORMAL"}):
        name = CHANNELS[channel]
        saved = []
        try:
            for material, output, shader, target, _ in surfaces:
                tree = shader.id_data
                link = target.links[0]
                saved.append((tree, target, link.from_socket, None))
                tree.links.remove(link)
                emission = tree.nodes.new("ShaderNodeEmission")
                saved[-1] = (tree, target, saved[-1][2], emission)
                source = shader.inputs.get(name)
                if source is not None and source.is_linked:
                    tree.links.new(
                        source.links[0].from_socket, emission.inputs["Color"]
                    )
                elif source is not None:
                    value = source.default_value
                    emission.inputs["Color"].default_value = (
                        tuple(value)
                        if hasattr(value, "__len__")
                        else (value, value, value, 1)
                    )
                else:
                    emission.inputs["Color"].default_value = (0, 0, 0, 1)
                tree.links.new(emission.outputs[0], target)
            native.bake_pass(
                obj,
                destination,
                settings.texture_resolution,
                channel,
                False,
                prefix,
                bake_type_override="EMIT",
                color_space="sRGB"
                if channel in {"DIFFUSE", "EMISSION"}
                else "Non-Color",
            )
        finally:
            for tree, target, source, emission in saved:
                if emission is not None:
                    tree.nodes.remove(emission)
                tree.links.new(source, target)

    # Preserve constants on every material, including coat, sheen, IOR and glass.
    # Do not use process_interfering_params, which only restores the last slot.
    for material, output, shader, _, _ in surfaces:
        if shader.id_data != material.node_tree:
            # Only the export copy is simplified. Baked inputs have already been
            # evaluated inside their original groups, with their external inputs.
            root_shader = material.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
            root_shader.name = "Principled BSDF"
            material.node_tree.links.new(
                root_shader.outputs["BSDF"], output.inputs["Surface"]
            )
    native.apply_baked_tex(obj, extra_channels=CHANNELS)
    for material, _, _, _, properties in surfaces:
        shader = material.node_tree.nodes["Principled BSDF"]
        for name, value in properties.items():
            socket = shader.inputs.get(name)
            if socket is not None:
                socket.default_value = value
        for channel in channels - {"NORMAL"}:
            socket = shader.inputs.get(CHANNELS[channel])
            node = material.node_tree.nodes.get(channel + "_node")
            if socket is not None and node is not None:
                material.node_tree.links.new(node.outputs["Color"], socket)
    return sorted(channels)


def export_glb(bpy, objects, path: Path, settings: MaterialExportSettings):
    """Export evaluated copies; restore the source scene even when conversion fails."""
    from infinigen.tools import export as native

    collections = ("objects", "meshes", "materials", "node_groups", "images", "scenes")
    before = {key: set(getattr(bpy.data, key)) for key in collections}
    window = bpy.context.window
    if window is None:
        raise RuntimeError("GLB export needs a Blender scene context")
    original_scene = window.scene
    selected = list(bpy.context.selected_objects)
    active = bpy.context.view_layer.objects.active
    report = {
        "backend": "infinigen.tools.export + Blender glTF",
        "settings": asdict(settings),
        "materials": [],
        "source_preserved": True,
    }
    try:
        depsgraph = bpy.context.evaluated_depsgraph_get()
        scene = bpy.data.scenes.new("__inf_agent_glb_export")
        clones = []
        for original in objects:
            evaluated = original.evaluated_get(depsgraph)
            mesh = bpy.data.meshes.new_from_object(
                evaluated, preserve_all_data_layers=True, depsgraph=depsgraph
            )
            clone = bpy.data.objects.new(original.name + "_export", mesh)
            clone.matrix_world = original.matrix_world.copy()
            scene.collection.objects.link(clone)
            for index, material in enumerate(mesh.materials):
                if material is not None:
                    mesh.materials[index] = native.deep_copy_material(
                        material, "_export"
                    )
            clones.append(clone)
        window.scene = scene
        window.view_layer = scene.view_layers[0]
        scene.view_layers[0].update()
        scene.render.engine = "CYCLES"
        scene.cycles.device = "CPU"
        scene.cycles.samples = settings.bake_samples
        scene.render.bake.margin = min(8, settings.texture_resolution // 32)
        destination = path.parent / "textures"
        for index, clone in enumerate(clones):
            bpy.ops.object.select_all(action="DESELECT")
            clone.select_set(True)
            bpy.context.view_layer.objects.active = clone
            needs_bake = False
            for material in clone.data.materials:
                if material is None:
                    continue
                output, shader, target = _surface(material)
                needs_bake |= output is not None and (
                    shader.type != "BSDF_PRINCIPLED"
                    or shader.id_data != material.node_tree
                    or any(socket.is_linked for socket in shader.inputs)
                    or output.inputs["Displacement"].is_linked
                )
            if needs_bake:
                destination.mkdir(exist_ok=True)
                with bpy.context.temp_override(
                    scene=scene,
                    view_layer=scene.view_layers[0],
                    active_object=clone,
                    object=clone,
                    selected_objects=[clone],
                    selected_editable_objects=[clone],
                ):
                    channels = _bake_materials(
                        clone, destination, settings, native, bpy, f"object_{index:03d}"
                    )
            else:
                channels = []
            report["materials"].extend(
                {
                    "name": material.name,
                    "mode": "baked" if channels else "direct_pbr",
                    "channels": channels,
                }
                for material in clone.data.materials
                if material is not None
            )
        bpy.ops.object.select_all(action="DESELECT")
        for clone in clones:
            clone.select_set(True)
        if clones:
            bpy.context.view_layer.objects.active = clones[0]
        result = bpy.ops.export_scene.gltf(
            filepath=str(path),
            export_format="GLB",
            use_selection=True,
            use_active_scene=True,
            export_apply=True,
        )
        if "FINISHED" not in result:
            raise RuntimeError(f"GLB export did not finish: {result}")
        from inf_agent.execution.artifact_validation import validate_glb

        report["validation"] = validate_glb(path)
        write_json_atomic(path.parent / "material_export.json", report)
        return report
    finally:
        window.scene = original_scene
        for key in collections:
            data = getattr(bpy.data, key)
            for block in set(data) - before[key]:
                data.remove(block, do_unlink=True)
        for obj in selected:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = active
