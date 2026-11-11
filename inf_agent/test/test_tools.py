"""Tests for repository maintenance tools and explicit installation configuration."""

from __future__ import annotations

import contextlib
import io
import json
import os
import runpy
import sys
from unittest.mock import patch
from pathlib import Path

from helpers import TemporaryWorkspaceTestCase

from inf_agent.cli import build_parser
from inf_agent.tools.index_generator import index_is_current, write_index
from inf_agent.tools.markdown_links import find_broken_markdown_links


class ToolTests(TemporaryWorkspaceTestCase):
    def test_written_index_is_current_ignoring_generation_timestamp(self) -> None:
        output = self.test_root / "indexes"
        api = {"generated_at_utc": "first", "symbols": [{"id": "fixture"}]}
        write_index(output, api)

        current, stale = index_is_current(
            output,
            {**api, "generated_at_utc": "second"},
        )
        self.assertTrue(current)
        self.assertEqual(stale, [])
        self.assertEqual([path.name for path in output.iterdir()], ["api_index.json"])

        path = output / "api_index.json"
        changed = json.loads(path.read_text(encoding="utf-8"))
        changed["symbols"].append({"id": "changed"})
        path.write_text(json.dumps(changed), encoding="utf-8")
        current, stale = index_is_current(output, api)
        self.assertFalse(current)
        self.assertEqual(stale, ["api_index.json"])

    def test_markdown_link_checker_reports_only_missing_local_targets(self) -> None:
        docs = self.test_root / "docs"
        docs.mkdir()
        (docs / "present.md").write_text("# Present\n", encoding="utf-8")
        (docs / "index.md").write_text(
            "[present](present.md)\n"
            "[missing](missing.md)\n"
            "[external](https://example.com/missing.md)\n"
            "```markdown\n[code sample](not-a-real-link.md)\n```\n",
            encoding="utf-8",
        )

        broken = find_broken_markdown_links(
            self.test_root,
            roots=(Path("docs"),),
        )

        self.assertEqual(len(broken), 1)
        self.assertEqual(broken[0].target, "missing.md")
        self.assertEqual(broken[0].line, 2)

    def test_cli_exposes_product_version(self) -> None:
        output = io.StringIO()
        with (
            contextlib.redirect_stdout(output),
            self.assertRaises(SystemExit) as raised,
        ):
            build_parser().parse_args(["--version"])

        self.assertEqual(raised.exception.code, 0)
        self.assertEqual(output.getvalue().strip(), "1.1")


class InstallationConfigurationTests(TemporaryWorkspaceTestCase):
    def environment(self, install_mode):
        names = {
            "INFINIGEN_MINIMAL_INSTALL", "INFINIGEN_INSTALL_TERRAIN",
            "INFINIGEN_INSTALL_CUSTOMGT", "INFINIGEN_INSTALL_BNURBS",
        }
        environment = {key: existing for key, existing in os.environ.items() if key not in names}
        if install_mode is not None:
            environment["INFINIGEN_MINIMAL_INSTALL"] = install_mode
        return environment

    def test_missing_or_invalid_install_mode_fails_before_installation(self):
        setup_path = Path(__file__).resolve().parents[2] / "setup.py"
        for value in (None, "", "true", "1"):
            with (
                self.subTest(value=value),
                patch.dict(os.environ, self.environment(value), clear=True),
                patch.object(sys, "argv", ["setup.py"]),
                patch("setuptools.setup") as install,
                patch("subprocess.run") as native,
                self.assertRaisesRegex(RuntimeError, "INFINIGEN_MINIMAL_INSTALL"),
            ):
                runpy.run_path(str(setup_path))
            install.assert_not_called()
            native.assert_not_called()

    def test_explicit_minimal_mode_installs_without_native_processes(self):
        setup_path = Path(__file__).resolve().parents[2] / "setup.py"
        with (
            patch.dict(os.environ, self.environment("True"), clear=True),
            patch.object(sys, "argv", ["setup.py"]),
            patch("setuptools.setup") as install,
            patch("subprocess.run") as native,
        ):
            runpy.run_path(str(setup_path))
        install.assert_called_once_with()
        native.assert_not_called()

    def test_nonminimal_mode_requires_explicit_native_flags_to_compile(self):
        setup_path = Path(__file__).resolve().parents[2] / "setup.py"
        with (
            patch.dict(os.environ, self.environment("False"), clear=True),
            patch.object(sys, "argv", ["setup.py"]),
            patch("setuptools.setup") as install,
            patch("subprocess.run") as native,
        ):
            runpy.run_path(str(setup_path))
        install.assert_called_once_with()
        native.assert_not_called()


if __name__ == "__main__":
    import unittest

    unittest.main()
