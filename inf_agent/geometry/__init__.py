"""Geometry authoring metadata and objective assembly validation."""

from inf_agent.geometry.assembly import AssemblyBuilder, LocalFrame, PartRegistry
from inf_agent.geometry.validation import evaluate_geometry_contract

__all__ = [
    "AssemblyBuilder",
    "LocalFrame",
    "PartRegistry",
    "evaluate_geometry_contract",
]
