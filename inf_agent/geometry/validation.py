"""Pure-Python hard gate for semantic geometry and assembly evidence."""

from __future__ import annotations

import math
from collections import Counter, defaultdict, deque
from typing import Any


def _number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        converted = float(value)
        if math.isfinite(converted):
            return converted
    return None


def _instance_pair(
    record: dict[str, Any], *, attachment: bool = False
) -> tuple[str, str] | None:
    keys = (
        ("child_registration_id", "parent_registration_id")
        if attachment
        else ("left_registration_id", "right_registration_id")
    )
    left, right = (record.get(key) for key in keys)
    if not isinstance(left, str) or not isinstance(right, str) or left == right:
        return None
    return tuple(sorted((left, right)))


def _fallback_checks(metrics: dict[str, Any]) -> tuple[list[str], list[dict[str, Any]]]:
    """Reject explicit bad evidence even outside a workspace-bound evaluation."""

    errors: list[str] = []
    attachments = metrics.get("semantic_attachments", [])
    if isinstance(attachments, list):
        for item in attachments:
            if isinstance(item, dict) and item.get("passed") is False:
                identity = item.get("attachment_id", "unknown")
                errors.append(f"semantic attachment {identity} failed")
    return errors, attachments if isinstance(attachments, list) else []


def _exemption_maps(
    asset_spec: dict[str, Any],
    part_manifest: dict[str, Any],
    errors: list[str],
) -> tuple[set[tuple[str, str]], dict[str, set[str]]]:
    spec_exemptions: set[tuple[str, str]] = set()
    for item in asset_spec.get("geometry_exemptions", []):
        if not isinstance(item, dict):
            errors.append("geometry exemption record is invalid")
            continue
        kind, target = item.get("kind"), item.get("target_id")
        if kind not in {"non_contact", "penetration", "multi_island"} or not isinstance(
            target, str
        ):
            errors.append("geometry exemption kind or target is invalid")
            continue
        spec_exemptions.add((kind, target))

    manifest_exemptions: dict[str, set[str]] = {}
    allowed_targets = {
        f"non_contact:{item['attachment_id']}"
        for item in asset_spec.get("attachment_constraints", [])
        if isinstance(item, dict) and isinstance(item.get("attachment_id"), str)
    }
    allowed_targets.update(
        f"penetration:{item['attachment_id']}"
        for item in asset_spec.get("attachment_constraints", [])
        if isinstance(item, dict) and isinstance(item.get("attachment_id"), str)
    )
    allowed_targets.update(
        f"multi_island:{item['part_id']}"
        for item in asset_spec.get("required_parts", [])
        if isinstance(item, dict) and isinstance(item.get("part_id"), str)
    )
    for part in part_manifest.get("parts", []):
        if not isinstance(part, dict) or not isinstance(part.get("part_id"), str):
            continue
        values = (
            set(part.get("exemptions", []))
            if isinstance(part.get("exemptions"), list)
            else set()
        )
        unknown = {value for value in values if value not in allowed_targets}
        if unknown:
            errors.append(
                f"part {part['part_id']} has unsupported geometry exemptions: "
                + ", ".join(sorted(map(str, unknown)))
            )
        manifest_exemptions[part["part_id"]] = {str(value) for value in values}
    return spec_exemptions, manifest_exemptions


def _has_exemption(
    kind: str,
    target: str,
    part_id: str,
    spec_exemptions: set[tuple[str, str]],
    manifest_exemptions: dict[str, set[str]],
) -> bool:
    return (
        kind,
        target,
    ) in spec_exemptions and f"{kind}:{target}" in manifest_exemptions.get(
        part_id, set()
    )


