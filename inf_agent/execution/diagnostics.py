"""Prioritize real geometry/visual failures without restricting repair iterations."""

from typing import Any

PRIORITY = (
    "environment",
    "process",
    "artifacts",
    "identity_silhouette",
    "required_features",
    "assembly",
    "proportion",
    "material_semantics",
    "surface_quality",
    "multi_view_consistency",
    "construction",
)


def objective_failure_domains(report: dict[str, Any]) -> list[str]:
    """Classify actionable preview failures without mislabeling color as code failure."""

    layers = report.get("layers", {})
    objective = layers.get("objective_asset_health", {})
    geometry = layers.get("geometry_and_assembly", {})
    domains: set[str] = set()
    if layers.get("execution_health", {}).get("passed") is False:
        kind = layers.get("execution_health", {}).get("error_type")
        domains.add(
            "environment"
            if kind in {"ModuleNotFoundError", "ImportError"}
            else "process"
            if kind in {"ProcessError", "ExecutionReportError"}
            else "construction"
        )
    else:
        if layers.get("artifact_validation", {}).get("success") is False:
            domains.add("artifacts")
        if any(
            not item.get("passed", True) for item in geometry.get("negative_spaces", [])
        ):
            domains.add("required_features")
        if objective.get("focus_plan", {}).get("passed") is False:
            domains.add("required_features")
        if geometry.get("passed") is False:
            domains.add("assembly")
        if objective.get("asset_spec_proportions", {}).get("passed") is False or any(
            item.get("passed") is False
            for item in objective.get("explicit_dimensions", {}).values()
        ):
            domains.add("proportion")
        if (
            objective.get("materials", {}).get("passed") is False
            or objective.get("chromatic_render", {}).get("passed") is False
        ):
            domains.add("material_semantics")
        if objective.get("topology", {}).get("passed") is False:
            domains.add("surface_quality")
    ranked = [domain for domain in PRIORITY if domain in domains]
    if ranked:
        return ranked
    if report.get("success") is True:
        return []
    return ["construction"]
