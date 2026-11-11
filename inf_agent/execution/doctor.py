"""Host readiness gate for the local Blender asset pipeline."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from inf_agent.execution.process import ProcessError, ProcessRequest, run_process


class HostDoctorError(RuntimeError):
    """Raised before workspace creation when the host is not ready."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def host_doctor_report(
    repo_root: Path | str,
    *,
    timeout_seconds: int = 5 * 60,
) -> dict[str, Any]:
    """Run a Blender build/save/export/reopen probe without a formal workspace."""

    repository = Path(repo_root).resolve()
    checks: dict[str, bool] = {
        "repository_exists": repository.is_dir(),
        "infinigen_package": (repository / "infinigen" / "__init__.py").is_file(),
        "agent_package": (repository / "inf_agent" / "cli.py").is_file(),
    }
    report: dict[str, Any] = {
        "schema_version": "1.1",
        "status": "ENVIRONMENT_ERROR",
        "checked_at_utc": _utc_now(),
        "python_executable": sys.executable,
        "checks": checks,
        "probe": None,
        "error": None,
    }
    if not all(checks.values()):
        report["error"] = "repository does not contain the required packages"
        return report
    try:
        with tempfile.TemporaryDirectory(prefix="inf_agent_doctor_") as temporary:
            root = Path(temporary)
            output = root / "staging"
            output.mkdir()
            process_log = root / "doctor_process.log"
            command = (
                sys.executable,
                "-B",
                "-m",
                "inf_agent.execution.doctor_probe",
                "--output",
                str(output),
            )
            with process_log.open("w", encoding="utf-8", newline="\n") as stream:
                completed = run_process(
                    ProcessRequest(
                        command=command,
                        cwd=repository,
                        writable_dir=output,
                        timeout_seconds=timeout_seconds,
                    ),
                    stdout=stream,
                    stderr=subprocess.STDOUT,
                )
            probe_path = output / "doctor_probe.json"
            if not probe_path.is_file():
                raise HostDoctorError(
                    "Blender probe returned no report "
                    f"(exit_code={completed.returncode})"
                )
            probe = json.loads(probe_path.read_text(encoding="utf-8"))
            report["probe"] = probe
            checks["minimal_blender_round_trip"] = (
                completed.returncode == 0 and probe.get("success") is True
            )
            if not checks["minimal_blender_round_trip"]:
                report["error"] = str(
                    probe.get("error") or "minimal Blender probe failed"
                )
                return report
    except (OSError, UnicodeError, json.JSONDecodeError, ProcessError, HostDoctorError) as error:
        report["error"] = f"{type(error).__name__}: {error}"
        return report
    report["status"] = "READY"
    report["error"] = None
    return report


def require_host_ready(
    repo_root: Path | str,
) -> dict[str, Any]:
    report = host_doctor_report(repo_root)
    if report["status"] != "READY":
        raise HostDoctorError(str(report.get("error") or "host doctor failed"))
    return report


__all__ = ["HostDoctorError", "host_doctor_report", "require_host_ready"]
