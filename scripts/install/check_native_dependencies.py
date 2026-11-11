"""Check only the submodules needed by the requested native build targets.

This check is offline and validates the bundled native source directories.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CUSTOMGT = "infinigen/datagen/customgt/dependencies"
SUBMODULE_MARKERS = {
    "infinigen/OcMesher": ("install.sh", "ocmesher/source/core.cpp"),
    f"{CUSTOMGT}/glm": ("glm/glm.hpp",),
    f"{CUSTOMGT}/eigen": ("Eigen/Core",),
    f"{CUSTOMGT}/argparse": ("include/argparse/argparse.hpp",),
    f"{CUSTOMGT}/cnpy": ("CMakeLists.txt", "cnpy.h"),
    f"{CUSTOMGT}/json": ("single_include/nlohmann/json.hpp",),
    f"{CUSTOMGT}/stb": ("stb_image.h",),
    f"{CUSTOMGT}/glfw": ("CMakeLists.txt", "include/GLFW/glfw3.h"),
}


def required_submodules(targets, platform=None):
    platform = sys.platform if platform is None else platform
    required = set()
    if "terrain" in targets:
        required.update(("infinigen/OcMesher", f"{CUSTOMGT}/glm"))
    if "customgt" in targets:
        required.update(
            f"{CUSTOMGT}/{name}"
            for name in ("eigen", "argparse", "cnpy", "glm", "json", "stb")
        )
        if platform == "darwin":
            required.add(f"{CUSTOMGT}/glfw")
    return sorted(required)


def check_submodules(targets, root=ROOT, platform=None):
    missing = [
        module
        for module in required_submodules(targets, platform)
        if not all((root / module / marker).is_file() for marker in SUBMODULE_MARKERS[module])
    ]
    if missing:
        raise RuntimeError(
            "Missing native source files in: "
            + ", ".join(missing)
            + ". Restore the required source directories before building."
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("targets", nargs="+", choices=("terrain", "customgt"))
    args = parser.parse_args()
    try:
        check_submodules(args.targets)
    except RuntimeError as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
