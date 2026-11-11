"""Keep completed standalone bpy workers from crashing during GLTF teardown."""

import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from inf_agent.execution.run_asset import _exit


class ProcessExitTests(unittest.TestCase):
    def test_wheel_gltf_exit_flushes_streams_and_preserves_success_or_failure(self):
        for platform in ("win32", "linux"):
            for code in (0, 1, 2):
                with self.subTest(platform=platform, code=code):
                    modules = {
                        "bpy": SimpleNamespace(app=SimpleNamespace(binary_path="")),
                        "io_scene_gltf2": object(),
                    }
                    with (
                        patch.dict(sys.modules, modules),
                        patch.object(sys, "platform", platform),
                        patch.object(sys, "stdout") as stdout,
                        patch.object(sys, "stderr") as stderr,
                        patch(
                            "inf_agent.execution.run_asset.os._exit",
                            side_effect=SystemExit,
                        ) as process_exit,
                        self.assertRaises(SystemExit),
                    ):
                        _exit(code)
                    stdout.flush.assert_called_once_with()
                    stderr.flush.assert_called_once_with()
                    process_exit.assert_called_once_with(code)

    def test_worker_without_gltf_keeps_normal_shutdown(self):
        with (
            patch.dict(sys.modules),
            patch("inf_agent.execution.run_asset.os._exit") as process_exit,
        ):
            sys.modules.pop("io_scene_gltf2", None)
            sys.modules["bpy"] = SimpleNamespace(app=SimpleNamespace(binary_path=""))
            with self.assertRaises(SystemExit) as raised:
                _exit(2)
            self.assertEqual(raised.exception.code, 2)
            process_exit.assert_not_called()

    def test_desktop_blender_keeps_normal_shutdown(self):
        modules = {
            "bpy": SimpleNamespace(
                app=SimpleNamespace(binary_path="/opt/blender/blender")
            ),
            "io_scene_gltf2": object(),
        }
        with (
            patch.dict(sys.modules, modules),
            patch("inf_agent.execution.run_asset.os._exit") as process_exit,
        ):
            with self.assertRaises(SystemExit) as raised:
                _exit(1)
            self.assertEqual(raised.exception.code, 1)
            process_exit.assert_not_called()

    def test_unaffected_platform_keeps_normal_shutdown(self):
        modules = {
            "bpy": SimpleNamespace(app=SimpleNamespace(binary_path="")),
            "io_scene_gltf2": object(),
        }
        with (
            patch.dict(sys.modules, modules),
            patch.object(sys, "platform", "darwin"),
            patch("inf_agent.execution.run_asset.os._exit") as process_exit,
        ):
            with self.assertRaises(SystemExit) as raised:
                _exit(0)
            self.assertEqual(raised.exception.code, 0)
            process_exit.assert_not_called()
