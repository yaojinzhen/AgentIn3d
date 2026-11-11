"""Scoped imports from the current asset snapshot; the process cwd is unchanged."""

from contextlib import contextmanager
from pathlib import Path
import sys


@contextmanager
def asset_source_context(root):
    root = Path(root).resolve()
    path = str(root)
    before = set(sys.modules)
    sys.path.insert(0, path)
    try:
        yield
    finally:
        if path in sys.path:
            sys.path.remove(path)
        # In-process callers must not reuse a previous run's ordinary helper imports.
        for name in set(sys.modules) - before:
            module = sys.modules.get(name)
            filename = getattr(module, "__file__", None)
            if isinstance(filename, str) and Path(filename).resolve().is_relative_to(
                root
            ):
                sys.modules.pop(name, None)
