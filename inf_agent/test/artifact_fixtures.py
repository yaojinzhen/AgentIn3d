"""Binary triangle fixtures for static parsing tests; not Blender execution proof."""

import json
import struct


def triangle():
    binary = (
        struct.pack("<9f", 0, 0, 0, 1, 0, 0, 0, 1, 0)
        + struct.pack("<3H", 0, 1, 2)
        + b"\x00\x00"
    )
    doc = dict(
        asset={"version": "2.0"},
        scene=0,
        scenes=[{"nodes": [0]}],
        nodes=[{"mesh": 0}],
        meshes=[{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1}]}],
        buffers=[{"byteLength": 42}],
        bufferViews=[
            {"buffer": 0, "byteOffset": 0, "byteLength": 36},
            {"buffer": 0, "byteOffset": 36, "byteLength": 6},
        ],
        accessors=[
            {
                "bufferView": 0,
                "componentType": 5126,
                "count": 3,
                "type": "VEC3",
                "min": [0, 0, 0],
                "max": [1, 1, 0],
            },
            {"bufferView": 1, "componentType": 5123, "count": 3, "type": "SCALAR"},
        ],
    )
    return doc, binary


def glb_bytes(doc, binary):
    data = json.dumps(doc, allow_nan=False).encode()
    data += b" " * (-len(data) % 4)
    binary += b"\x00" * (-len(binary) % 4)
    return (
        struct.pack("<4sII", b"glTF", 2, 28 + len(data) + len(binary))
        + struct.pack("<II", len(data), 0x4E4F534A)
        + data
        + struct.pack("<II", len(binary), 0x004E4942)
        + binary
    )
