"""Static checks for embedded, uncompressed glTF mesh geometry (not full glTF)."""

import math


def validate_mesh_document(doc, binary, fail):
    def integer(v, label, minimum=0):
        if not isinstance(v, int) or isinstance(v, bool) or v < minimum:
            fail(f"{label}: expected integer >= {minimum}")
        return v

    def records(key, required=False):
        values = doc.get(key, [])
        if (
            not isinstance(values, list)
            or any(not isinstance(x, dict) for x in values)
            or (required and not values)
        ):
            fail(
                f"GLB {key}: expected "
                + ("non-empty " if required else "")
                + "object array"
            )
        return values

    def ref(value, values, label):
        value = integer(value, label)
        if value >= len(values):
            fail(f"{label}: index is out of range")
        return values[value]

    buffers = records("buffers", True)
    if len(buffers) != 1 or "uri" in buffers[0]:
        fail("GLB mesh profile requires one embedded BIN buffer")
    length = integer(buffers[0].get("byteLength"), "buffer.byteLength", 1)
    if not length <= len(binary) <= length + 3:
        fail("GLB BIN length does not match buffer.byteLength")
    views = records("bufferViews", True)
    for view in views:
        ref(view.get("buffer"), buffers, "bufferView.buffer")
        offset = integer(view.get("byteOffset", 0), "bufferView.byteOffset")
        size = integer(view.get("byteLength"), "bufferView.byteLength", 1)
        if offset + size > length:
            fail("bufferView exceeds embedded buffer range")
        if "byteStride" in view:
            stride = integer(view["byteStride"], "bufferView.byteStride", 4)
            if stride > 252 or stride % 4:
                fail("invalid bufferView.byteStride")
    accessors = records("accessors", True)
    components = {
        5120: ("b", 1),
        5121: ("B", 1),
        5122: ("h", 2),
        5123: ("H", 2),
        5125: ("I", 4),
        5126: ("f", 4),
    }
    widths = {
        "SCALAR": 1,
        "VEC2": 2,
        "VEC3": 3,
        "VEC4": 4,
        "MAT2": 4,
        "MAT3": 9,
        "MAT4": 16,
    }
    layouts = []
    for a in accessors:
        if "sparse" in a:
            fail("sparse accessors are outside the current embedded mesh profile")
        component = a.get("componentType")
        dtype = a.get("type")
        if (
            not isinstance(component, int)
            or component not in components
            or not isinstance(dtype, str)
            or dtype not in widths
        ):
            fail("accessor has an invalid componentType or type")
        if "normalized" in a and not isinstance(a["normalized"], bool):
            fail("accessor.normalized must be a bool")
        view = ref(a.get("bufferView"), views, "accessor.bufferView")
        count = integer(a.get("count"), "accessor.count", 1)
        fmt, size = components[component]
        element = size * widths[dtype]
        if dtype.startswith("MAT"):
            columns = int(dtype[-1])
            element = columns * ((columns * size + 3) // 4 * 4)
        offset = integer(a.get("byteOffset", 0), "accessor.byteOffset")
        stride = view.get("byteStride", element)
        if (
            stride < element
            or offset % size
            or (view.get("byteOffset", 0) + offset) % size
            or offset + (count - 1) * stride + element > view["byteLength"]
        ):
            fail("accessor exceeds bufferView range or has invalid alignment/stride")
        layouts.append((view.get("byteOffset", 0) + offset, stride, fmt, size))
    meshes = records("meshes", True)
    materials = records("materials")
    triangle_meshes = set()
    checked_positions = set()
    for mesh_index, mesh in enumerate(meshes):
        primitives = mesh.get("primitives")
        if (
            not isinstance(primitives, list)
            or not primitives
            or any(not isinstance(x, dict) for x in primitives)
        ):
            fail("GLB mesh has no usable primitives")
        for primitive in primitives:
            attrs = primitive.get("attributes")
            if not isinstance(attrs, dict) or "POSITION" not in attrs:
                fail("primitive requires POSITION attributes")
            position = ref(attrs["POSITION"], accessors, "primitive.POSITION")
            if position["type"] != "VEC3" or position["componentType"] != 5126:
                fail("POSITION must use float VEC3 accessors")
            for name, index in attrs.items():
                attribute = ref(index, accessors, f"primitive.{name}")
                if attribute["count"] != position["count"]:
                    fail("primitive attribute counts disagree")
            start, stride, _, _ = layouts[attrs["POSITION"]]
            if attrs["POSITION"] not in checked_positions:
                for values in binary.values("<3f", start, stride, position["count"]):
                    if not all(math.isfinite(x) for x in values):
                        fail("POSITION contains non-finite coordinates")
                checked_positions.add(attrs["POSITION"])
            count = position["count"]
            if "indices" in primitive:
                index = primitive["indices"]
                accessor = ref(index, accessors, "primitive.indices")
                if (
                    accessor["type"] != "SCALAR"
                    or accessor["componentType"] not in (5121, 5123, 5125)
                    or accessor.get("normalized", False)
                ):
                    fail("primitive indices must use unsigned integer SCALAR accessors")
                start, stride, fmt, _ = layouts[index]
                count = accessor["count"]
                for (value,) in binary.values("<" + fmt, start, stride, count):
                    if value >= position["count"]:
                        fail("primitive index exceeds POSITION vertex count")
            mode = integer(primitive.get("mode", 4), "primitive.mode")
            if (
                mode > 6
                or count < (1 if mode == 0 else 2 if mode in (1, 2, 3) else 3)
                or (mode == 4 and count % 3)
                or (mode == 1 and count % 2)
            ):
                fail("primitive mode/count cannot form complete primitives")
            if mode in (4, 5, 6):
                triangle_meshes.add(mesh_index)
            if "material" in primitive:
                ref(primitive["material"], materials, "primitive.material")
            targets = primitive.get("targets", [])
            if not isinstance(targets, list) or any(
                not isinstance(x, dict) for x in targets
            ):
                fail("primitive.targets must be attribute objects")
            for target in targets:
                for index in target.values():
                    if (
                        ref(index, accessors, "morph accessor")["count"]
                        != position["count"]
                    ):
                        fail("morph attribute count disagrees with POSITION")
    nodes = records("nodes", True)
    scenes = records("scenes", True)
    for node in nodes:
        if "mesh" in node:
            ref(node["mesh"], meshes, "node.mesh")
        children = node.get("children", [])
        if not isinstance(children, list):
            fail("node.children must be node indices")
        for index in children:
            ref(index, nodes, "node.children")
    for scene in scenes:
        if not isinstance(scene.get("nodes", []), list):
            fail("scene.nodes must be node indices")
        for index in scene.get("nodes", []):
            ref(index, nodes, "scene.nodes")
    # Reject cycles even in nodes outside the active scene.
    done = set()
    for first in range(len(nodes)):
        active = set()
        stack = [(first, False)]
        while stack:
            index, leaving = stack.pop()
            if leaving:
                active.remove(index)
                done.add(index)
            elif index in active:
                fail("node graph contains a cycle")
            elif index not in done:
                active.add(index)
                stack.append((index, True))
                stack.extend((x, False) for x in nodes[index].get("children", []))
    scene = ref(doc.get("scene", 0), scenes, "scene")
    reachable = set()
    pending = list(scene.get("nodes", []))
    while pending:
        index = pending.pop()
        if index not in reachable:
            reachable.add(index)
            pending.extend(nodes[index].get("children", []))
    if not any(nodes[n].get("mesh") in triangle_meshes for n in reachable):
        fail("active GLB scene contains no reachable triangle mesh")
    return dict(
        semantic_valid=True,
        semantic_coverage="embedded_uncompressed_mesh_profile",
        triangle_meshes=len(triangle_meshes),
        accessors=len(accessors),
    )
