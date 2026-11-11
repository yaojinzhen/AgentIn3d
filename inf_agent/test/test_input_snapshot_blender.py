"""Real Blender checks for frozen local modules and file-relative resources."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from inf_agent.execution.service import REPO_ROOT, run_workspace
from inf_agent.execution.process import run_process
from inf_agent.workspace.contracts import load_json, write_json_atomic
from inf_agent.workspace.manager import create_workspace

ASSET = """from pathlib import Path
import bpy
from infinigen.core.placement.factory import AssetFactory
from .local_pkg.shape import add_shape
class LocalFactory(AssetFactory):
    def __init__(self, factory_seed, *, spec):
        super().__init__(factory_seed)
        self.spec = spec
    def create_asset(self, **params):
        from lazy_helper import color
        assert Path.cwd() == Path(__EXPECTED_CWD__)
        obj = add_shape()
        material = bpy.data.materials.new('FrozenTexture')
        material.use_nodes = True
        image = bpy.data.images.load(str(Path(__file__).parent / 'textures' / 'skin.png'))
        assert image.pixels[0] > 0.9 and image.pixels[2] < 0.1
        texture = material.node_tree.nodes.new('ShaderNodeTexImage')
        texture.image = image
        material.node_tree.links.new(texture.outputs['Color'], material.node_tree.nodes['Principled BSDF'].inputs['Base Color'])
        material.diffuse_color = color
        obj.data.materials.append(material)
        reference = bpy.data.images.load(self.spec['request']['reference_image'])
        assert reference.pixels[2] > 0.9 and reference.pixels[0] < 0.1
        return obj
    def finalize_assets(self, obj):
        from late_finalize import finish
        finish(obj)
"""


@unittest.skipUnless(
    os.environ.get("INF_AGENT_BLENDER_TESTS") == "1",
    "set INF_AGENT_BLENDER_TESTS=1 for actual Blender",
)
class InputSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="inf_agent_input_snapshot_")
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name) / "工作区 with spaces"
        create_workspace(self.workspace, prompt="a textured block")

    def test_frozen_helpers_textures_and_reference_run_outside_repository(self):
        ws = self.workspace
        (ws / "asset.py").write_text(
            ASSET.replace("__EXPECTED_CWD__", repr(REPO_ROOT.as_posix())),
            encoding="utf-8",
        )
        (ws / "local_pkg").mkdir()
        (ws / "local_pkg/__init__.py").write_text("")
        (ws / "local_pkg/shape.py").write_text("""import json
from pathlib import Path
import bpy
def add_shape():
    dimensions = json.loads((Path(__file__).parents[1]/'resources'/'shape.json').read_text())
    bpy.ops.mesh.primitive_cube_add(size=1)
    obj = bpy.context.object
    obj.scale = (dimensions['width'], 0.5, 0.5)
    return obj
""")
        (ws / "lazy_helper.py").write_text("color = (1, 0, 0, 1)\n")
        (ws / "late_finalize.py").write_text(
            'def finish(obj):\n    assert obj.data.materials[0].name == "FrozenTexture"\n'
        )
        (ws / "resources").mkdir()
        (ws / "resources/shape.json").write_text(json.dumps({"width": 1.25}))
        (ws / "textures").mkdir()
        Image.new("RGB", (8, 8), "red").save(ws / "textures/skin.png")
        Image.new("RGB", (8, 8), "blue").save(ws / "reference.png")
        reference = (ws / "reference.png").read_bytes()
        (ws / "design.md").write_text("original design", encoding="utf-8")
        request = load_json(ws / "request.json")
        request.update(
            reference_image="reference.png",
            local_dependencies=[
                "local_pkg",
                "lazy_helper.py",
                "late_finalize.py",
                "resources",
                "textures",
            ],
        )
        write_json_atomic(ws / "request.json", request)

        def mutate_before_launch(process_request, **kwargs):
            if "inf_agent.execution.run_asset" in process_request.command:
                (ws / "resources/shape.json").write_text(json.dumps({"width": 2.5}))
                (ws / "lazy_helper.py").write_text(
                    'raise RuntimeError("changed live helper must not execute")\n'
                )
                Image.new("RGB", (8, 8), "blue").save(ws / "textures/skin.png")
                Image.new("RGB", (8, 8), "green").save(ws / "reference.png")
                (ws / "design.md").write_text("changed design")
            return run_process(process_request, **kwargs)

        with patch(
            "inf_agent.execution.service.run_process", side_effect=mutate_before_launch
        ):
            result = run_workspace(ws, export_glb=True, render=False)
        self.assertTrue(result["objective_success"], result)
        run = Path(result["run"])
        config = load_json(run / "input/config.json")
        self.assertTrue(
            Path(config["source_path"]).is_relative_to(run / "input/source")
        )
        self.assertEqual(
            Path(config["request"]["reference_image"]).read_bytes(), reference
        )
        self.assertEqual((run / "input/design.md").read_text(), "original design")
        self.assertEqual(
            load_json(run / "metadata.json")["asset"]["bbox"]["width"], 1.25
        )
        self.assertEqual(load_json(run / "artifact_reopen.json")["backend"], "blender")

    def test_undeclared_helper_does_not_silently_read_live_workspace(self):
        ws = self.workspace
        (ws / "helper.py").write_text("VALUE = 1\n")
        (ws / "asset.py").write_text(
            "import helper\n"
            + ASSET.replace("__EXPECTED_CWD__", repr(REPO_ROOT.as_posix())),
            encoding="utf-8",
        )
        result = run_workspace(ws, render=False)
        self.assertFalse(result["execution_success"])
        self.assertEqual(result["error"]["type"], "ModuleNotFoundError")
        self.assertIn("helper", result["error"]["message"])
