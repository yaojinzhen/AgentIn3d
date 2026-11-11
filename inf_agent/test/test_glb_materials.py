"""Material validation rejects broken images, texture references and missing UVs."""

import copy
import io
import struct
from PIL import Image
from artifact_fixtures import triangle, glb_bytes
from test_core_workflow import TemporaryCase
from inf_agent.execution.artifact_validation import (
    validate_glb,
    ArtifactValidationError,
)


class EmbeddedMaterialTests(TemporaryCase):
    def fixture(self):
        doc, binary = triangle()
        uv = struct.pack("<6f", 0, 0, 1, 0, 0, 1)
        uv_offset = len(binary)
        binary += uv
        image = io.BytesIO()
        Image.new("RGB", (4, 4), "blue").save(image, format="PNG")
        data = image.getvalue()
        doc["bufferViews"].extend(
            [
                {"buffer": 0, "byteOffset": uv_offset, "byteLength": len(uv)},
                {"buffer": 0, "byteOffset": len(binary), "byteLength": len(data)},
            ]
        )
        binary += data
        doc["buffers"][0]["byteLength"] = len(binary)
        doc["accessors"].append(
            {"bufferView": 2, "componentType": 5126, "count": 3, "type": "VEC2"}
        )
        prim = doc["meshes"][0]["primitives"][0]
        prim["attributes"]["TEXCOORD_0"] = 2
        prim["material"] = 0
        doc["materials"] = [
            {"pbrMetallicRoughness": {"baseColorTexture": {"index": 0}}}
        ]
        doc["textures"] = [{"source": 0}]
        doc["images"] = [{"bufferView": 3, "mimeType": "image/png"}]
        return doc, binary

    def parse(self, doc, binary):
        path = self.root / "asset.glb"
        path.write_bytes(glb_bytes(doc, binary))
        return validate_glb(path)

    def test_embedded_texture_decodes_and_constant_material_needs_no_image(self):
        report = self.parse(*self.fixture())
        self.assertTrue(report["materials_valid"])
        self.assertEqual(report["embedded_images"], [{"width": 4, "height": 4}])
        self.assertEqual(self.parse(*triangle())["textures"], 0)

    def test_missing_uv_invalid_binding_and_truncated_image_fail(self):
        doc, binary = self.fixture()
        variants = []
        missing = copy.deepcopy(doc)
        del missing["meshes"][0]["primitives"][0]["attributes"]["TEXCOORD_0"]
        variants.append((missing, binary))
        invalid = copy.deepcopy(doc)
        invalid["textures"][0]["source"] = 9
        variants.append((invalid, binary))
        truncated = copy.deepcopy(doc)
        truncated["bufferViews"][3]["byteLength"] = 16
        variants.append((truncated, binary))
        external = copy.deepcopy(doc)
        external["images"][0] = {"uri": "not_embedded.png"}
        variants.append((external, binary))
        for document, payload in variants:
            with (
                self.subTest(document=document),
                self.assertRaises(ArtifactValidationError),
            ):
                self.parse(document, payload)
