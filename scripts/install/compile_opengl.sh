#!/bin/bash

set -e

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON="${PYTHON:-python}"
"${PYTHON}" "${repo_root}/scripts/install/check_native_dependencies.py" customgt
cd "${repo_root}/infinigen/datagen/customgt"

cmake -S . -Bbuild -DCMAKE_BUILD_TYPE=Release
cmake --build build --target all
if ./build/customgt -in x -dst_in x -out x --frame 0 --dst_frame 0; then
	echo "OpenGL/EGL ground truth is working."
else
	echo "WARNING: OpenGL/EGL is not supported on this machine. If you are running from a cluster head-node, this is likely not an issue."
fi
