"""Run the asset pipeline with the Python interpreter that launched the CLI.

This is local execution, not a security boundary. Agent-authored code has the
same filesystem and network permissions as the current user.
"""

from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import IO

from inf_agent.execution.resource_policy import (
    DEFAULT_RESOURCE_POLICY,
    ResourcePolicy,
    directory_bytes,
)


class ProcessError(RuntimeError):
    """A local process could not start or exceeded an operational budget."""


@dataclass(frozen=True)
class ProcessRequest:
    command: tuple[str, ...]
    cwd: Path
    writable_dir: Path
    build_marker: Path | None = None
    timeout_seconds: int | None = None
    resource_policy: ResourcePolicy = DEFAULT_RESOURCE_POLICY


def run_process(
    request: ProcessRequest,
    *,
    stdout: IO[str] | int | None = None,
    stderr: IO[str] | int | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run locally while retaining wall-time, build-time, and output budgets."""

    if not request.command or not all(isinstance(arg, str) and arg for arg in request.command):
        raise ProcessError("process command must be a non-empty string sequence")
    cwd = request.cwd.resolve()
    writable = request.writable_dir.resolve()
    if not cwd.is_dir() or not writable.is_dir():
        raise ProcessError("process cwd and writable directory must exist")
    marker = request.build_marker.resolve() if request.build_marker else None
    if marker is not None and not marker.is_relative_to(writable):
        raise ProcessError("build marker must be inside the output directory")
    timeout = request.timeout_seconds or request.resource_policy.max_wall_seconds
    try:
        process = subprocess.Popen(
            request.command,
            cwd=cwd,
            stdout=stdout,
            stderr=stderr,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
    except OSError as error:
        raise ProcessError(f"cannot launch local process: {error}") from error
    deadline = time.monotonic() + timeout
    try:
        while process.poll() is None:
            failure: str | None = None
            if time.monotonic() >= deadline:
                failure = f"process wall timeout after {timeout} seconds"
            else:
                try:
                    artifact_bytes = directory_bytes(writable)
                except OSError as error:
                    failure = f"process output monitor failed: {error}"
                else:
                    if artifact_bytes > request.resource_policy.max_artifact_bytes:
                        failure = "process output exceeded the disk budget"
            if failure is None and marker is not None and marker.is_file():
                try:
                    build_elapsed = time.time() - marker.stat().st_mtime
                except OSError:
                    build_elapsed = 0.0
                if build_elapsed > request.resource_policy.max_build_seconds:
                    failure = (
                        "asset build exceeded the "
                        f"{request.resource_policy.max_build_seconds:g} second budget"
                    )
            if failure is not None:
                raise ProcessError(failure)
            time.sleep(0.1)
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    return subprocess.CompletedProcess(request.command, process.returncode)
