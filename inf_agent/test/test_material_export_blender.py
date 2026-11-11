"""Real material baking, PBR preservation and source-scene failure recovery."""

import json
import functools
import subprocess
import sys
import os
import struct
import tempfile
import unittest
from pathlib import Path
from inf_agent.execution.material_export import MaterialExportSettings, export_glb


def document(path):
    with path.open("rb") as stream:
        stream.read(12)
        size, _ = struct.unpack("<II", stream.read(8))
        return json.loads(stream.read(size))


def isolated(test):
    @functools.wraps(test)
    def run(self):
        if os.environ.get("INF_AGENT_MATERIAL_CHILD") == "1":
            return test(self)
        root = Path(__file__).resolve().parents[2]
        script = (
            "import sys,unittest; "
            f"sys.path.insert(0, {str(root / 'inf_agent/test')!r}); "
            "from inf_agent.execution.run_asset import _exit; "
            f"suite=unittest.defaultTestLoader.loadTestsFromName('test_material_export_blender.MaterialExportTests.{test.__name__}'); "
            "result=unittest.TextTestRunner().run(suite); "
            "_exit(0 if result.wasSuccessful() else 1)"
        )
        completed = subprocess.run(
            [sys.executable, "-B", "-c", script],
            cwd=root,
            env={**os.environ, "INF_AGENT_MATERIAL_CHILD": "1"},
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=180,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    return run


@unittest.skipUnless(
    os.environ.get("INF_AGENT_BLENDER_TESTS") == "1",
    "set INF_AGENT_BLENDER_TESTS=1 for actual Blender",
)
class MaterialExportTests(unittest.TestCase):
    def setUp(self):
        if os.environ.get("INF_AGENT_MATERIAL_CHILD") != "1":
            return
        import bpy

        self.bpy = bpy
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.mesh.primitive_cube_add()
        self.obj = bpy.context.object
        self.temp = tempfile.TemporaryDirectory(prefix="inf_agent_material_export_")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "asset.glb"

    def material(self, name, color):
        mat = self.bpy.data.materials.new(name)
        mat.use_nodes = True
        shader = mat.node_tree.nodes["Principled BSDF"]
        shader.inputs["Base Color"].default_value = color
        self.obj.data.materials.append(mat)
        return mat, shader

    @isolated
    def test_direct_pbr_glass_preserves_parameters_without_baking(self):
        material, shader = self.material("Glass", (0.12, 0.4, 0.8, 1))
        shader.inputs["Metallic"].default_value = 0.3
        shader.inputs["Coat Weight"].default_value = 0.4
        shader.inputs["Transmission Weight"].default_value = 0.5
        shader.inputs["IOR"].default_value = 1.45
        scene = self.bpy.context.scene
        counts = (len(self.bpy.data.materials), len(self.bpy.data.scenes))
        report = export_glb(
            self.bpy, [self.obj], self.path, MaterialExportSettings(128, 1)
        )
        data = document(self.path)
        self.assertEqual(len(data.get("images", [])), 0)
        self.assertEqual(len(data["meshes"]), 1)
        self.assertEqual(report["materials"][0]["mode"], "direct_pbr")
        mat = data["materials"][0]
        self.assertAlmostEqual(mat["pbrMetallicRoughness"]["baseColorFactor"][2], 0.8)
        self.assertAlmostEqual(
            mat["extensions"]["KHR_materials_transmission"]["transmissionFactor"], 0.5
        )
        self.assertAlmostEqual(
            mat["extensions"]["KHR_materials_clearcoat"]["clearcoatFactor"], 0.4
        )
        self.assertEqual(self.bpy.context.scene, scene)
        self.assertEqual(
            (len(self.bpy.data.materials), len(self.bpy.data.scenes)), counts
        )
        self.assertEqual(self.obj.data.materials[0], material)

    @isolated
    def test_nested_group_bakes_color_and_normal_and_preserves_both_materials(self):
        bpy = self.bpy
        mat, shader = self.material("Blue procedural", (0.02, 0.1, 0.8, 1))
        tree = mat.node_tree
        tree.nodes.remove(shader)
        group = bpy.data.node_groups.new("BlueGroup", "ShaderNodeTree")
        group.interface.new_socket(
            name="Shader", in_out="OUTPUT", socket_type="NodeSocketShader"
        )
        group.interface.new_socket(
            name="Roughness", in_out="INPUT", socket_type="NodeSocketFloat"
        )
        source = group.nodes.new("NodeGroupInput")
        output = group.nodes.new("NodeGroupOutput")
        principled = group.nodes.new("ShaderNodeBsdfPrincipled")
        principled.inputs["Coat Weight"].default_value = 0.37
        noise = group.nodes.new("ShaderNodeTexNoise")
        ramp = group.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].color = (0.01, 0.04, 0.2, 1)
        ramp.color_ramp.elements[1].color = (0.03, 0.2, 0.9, 1)
        bump = group.nodes.new("ShaderNodeBump")
        bump.inputs["Distance"].default_value = 0.01
        group.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
        group.links.new(ramp.outputs["Color"], principled.inputs["Base Color"])
        group.links.new(noise.outputs["Fac"], bump.inputs["Height"])
        group.links.new(bump.outputs["Normal"], principled.inputs["Normal"])
        group.links.new(source.outputs["Roughness"], principled.inputs["Roughness"])
        group.links.new(principled.outputs[0], output.inputs["Shader"])
        outer = bpy.data.node_groups.new("OuterGroup", "ShaderNodeTree")
        outer.interface.new_socket(
            name="Shader", in_out="OUTPUT", socket_type="NodeSocketShader"
        )
        nested = outer.nodes.new("ShaderNodeGroup")
        nested.node_tree = group
        nested.inputs["Roughness"].default_value = 0.23
        outer_output = outer.nodes.new("NodeGroupOutput")
        outer.links.new(nested.outputs[0], outer_output.inputs[0])
        node = tree.nodes.new("ShaderNodeGroup")
        node.node_tree = outer
        tree.links.new(node.outputs[0], tree.nodes["Material Output"].inputs["Surface"])
        glass, glass_shader = self.material("Constant glass", (0.8, 0.3, 0.1, 1))
        glass_shader.inputs["Coat Weight"].default_value = 0.62
        glass_shader.inputs["Transmission Weight"].default_value = 0.4
        glass_shader.inputs["IOR"].default_value = 1.46
        for face in self.obj.data.polygons:
            face.material_index = face.index % 2
        scene = bpy.context.scene
        report = export_glb(bpy, [self.obj], self.path, MaterialExportSettings(128, 1))
        data = document(self.path)
        self.assertTrue(report["validation"]["materials_valid"])
        self.assertEqual(len(data["images"]), 2)
        self.assertTrue(all("bufferView" in im for im in data["images"]))
        materials = data["materials"]
        self.assertAlmostEqual(
            materials[0]["extensions"]["KHR_materials_clearcoat"]["clearcoatFactor"],
            0.37,
            places=5,
        )
        self.assertAlmostEqual(
            materials[1]["extensions"]["KHR_materials_clearcoat"]["clearcoatFactor"],
            0.62,
            places=5,
        )
        self.assertAlmostEqual(
            materials[1]["extensions"]["KHR_materials_transmission"][
                "transmissionFactor"
            ],
            0.4,
            places=5,
        )
        self.assertAlmostEqual(
            materials[0]["pbrMetallicRoughness"]["roughnessFactor"], 0.23, places=5
        )
        self.assertIn("normalTexture", materials[0])
        self.assertTrue(
            all("baseColorTexture" in m["pbrMetallicRoughness"] for m in materials)
        )
        self.assertEqual(bpy.context.scene, scene)
        self.assertEqual(self.obj.data.materials[0], mat)
        self.assertTrue(principled.inputs["Base Color"].is_linked)
        self.assertEqual(node.node_tree, outer)
        self.assertEqual(len(self.obj.data.uv_layers), 1)
        images = sorted((self.path.parent / "textures").glob("*.png"))
        from PIL import Image

        with Image.open(next(p for p in images if "DIFFUSE" in p.name)) as image:
            colors = image.convert("RGB")
            self.assertGreater(max(b - r for r, g, b in colors.getdata()), 20)

    @isolated
    def test_unsupported_shader_failure_restores_source_scene_and_data(self):
        material, shader = self.material("Unsupported", (0.2, 0.3, 0.4, 1))
        tree = material.node_tree
        mix = tree.nodes.new("ShaderNodeMixShader")
        tree.links.new(shader.outputs[0], mix.inputs[1])
        tree.links.new(shader.outputs[0], mix.inputs[2])
        tree.links.new(mix.outputs[0], tree.nodes["Material Output"].inputs["Surface"])
        scene = self.bpy.context.scene
        counts = tuple(
            len(getattr(self.bpy.data, key))
            for key in ["objects", "meshes", "materials", "scenes"]
        )
        with self.assertRaisesRegex(RuntimeError, "Principled"):
            export_glb(self.bpy, [self.obj], self.path, MaterialExportSettings(128, 1))
        self.assertEqual(self.bpy.context.scene, scene)
        self.assertEqual(
            tuple(
                len(getattr(self.bpy.data, key))
                for key in ["objects", "meshes", "materials", "scenes"]
            ),
            counts,
        )
        self.assertEqual(self.obj.data.materials[0], material)
        self.assertFalse(self.path.exists())
