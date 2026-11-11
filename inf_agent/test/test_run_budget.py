"""Workspace execution allowance counts actual allocations, including failures."""

import concurrent.futures
import contextlib
import io
import json
from unittest.mock import patch

from test_core_workflow import TemporaryCase, fake_run
from inf_agent.cli import main
from inf_agent.execution.resource_policy import ResourceLimitError, ResourcePolicy
from inf_agent.execution.service import run_workspace, validate_run
from inf_agent.workspace.manager import allocate_run, workspace_status


class RunBudgetTests(TemporaryCase):
    def test_twenty_runs_are_allowed_and_next_allocation_preserves_evidence(self):
        self.start()
        paths = [allocate_run(self.workspace) for _ in range(20)]
        (paths[0] / "failure.txt").write_text("keep")
        with self.assertRaisesRegex(ResourceLimitError, "20"):
            allocate_run(self.workspace)
        self.assertEqual(len(list((self.workspace / "runs").iterdir())), 20)
        self.assertEqual((paths[0] / "failure.txt").read_text(), "keep")
        status = workspace_status(self.workspace)
        self.assertEqual(status["run_budget"]["remaining_at_default"], 0)
        allocate_run(self.workspace, max_runs=21)

    def test_exhausted_budget_returns_json_before_starting_process(self):
        self.start()
        for _ in range(20):
            allocate_run(self.workspace)
        with patch("inf_agent.execution.service.run_process") as process:
            with self.assertRaises(ResourceLimitError):
                run_workspace(self.workspace, render=False)
            process.assert_not_called()
        error = io.StringIO()
        with (
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(error),
        ):
            code = main(["preview", "--workspace", str(self.workspace)])
        self.assertEqual(code, 2)
        self.assertIn("run limit", json.loads(error.getvalue())["error"])
        self.assertEqual(len(list((self.workspace / "runs").iterdir())), 20)

    def test_budget_and_texture_settings_reject_invalid_inputs(self):
        from inf_agent.execution.material_export import MaterialExportSettings
        from inf_agent.workspace.contracts import ContractError

        for value in [0, -1, True, 2.5, "20"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                ResourcePolicy(max_runs=value)
        for kwargs in [
            {"texture_resolution": 0},
            {"texture_resolution": 8192},
            {"bake_samples": True},
            {"bake_samples": 0},
        ]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ContractError):
                MaterialExportSettings(**kwargs)

    def test_concurrent_allocations_do_not_leave_runs_over_the_limit(self):
        self.start()

        def attempt(_):
            try:
                return allocate_run(self.workspace, max_runs=6)
            except ResourceLimitError:
                return None

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            allocated = [
                path for path in pool.map(attempt, range(24)) if path is not None
            ]
        self.assertLessEqual(len(allocated), 6)
        self.assertEqual(len(list((self.workspace / "runs").iterdir())), len(allocated))

    def test_cli_explicit_larger_limit_and_validation_at_limit(self):
        self.start()
        for _ in range(20):
            allocate_run(self.workspace)
        limits = self.root / "limits.json"
        limits.write_text(json.dumps({"max_runs": 21}))
        output = io.StringIO()
        with (
            patch("inf_agent.execution.service.run_process", side_effect=fake_run),
            contextlib.redirect_stdout(output),
        ):
            code = main(
                [
                    "preview",
                    "--workspace",
                    str(self.workspace),
                    "--no-render",
                    "--limits",
                    str(limits),
                ]
            )
        self.assertEqual(code, 0)
        run = json.loads(output.getvalue())["run"]
        with patch("inf_agent.execution.service.run_process", side_effect=fake_run):
            self.assertTrue(validate_run(run)["objective_success"])
        self.assertEqual(workspace_status(self.workspace)["run_count"], 21)
