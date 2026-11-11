"""Development-only CLI entry point for generating the agent API index.

Run with ``python -m inf_agent.tools.generate_indexes``.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from inf_agent.tools.index_generator import (  # noqa: E402 - direct script bootstrap
    main,
)

if __name__ == "__main__":
    raise SystemExit(main())