def _connected_with_spaced_constraints(
    component_ids: set[int],
    spaced_edges: list[tuple[int, int]],
) -> bool:
    if len(component_ids) <= 1:
        return True
    adjacency: dict[int, set[int]] = defaultdict(set)
    for left, right in spaced_edges:
        adjacency[left].add(right)
        adjacency[right].add(left)
    seen = {next(iter(component_ids))}
    pending = deque(seen)
    while pending:
        current = pending.popleft()
        for neighbor in adjacency[current]:
            if neighbor not in seen:
                seen.add(neighbor)
                pending.append(neighbor)
    return component_ids <= seen


def evaluate_geometry_contract(
    *,
    asset_spec: dict[str, Any] | None,
    part_manifest: dict[str, Any] | None,
    metrics: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate registered geometry against the optional declared design.

    When contracts are absent, this function still rejects explicit failed
    island or attachment evidence for diagnostic callers.  Callers without declared parts use general geometry diagnostics.
    """

    fallback_errors, fallback_attachments = _fallback_checks(metrics)
    warnings: list[str] = []
    strict = isinstance(asset_spec, dict) and isinstance(part_manifest, dict)
    errors = [] if strict else fallback_errors
    report: dict[str, Any] = {
        "strict": strict,
        "registry": None,
        "required_parts": [],
        "islands": [],
        "attachments": fallback_attachments,
        "negative_spaces": [],
        "connectivity": None,
        "penetrations": [],
        "material_regions": [],
    }
    if not strict:
        report.update(
            {
                "passed": not errors,
                "errors": list(dict.fromkeys(errors)),
                "warnings": warnings,
            }
        )
        return report

    assert asset_spec is not None and part_manifest is not None
    registry = metrics.get("part_registry")
    islands = metrics.get("evaluated_mesh_islands")
    structural = metrics.get("structural")
    negative_spaces = metrics.get("negative_spaces")
    report["registry"] = registry
    report["islands"] = islands if isinstance(islands, list) else []
    report["connectivity"] = structural
    report["negative_spaces"] = (
        negative_spaces if isinstance(negative_spaces, list) else []
    )
    if not isinstance(registry, dict) or registry.get("available") is not True:
        errors.append(
            "part registry is missing; every preview asset must finalize PartRegistry"
        )
        registrations: list[dict[str, Any]] = []
        registry_attachments: list[dict[str, Any]] = []
    else:
        if registry.get("valid") is not True:
            errors.extend(
                str(item)
                for item in registry.get("errors", ["part registry is invalid"])
            )
        registrations = registry.get("registrations", [])
        registry_attachments = registry.get("attachments", [])
        if not isinstance(registrations, list):
            registrations = []
            errors.append("part registry registrations are unavailable")
        if not isinstance(registry_attachments, list):
            registry_attachments = []
            errors.append("part registry attachments are unavailable")
    if not isinstance(islands, list) or not islands:
        islands = []
        errors.append("evaluated mesh island evidence is unavailable")
    if not isinstance(structural, dict) or not isinstance(
        structural.get("contacts"), list
    ):
        structural = {}
        errors.append("evaluated island contact graph is unavailable")
    if not isinstance(negative_spaces, list):
        negative_spaces = []

    required = {
        item["part_id"]: item
        for item in asset_spec.get("required_parts", [])
        if isinstance(item, dict) and isinstance(item.get("part_id"), str)
    }
    manifest_parts = {
        item["part_id"]: item
        for item in part_manifest.get("parts", [])
        if isinstance(item, dict) and isinstance(item.get("part_id"), str)
    }
    spec_exemptions, manifest_exemptions = _exemption_maps(
        asset_spec, part_manifest, errors
    )

    counts = Counter(
        item.get("part_id") for item in registrations if isinstance(item, dict)
    )
    for part_id, requirement in required.items():
        count = counts[part_id]
        minimum = int(requirement.get("minimum_count", 0))
        maximum = int(requirement.get("maximum_count", minimum))
        passed = minimum <= count <= maximum
        report["required_parts"].append(
            {
                "part_id": part_id,
                "observed_count": count,
                "minimum_count": minimum,
                "maximum_count": maximum,
                "passed": passed,
            }
        )
        if not passed:
            errors.append(
                f"required part {part_id} count {count} is outside [{minimum}, {maximum}]"
            )
    unknown_parts = sorted({str(item) for item in counts if item not in required})
    if unknown_parts:
        errors.append(
            "part registry contains undeclared parts: " + ", ".join(unknown_parts)
        )

    registration_by_id = {
        item.get("registration_id"): item
        for item in registrations
        if isinstance(item, dict) and isinstance(item.get("registration_id"), str)
    }
    registration_by_index = {
        item.get("registration_index"): item
        for item in registrations
        if isinstance(item, dict) and isinstance(item.get("registration_index"), int)
    }
    island_by_registration: dict[str, list[dict[str, Any]]] = defaultdict(list)
    registration_components: dict[str, set[int]] = defaultdict(set)
    for island in islands:
        if not isinstance(island, dict):
            errors.append("evaluated mesh island record is invalid")
            continue
        indices = island.get("registration_indices")
        if not isinstance(indices, list) or len(indices) != 1:
            errors.append(
                f"evaluated mesh island {island.get('island_id', 'unknown')} does not have exactly one part identity"
            )
            continue
        registration = registration_by_index.get(indices[0])
        if registration is None:
            errors.append(
                f"evaluated mesh island {island.get('island_id', 'unknown')} is unregistered"
            )
            continue
        registration_id = registration["registration_id"]
        if island.get("part_id") not in {None, registration.get("part_id")}:
            errors.append(
                f"evaluated mesh island {island.get('island_id')} has conflicting part identity"
            )
        island_by_registration[registration_id].append(island)
        component = island.get("contact_component")
        if isinstance(component, int):
            registration_components[registration_id].add(component)

    for registration_id, registration in registration_by_id.items():
        owned = island_by_registration.get(registration_id, [])
        part_id = registration.get("part_id")
        if not owned:
            errors.append(
                f"registered part instance {registration_id} has no evaluated mesh island"
            )
        elif len(owned) > 1 and not _has_exemption(
            "multi_island",
            str(part_id),
            str(part_id),
            spec_exemptions,
            manifest_exemptions,
        ):
            errors.append(
                f"registered part instance {registration_id} contains {len(owned)} disconnected mesh islands"
            )
        manifest = manifest_parts.get(str(part_id))
        if manifest is None:
            errors.append(f"registered part {part_id} is absent from part manifest")
        elif registration.get("parent_part_id") != manifest.get("parent_part_id"):
            errors.append(f"registered part {part_id} has the wrong parent_part_id")

    contacts = structural.get("contacts", []) if isinstance(structural, dict) else []
    attachment_specs = {
        item["attachment_id"]: item
        for item in asset_spec.get("attachment_constraints", [])
        if isinstance(item, dict) and isinstance(item.get("attachment_id"), str)
    }
    registry_attachment_map = {
        item.get("attachment_id"): item
        for item in registry_attachments
        if isinstance(item, dict) and isinstance(item.get("attachment_id"), str)
    }
    anchor_owner = {
        item.get("anchor_id"): item.get("registration_id")
        for item in (registry.get("anchors", []) if isinstance(registry, dict) else [])
        if isinstance(item, dict)
    }
    spaced_component_edges: list[tuple[int, int]] = []
    semantic_attachments: list[dict[str, Any]] = []
    for attachment_id, expected in attachment_specs.items():
        declared = registry_attachment_map.get(attachment_id)
        part_id = expected.get("part_id")
        parent_part_id = expected.get("parent_part_id")
        kind = expected.get("kind")
        attachment_errors: list[str] = []
        if declared is None:
            attachment_errors.append("not declared in PartRegistry")
            gap = None
            touching = False
        else:
            for field in ("part_id", "parent_part_id", "kind"):
                if declared.get(field) != expected.get(field):
                    attachment_errors.append(
                        f"registry {field} does not match AssetSpec"
                    )
            child_id = declared.get("child_registration_id")
            parent_id = declared.get("parent_registration_id")
            child = registration_by_id.get(child_id)
            parent = registration_by_id.get(parent_id)
            if child is None or child.get("part_id") != part_id:
                attachment_errors.append(
                    "child registration does not belong to the expected part"
                )
            if parent is None or parent.get("part_id") != parent_part_id:
                attachment_errors.append(
                    "parent registration does not belong to the expected part"
                )
            if child is not None and child.get("parent_part_id") != parent_part_id:
                attachment_errors.append("child registration has the wrong parent part")
            if expected.get("require_anchors"):
                for side, owner_id in (("child", child_id), ("parent", parent_id)):
                    anchor_id = declared.get(f"{side}_anchor_id")
                    if (
                        not isinstance(anchor_id, str)
                        or anchor_owner.get(anchor_id) != owner_id
                    ):
                        attachment_errors.append(
                            f"lacks a valid {side} anchor owned by its instance"
                        )
            pair = _instance_pair(declared, attachment=True)
            if pair is None:
                attachment_errors.append(
                    "attachment requires two distinct registered instances"
                )
            relevant = [
                item
                for item in contacts
                if isinstance(item, dict)
                and pair is not None
                and _instance_pair(item) == pair
                and {item.get("left_part_id"), item.get("right_part_id")}
                == {part_id, parent_part_id}
            ]
            distances = [
                value
                for value in (
                    _number(item.get("surface_distance_m")) for item in relevant
                )
                if value is not None
            ]
            gap = min(distances, default=None)
            touching = any(item.get("within_tolerance") is True for item in relevant)
            if kind == "spaced":
                has_exemption = _has_exemption(
                    "non_contact",
                    attachment_id,
                    str(part_id),
                    spec_exemptions,
                    manifest_exemptions,
                )
                minimum = _number(expected.get("minimum_gap_m"))
                maximum = _number(expected.get("maximum_gap_m"))
                for field in ("minimum_gap_m", "maximum_gap_m"):
                    if _number(declared.get(field)) != _number(expected.get(field)):
                        attachment_errors.append(
                            f"registry {field} does not match AssetSpec"
                        )
                if not has_exemption:
                    attachment_errors.append(
                        "spaced attachment lacks matching AssetSpec and part exemption"
                    )
                if minimum is None or maximum is None or not 0 <= minimum <= maximum:
                    attachment_errors.append(
                        "spaced attachment lacks dedicated gap bounds"
                    )
                elif gap is None or not minimum <= gap <= maximum:
                    attachment_errors.append(
                        "spaced attachment gap is outside its dedicated bounds"
                    )
                child_components = registration_components.get(
                    str(declared.get("child_registration_id")), set()
                )
                parent_components = registration_components.get(
                    str(declared.get("parent_registration_id")), set()
                )
                if (
                    not attachment_errors
                    and len(child_components) == 1
                    and len(parent_components) == 1
                ):
                    spaced_component_edges.append(
                        (next(iter(child_components)), next(iter(parent_components)))
                    )
            elif not touching:
                attachment_errors.append("required contact is absent")
        passed = not attachment_errors
        record = {
            "attachment_id": attachment_id,
            "part_id": part_id,
            "parent_part_id": parent_part_id,
            "kind": kind,
            "child_registration_id": declared.get("child_registration_id")
            if declared
            else None,
            "parent_registration_id": declared.get("parent_registration_id")
            if declared
            else None,
            "gap_m": gap,
            "touching": touching,
            "passed": passed,
            "errors": attachment_errors,
        }
        semantic_attachments.append(record)
        if attachment_errors:
            errors.append(
                f"semantic attachment {attachment_id} failed: "
                + "; ".join(attachment_errors)
            )
    unknown_attachments = sorted(set(registry_attachment_map) - set(attachment_specs))
    if unknown_attachments:
        errors.append(
            "PartRegistry contains undeclared attachments: "
            + ", ".join(unknown_attachments)
        )
    report["attachments"] = semantic_attachments
    penetration_tolerance = _number(structural.get("penetration_tolerance_m")) or 0.0
    penetration_pairs: dict[tuple[str, str], dict[str, Any]] = {}
    unresolved_pairs: dict[tuple[str, str], dict[str, Any]] = {}
    for contact in contacts:
        if not isinstance(contact, dict):
            continue
        depth = _number(contact.get("penetration_depth_m"))
        measurement = contact.get("penetration_status")
        upper = _number(contact.get("penetration_upper_bound_m"))
        overlap_count = contact.get("overlap_triangle_pairs", 0)
        if measurement == "NONE" and depth == 0 and overlap_count == 0:
            continue
        if (
            measurement == "WITHIN_TOLERANCE"
            and depth is not None
            and depth <= penetration_tolerance
            and upper is not None
            and upper <= penetration_tolerance
        ):
            continue
        if measurement is not None and (
            measurement != "EXCEEDS_TOLERANCE"
            or depth is None
            or depth <= penetration_tolerance
        ):
            left_part, right_part = (
                contact.get("left_part_id"),
                contact.get("right_part_id"),
            )
            if isinstance(left_part, str) and isinstance(right_part, str):
                pair = _instance_pair(contact) or tuple(
                    sorted(
                        (
                            str(contact.get("left_island_id")),
                            str(contact.get("right_island_id")),
                        )
                    )
                )
                unresolved_pairs[pair] = {
                    "registration_ids": list(pair),
                    "left_part_id": left_part,
                    "right_part_id": right_part,
                    "status": "UNRESOLVED",
                    "lower_bound_m": depth,
                    "upper_bound_m": upper,
                    "tolerance_m": penetration_tolerance,
                }
            continue
        if depth is None or depth <= penetration_tolerance:
            continue
        left_part, right_part = (
            contact.get("left_part_id"),
            contact.get("right_part_id"),
        )
        if (
            contact.get("left_registration_id") == contact.get("right_registration_id")
            and contact.get("left_registration_id") is not None
        ):
            continue
        if not isinstance(left_part, str) or not isinstance(right_part, str):
            continue
        matching = [
            item
            for item in attachment_specs.values()
            if {item.get("part_id"), item.get("parent_part_id")}
            == {left_part, right_part}
            and _instance_pair(contact) is not None
            and _instance_pair(
                registry_attachment_map.get(item["attachment_id"], {}), attachment=True
            )
            == _instance_pair(contact)
        ]
        exempt = any(
            _has_exemption(
                "penetration",
                item["attachment_id"],
                str(item.get("part_id")),
                spec_exemptions,
                manifest_exemptions,
            )
            for item in matching
        )
        pair = _instance_pair(contact) or tuple(
            sorted(
                (
                    str(contact.get("left_island_id")),
                    str(contact.get("right_island_id")),
                )
            )
        )
        record = penetration_pairs.get(pair)
        if record is None:
            record = {
                "left_part_id": left_part,
                "right_part_id": right_part,
                "registration_ids": list(pair),
                "depth_m": depth,
                "tolerance_m": penetration_tolerance,
                "excess_m": round(depth - penetration_tolerance, 6),
                "attachment_ids": sorted(item["attachment_id"] for item in matching),
                "contact_count": 0,
                "exempt": exempt,
            }
            penetration_pairs[pair] = record
        record["contact_count"] += 1
        if depth > record["depth_m"]:
            record["depth_m"] = depth
            record["excess_m"] = round(depth - penetration_tolerance, 6)
    for record in penetration_pairs.values():
        report["penetrations"].append(record)
        if not record["exempt"]:
            errors.append(
                f"parts {record['left_part_id']} and {record['right_part_id']} "
                f"exceed penetration tolerance by {record['excess_m']:.6f} m"
            )
    for record in unresolved_pairs.values():
        report["penetrations"].append(record)
        errors.append(
            f"parts {record['left_part_id']} and {record['right_part_id']} "
            "have overlapping evaluated geometry but penetration depth is unverified"
        )

    required_openings = {
        item["feature_id"]: item
        for item in asset_spec.get("required_openings_or_negative_spaces", [])
        if isinstance(item, dict) and isinstance(item.get("feature_id"), str)
    }
    measured_openings = {
        item.get("feature_id"): item
        for item in negative_spaces
        if isinstance(item, dict) and isinstance(item.get("feature_id"), str)
    }
    opening_results: list[dict[str, Any]] = []
    for feature_id, expected in required_openings.items():
        measured = measured_openings.get(feature_id)
        passed = (
            isinstance(measured, dict)
            and measured.get("owner_part_id") == expected.get("owner_part_id")
            and measured.get("kind") == expected.get("kind", "through_opening")
            and measured.get("bbox_span_valid") is True
            and measured.get("passed") is True
        )
        opening_results.append(
            {
                "feature_id": feature_id,
                "owner_part_id": expected.get("owner_part_id"),
                "passed": passed,
                "measurement": measured,
            }
        )
        if not passed:
            errors.append(
                f"required negative space {feature_id} has no clear geometry probe"
            )
    unknown_openings = sorted(set(measured_openings) - set(required_openings))
    if unknown_openings:
        errors.append(
            "PartRegistry contains undeclared negative spaces: "
            + ", ".join(unknown_openings)
        )
    report["negative_spaces"] = opening_results

    if asset_spec.get("material_regions"):
        declared_regions = (
            registry.get("material_regions", []) if isinstance(registry, dict) else []
        )
        by_region = {
            item.get("region_id"): item
            for item in declared_regions
            if isinstance(item, dict)
        }
        observed_faces = metrics.get("part_material_faces", {})
        if not isinstance(observed_faces, dict):
            observed_faces = {}
        expected_regions = {
            item["region_id"]: item for item in asset_spec.get("material_regions", [])
        }
        for region_id, expected in expected_regions.items():
            declared = by_region.get(region_id)
            material_name = (
                declared.get("material_name") if isinstance(declared, dict) else None
            )
            parts_match = isinstance(declared, dict) and set(
                declared.get("part_ids", [])
            ) == set(expected["part_ids"])
            passed = (
                parts_match
                and isinstance(material_name, str)
                and all(
                    observed_faces.get(part_id, {}).get(material_name, 0) > 0
                    for part_id in expected["part_ids"]
                )
            )
            report["material_regions"].append(
                {
                    "region_id": region_id,
                    "material_name": material_name,
                    "part_ids": expected["part_ids"],
                    "passed": passed,
                }
            )
            if not passed:
                errors.append(
                    f"material region {region_id} is not assigned to all declared parts"
                )
        if set(by_region) - set(expected_regions):
            errors.append("PartRegistry contains undeclared material regions")

    component_ids = {
        item.get("contact_component")
        for item in islands
        if isinstance(item, dict) and isinstance(item.get("contact_component"), int)
    }
    connectivity_passed = _connected_with_spaced_constraints(
        component_ids, spaced_component_edges
    )
    if not component_ids:
        connectivity_passed = False
    if not connectivity_passed:
        errors.append(
            "evaluated mesh islands form disconnected, unexempted assembly components"
        )
    report["semantic_connectivity_passed"] = connectivity_passed

    report.update(
        {
            "passed": not errors,
            "errors": list(dict.fromkeys(errors)),
            "warnings": list(dict.fromkeys(warnings)),
        }
    )
    return report


__all__ = ["evaluate_geometry_contract"]
