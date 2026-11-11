"""Temporary filesystem fixtures shared by pure-Python tests."""

import tempfile
import unittest
from pathlib import Path


class TemporaryWorkspaceTestCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="inf_agent_test_")
        self.addCleanup(self.temporary.cleanup)
        self.test_root = Path(self.temporary.name)
        self.repo_root = self.test_root / "repository"
        self.repo_root.mkdir()
