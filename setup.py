# Copyright (C) 2023, Princeton University.
# This source code is licensed under the BSD 3-Clause license found in the LICENSE file in the root directory
# of this source tree.

# Authors: Alexander Raistrick

# Acknowledgement: This file draws inspiration from https://github.com/pytorch/pytorch/blob/main/setup.py

import os
import subprocess
import sys
from pathlib import Path

from setuptools import setup

cwd = Path(__file__).resolve().parent

minimal_setting = os.environ.get("INFINIGEN_MINIMAL_INSTALL")
if minimal_setting not in {"True", "False"}:
    raise RuntimeError(
        "Set INFINIGEN_MINIMAL_INSTALL explicitly to 'True' or 'False' before installation."
    )
MINIMAL_INSTALL = minimal_setting == "True"
BUILD_TERRAIN = os.environ.get("INFINIGEN_INSTALL_TERRAIN", "False") == "True"
BUILD_OPENGL = os.environ.get("INFINIGEN_INSTALL_CUSTOMGT", "False") == "True"
BUILD_BNURBS = os.environ.get("INFINIGEN_INSTALL_BNURBS", "False") == "True"

if MINIMAL_INSTALL and any((BUILD_TERRAIN, BUILD_OPENGL, BUILD_BNURBS)):
    raise RuntimeError("native extensions require INFINIGEN_MINIMAL_INSTALL=False")

if not any((BUILD_TERRAIN, BUILD_OPENGL, BUILD_BNURBS)):
    # Metadata, editable installs and wheels all use the same minimal path.
    setup()
else:
    from setuptools import Distribution, Extension
    from setuptools.command.build_ext import build_ext
    from setuptools.command.build_py import build_py

    def build_native(distribution):
        """Build once per command invocation, never during metadata generation."""
        if getattr(distribution, "_infinigen_native_built", False):
            return
        targets = []
        if BUILD_TERRAIN:
            targets.append("terrain")
        if BUILD_OPENGL:
            targets.append("customgt")
        if targets:
            # Check all requested dependencies before starting any compilation.
            subprocess.run(
                [sys.executable, "scripts/install/check_native_dependencies.py", *targets],
                cwd=cwd,
                check=True,
            )
            env = os.environ.copy()
            # Native scripts use the current build interpreter.
            env["PYTHON"] = sys.executable
            scripts = {"terrain": "compile_terrain.sh", "customgt": "compile_opengl.sh"}
            for target in targets:
                subprocess.run(
                    ["bash", str(cwd / "scripts/install" / scripts[target])],
                    cwd=cwd,
                    env=env,
                    check=True,
                )
        distribution._infinigen_native_built = True

    class NativeDistribution(Distribution):
        def has_ext_modules(self):
            # custom GT is a platform binary even when no Cython modules are built.
            return True

    class NativeBuildPy(build_py):
        def run(self):
            # Generate native package-data before setuptools collects/copies it.
            build_native(self.distribution)
            super().run()

    class NativeBuildExt(build_ext):
        def run(self):
            build_native(self.distribution)
            if self.extensions:
                import numpy
                from Cython.Build import cythonize

                for extension in self.extensions:
                    extension.include_dirs.append(numpy.get_include())
                compiled = {ext.name: ext for ext in cythonize(self.extensions)}
                # Preserve the instances already finalized by setuptools, including
                # their output mapping and editable-copy attributes.
                for extension in self.extensions:
                    extension.__dict__.update(compiled[extension.name].__dict__)
            super().run()

    extensions = []
    if BUILD_BNURBS:
        extensions.append(
            Extension(
                name="bnurbs",
                sources=["infinigen/assets/utils/geometry/cpp_utils/bnurbs.pyx"],
            )
        )
    if BUILD_TERRAIN:
        extensions.append(
            Extension(
                name="infinigen.terrain.marching_cubes",
                sources=[
                    "infinigen/terrain/marching_cubes/_marching_cubes_lewiner_cy.pyx"
                ],
            )
        )

    setup(
        distclass=NativeDistribution,
        cmdclass={"build_py": NativeBuildPy, "build_ext": NativeBuildExt},
        ext_modules=extensions,
        # Other options come from pyproject.toml.
    )
