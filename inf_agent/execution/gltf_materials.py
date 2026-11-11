"""Validate embedded GLB images, texture bindings and required UV sets."""

import tempfile
from PIL import Image


def validate_material_document(doc, binary, fail):
    def records(key):
        values = doc.get(key, [])
        if not isinstance(values, list) or any(
            not isinstance(value, dict) for value in values
        ):
            fail(f"GLB {key} must be an object array")
        return values

    def index(value, values, label):
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or not 0 <= value < len(values)
        ):
            fail(f"{label} index is out of range")
        return values[value]

    images, textures, materials = (
        records("images"),
        records("textures"),
        records("materials"),
    )
    views, samplers = records("bufferViews"), records("samplers")
    decoded = []
    for image in images:
        if "uri" in image or image.get("mimeType") not in {"image/png", "image/jpeg"}:
            fail("GLB textures require embedded PNG/JPEG images")
        view = index(image.get("bufferView"), views, "image.bufferView")
        size, offset = view["byteLength"], view.get("byteOffset", 0)
        if size > 128 * 1024 * 1024:
            fail("embedded image exceeds 128 MiB")
        with tempfile.SpooledTemporaryFile(max_size=1024 * 1024) as stream:
            binary.stream.seek(binary.offset + offset)
            remaining = size
            while remaining:
                chunk = binary.stream.read(min(remaining, 64 * 1024))
                if not chunk:
                    fail("embedded image is truncated")
                stream.write(chunk)
                remaining -= len(chunk)
            stream.seek(0)
            try:
                with Image.open(stream) as pixels:
                    if pixels.format not in {"PNG", "JPEG"}:
                        fail("embedded image format is not PNG/JPEG")
                    dimensions = pixels.size
                    pixels.verify()
                stream.seek(0)
                with Image.open(stream) as pixels:
                    pixels.load()
                decoded.append({"width": dimensions[0], "height": dimensions[1]})
            except (
                OSError,
                ValueError,
                SyntaxError,
                Image.DecompressionBombError,
            ) as error:
                fail(f"embedded image cannot be decoded: {error}")
    for texture in textures:
        index(texture.get("source"), images, "texture.source")
        if "sampler" in texture:
            index(texture["sampler"], samplers, "texture.sampler")

    def bindings(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key.endswith("Texture") and isinstance(item, dict):
                    index(item.get("index"), textures, key)
                    coord = (
                        item.get("extensions", {})
                        .get("KHR_texture_transform", {})
                        .get("texCoord", item.get("texCoord", 0))
                    )
                    if (
                        isinstance(coord, bool)
                        or not isinstance(coord, int)
                        or coord < 0
                    ):
                        fail("texture texCoord must be a non-negative integer")
                    yield coord
                else:
                    yield from bindings(item)
        elif isinstance(value, list):
            for item in value:
                yield from bindings(item)

    uv_sets = [set(bindings(material)) for material in materials]
    for mesh in doc.get("meshes", []):
        for primitive in mesh.get("primitives", []):
            if "material" in primitive:
                material = primitive["material"]
                index(material, materials, "primitive.material")
                for coord in uv_sets[material]:
                    if f"TEXCOORD_{coord}" not in primitive.get("attributes", {}):
                        fail("textured primitive is missing its required UV attribute")
    return {
        "materials_valid": True,
        "materials": len(materials),
        "textures": len(textures),
        "embedded_images": decoded,
    }
