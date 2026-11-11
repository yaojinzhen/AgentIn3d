"""Execute the maintained Skill path and documentation examples in real Blender."""

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(
    os.environ.get("INF_AGENT_BLENDER_TESTS") == "1",
    "set INF_AGENT_BLENDER_TESTS=1 for actual Blender",
)
class SkillWorkflowTests(unittest.TestCase):
    def cli(self, *args, expected=0):
        completed = subprocess.run(
            [sys.executable, "-B", "-m", "inf_agent.cli", *map(str, args)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=180,
        )
        self.assertEqual(
            completed.returncode, expected, completed.stdout + completed.stderr
        )
        return json.loads(completed.stdout)

    def test_query_read_preview_diagnose_repair_export(self):
        with tempfile.TemporaryDirectory(prefix="inf_agent_skill_e2e_") as folder:
            workspace = Path(folder) / "box"
            query = self.cli("query", "api", "--query", "from_pydata")
            match = query["matches"][0]
            self.assertEqual(match["match_type"], "alias")
            document = self.cli("read", "--document", match["document_path"])["content"]
            section = document.split("### `bpy.types.Mesh.from_pydata`", 1)[1]
            source = re.search(r"```python\n(.*?)```", section, re.S)[1]
            self.assertIn("class MeshBoxFactory", source)
            self.cli(
                "start",
                "--workspace",
                workspace,
                "--prompt",
                "a blue mesh box",
                "--width",
                "1",
                "--depth",
                "1",
                "--height",
                "1",
            )
            asset = workspace / "asset.py"
            asset.write_text(
                source.replace("width = 1.0", "width = 0.5"), encoding="utf-8"
            )
            self.cli("lint", "--source", asset)
            failed = self.cli(
                "preview",
                "--workspace",
                workspace,
                "--resolution",
                "64x64",
                "--samples",
                "1",
                expected=1,
            )
            self.assertTrue(failed["execution_success"], failed)
            self.assertFalse(failed["objective_success"])

            # Execute the diagnostic example exactly as a user saving the code block would.
            output_doc = (ROOT / "inf_agent/docs/OUTPUT_FORMAT.md").read_text(
                encoding="utf-8"
            )
            snippet = re.search(r"```python\n(.*?)```", output_doc, re.S)[1]
            script = Path(folder) / "read_diagnostics.py"
            script.write_text(snippet, encoding="utf-8")

            def diagnostics(run):
                output = subprocess.check_output(
                    [sys.executable, "-B", str(script), run],
                    text=True,
                    encoding="utf-8",
                )
                return json.loads(output)

            report = diagnostics(failed["run"])
            width = report["dimensions"]["width"]
            self.assertFalse(width["passed"])
            self.assertAlmostEqual(width["observed_m"], 0.5)
            self.assertTrue(report["files_usable"])
            self.assertEqual(report["visual_status"], "NOT_CHECKED")
            dimension_error = next(
                error for error in failed["errors"] if "15% tolerance" in error
            )
            route = self.cli("query", "troubleshoot", "--query", dimension_error)[
                "matches"
            ][0]
            self.assertEqual(route["id"], "troubleshoot-geometry")
            self.assertIn(
                "explicit_dimensions",
                self.cli("read", "--document", route["document_path"])["content"],
            )
            asset.write_text(source, encoding="utf-8")
            repaired = self.cli(
                "preview",
                "--workspace",
                workspace,
                "--resolution",
                "64x64",
                "--samples",
                "1",
            )
            self.assertTrue(
                diagnostics(repaired["run"])["dimensions"]["width"]["passed"]
            )
            exported = self.cli(
                "export",
                "--workspace",
                workspace,
                "--resolution",
                "64x64",
                "--samples",
                "1",
            )
            self.assertTrue(exported["objective_success"], exported)
            self.assertTrue(Path(exported["artifacts"]["glb"]).is_file())
            checked = self.cli("validate", "--run", exported["run"])
            self.assertTrue(checked["objective_success"], checked)
            status = self.cli("status", "--workspace", workspace)
            self.assertEqual(status["latest_result"]["run"], exported["run"])
            self.assertTrue(diagnostics(exported["run"])["assembly_passed"])
            # Snapshot evidence remains the failed half-width version after live-source repair.
            self.assertIn(
                "width = 0.5",
                (Path(failed["run"]) / "input/source/asset.py").read_text(),
            )
