"""Pure-Python regression tests for geometry and assembly hard gates."""

from __future__ import annotations

import copy
import unittest

from inf_agent.geometry.assembly import LocalFrame
from inf_agent.geometry.validation import evaluate_geometry_contract


def _contracts() -> tuple[dict, dict]:
    asset_spec = {
        "required_parts": [
            {"part_id": "body", "minimum_count": 1, "maximum_count": 1},
            {"part_id": "handle", "minimum_count": 1, "maximum_count": 1},
        ],
        "attachment_constraints": [
            {
                "attachment_id": "handle_to_body",
                "part_id": "handle",
                "parent_part_id": "body",
                "kind": "contact",
            }
        ],
        "required_openings_or_negative_spaces": [
            {
                "feature_id": "handle_opening",
                "owner_part_id": "handle",
                "kind": "through_opening",
            }
        ],
        "geometry_exemptions": [],
    }
    part_manifest = {
        "parts": [
            {
                "part_id": "body",
                "parent_part_id": None,
                "exemptions": [],
            },
            {
                "part_id": "handle",
                "parent_part_id": "body",
                "exemptions": [],
            },
        ]
    }
    return asset_spec, part_manifest


def _metrics() -> dict:
    return {
        "part_registry": {
            "available": True,
            "valid": True,
            "errors": [],
            "registrations": [
                {
                    "registration_index": 1,
                    "registration_id": "body_001",
                    "part_id": "body",
                    "parent_part_id": None,
                },
                {
                    "registration_index": 2,
                    "registration_id": "handle_001",
                    "part_id": "handle",
                    "parent_part_id": "body",
                },
            ],
            "attachments": [
                {
                    "attachment_id": "handle_to_body",
                    "part_id": "handle",
                    "parent_part_id": "body",
                    "child_registration_id": "handle_001",
                    "parent_registration_id": "body_001",
                    "kind": "contact",
                    "minimum_gap_m": None,
                    "maximum_gap_m": None,
                }
            ],
            "openings": [{"feature_id": "handle_opening"}],
        },
        "evaluated_mesh_islands": [
            {
                "island_id": "body:island_001",
                "registration_indices": [1],
                "registration_id": "body_001",
                "part_id": "body",
                "contact_component": 0,
            },
            {
                "island_id": "joined:island_002",
                "registration_indices": [2],
                "registration_id": "handle_001",
                "part_id": "handle",
                "contact_component": 0,
            },
        ],
        "structural": {
            "connected": True,
            "connected_component_count": 1,
            "penetration_tolerance_m": 0.01,
            "contacts": [
                {
                    "left_registration_id": "body_001",
                    "right_registration_id": "handle_001",
                    "left_part_id": "body",
                    "right_part_id": "handle",
                    "surface_distance_m": 0.001,
                    "within_tolerance": True,
                    "penetration_depth_m": 0.0,
                }
            ],
        },
        "negative_spaces": [
            {
                "feature_id": "handle_opening",
                "owner_part_id": "handle",
                "kind": "through_opening",
                "bbox_span_valid": True,
                "passed": True,
            }
        ],
    }


class GeometryValidationTests(unittest.TestCase):
    def test_valid_registered_assembly_passes(self) -> None:
        asset_spec, manifest = _contracts()
        report = evaluate_geometry_contract(
            asset_spec=asset_spec,
            part_manifest=manifest,
            metrics=_metrics(),
        )
        self.assertTrue(report["passed"], report["errors"])

    def test_joined_mesh_island_identity_does_not_hide_disconnection(self) -> None:
        asset_spec, manifest = _contracts()
        metrics = _metrics()
        metrics["evaluated_mesh_islands"][1]["contact_component"] = 1
        metrics["structural"]["connected"] = False
        metrics["structural"]["connected_component_count"] = 2
        metrics["structural"]["contacts"][0]["within_tolerance"] = False
        metrics["structural"]["contacts"][0]["surface_distance_m"] = 0.2

        report = evaluate_geometry_contract(
            asset_spec=asset_spec,
            part_manifest=manifest,
            metrics=metrics,
        )

        self.assertFalse(report["passed"])
        self.assertTrue(any("attachment" in item for item in report["errors"]))
        self.assertTrue(any("disconnected" in item for item in report["errors"]))

    def test_multiple_islands_for_one_registration_fail_without_exemption(self) -> None:
        asset_spec, manifest = _contracts()
        metrics = _metrics()
        duplicate = copy.deepcopy(metrics["evaluated_mesh_islands"][1])
        duplicate["island_id"] = "joined:island_003"
        duplicate["contact_component"] = 1
        metrics["evaluated_mesh_islands"].append(duplicate)

        report = evaluate_geometry_contract(
            asset_spec=asset_spec,
            part_manifest=manifest,
            metrics=metrics,
        )

        self.assertFalse(report["passed"])
        self.assertTrue(
            any("disconnected mesh islands" in item for item in report["errors"])
        )

    def test_spaced_attachment_requires_spec_exemption_and_gap_bounds(self) -> None:
        asset_spec, manifest = _contracts()
        metrics = _metrics()
        asset_spec["attachment_constraints"][0].update(
            kind="spaced", minimum_gap_m=0.1, maximum_gap_m=0.3
        )
        metrics["part_registry"]["attachments"][0]["kind"] = "spaced"
        metrics["part_registry"]["attachments"][0]["minimum_gap_m"] = 0.1
        metrics["part_registry"]["attachments"][0]["maximum_gap_m"] = 0.3
        metrics["structural"]["contacts"][0]["within_tolerance"] = False
        metrics["structural"]["contacts"][0]["surface_distance_m"] = 0.2
        metrics["evaluated_mesh_islands"][1]["contact_component"] = 1
        asset_spec["geometry_exemptions"] = [
            {
                "exemption_id": "handle_spacing",
                "kind": "non_contact",
                "target_id": "handle_to_body",
                "reason": "fixture spacing",
                "evidence": [],
            }
        ]
        manifest["parts"][1]["exemptions"] = ["non_contact:handle_to_body"]

        report = evaluate_geometry_contract(
            asset_spec=asset_spec,
            part_manifest=manifest,
            metrics=metrics,
        )

        self.assertTrue(report["passed"], report["errors"])

    def test_excessive_penetration_and_missing_opening_are_hard_failures(self) -> None:
        asset_spec, manifest = _contracts()
        metrics = _metrics()
        metrics["structural"]["contacts"][0]["penetration_depth_m"] = 0.08
        metrics["negative_spaces"][0]["passed"] = False

        report = evaluate_geometry_contract(
            asset_spec=asset_spec,
            part_manifest=manifest,
            metrics=metrics,
        )

        self.assertFalse(report["passed"])
        self.assertTrue(any("penetration" in item for item in report["errors"]))
        self.assertTrue(any("negative space" in item for item in report["errors"]))

    def test_symmetric_penetration_contacts_are_one_diagnostic_pair(self) -> None:
        asset_spec, manifest = _contracts()
        metrics = _metrics()
        first = metrics["structural"]["contacts"][0]
        first["penetration_depth_m"] = 0.04
        reverse = copy.deepcopy(first)
        reverse["left_part_id"], reverse["right_part_id"] = (
            first["right_part_id"],
            first["left_part_id"],
        )
        reverse["penetration_depth_m"] = 0.08
        metrics["structural"]["contacts"].append(reverse)
        report = evaluate_geometry_contract(
            asset_spec=asset_spec,
            part_manifest=manifest,
            metrics=metrics,
        )
        self.assertEqual(len(report["penetrations"]), 1)
        self.assertEqual(report["penetrations"][0]["contact_count"], 2)
        self.assertEqual(report["penetrations"][0]["depth_m"], 0.08)
        self.assertAlmostEqual(report["penetrations"][0]["excess_m"], 0.07)
        self.assertEqual(
            report["penetrations"][0]["attachment_ids"], ["handle_to_body"]
        )
        self.assertEqual(
            sum("exceed penetration" in error for error in report["errors"]), 1
        )

    def test_unverified_mesh_penetration_fails_closed_without_false_depth(self) -> None:
        asset_spec, manifest = _contracts()
        metrics = _metrics()
        contact = metrics["structural"]["contacts"][0]
        contact.update(
            {
                "penetration_depth_m": 0.0,
                "penetration_upper_bound_m": 0.02,
                "penetration_status": "UNRESOLVED",
                "overlap_triangle_pairs": 40,
            }
        )
        reverse = copy.deepcopy(contact)
        reverse["left_part_id"], reverse["right_part_id"] = (
            contact["right_part_id"],
            contact["left_part_id"],
        )
        metrics["structural"]["contacts"].append(reverse)
        report = evaluate_geometry_contract(
            asset_spec=asset_spec,
            part_manifest=manifest,
            metrics=metrics,
        )
        self.assertFalse(report["passed"])
        self.assertEqual(len(report["penetrations"]), 1)
        self.assertEqual(report["penetrations"][0]["status"], "UNRESOLVED")
        self.assertEqual(
            sum(
                "penetration depth is unverified" in error for error in report["errors"]
            ),
            1,
        )

    def test_inconsistent_mesh_penetration_status_fails_closed(self) -> None:
        asset_spec, manifest = _contracts()
        for status, lower, upper, overlaps in (
            ("NONE", 0.04, 0.05, 0),
            ("NONE", 0.0, 0.05, 2),
            ("WITHIN_TOLERANCE", 0.0, 0.05, 2),
            ("EXCEEDS_TOLERANCE", 0.0, 0.05, 2),
            ("UNRESOLVED", 0.0, None, 0),
        ):
            with self.subTest(
                status=status, lower=lower, upper=upper, overlaps=overlaps
            ):
                metrics = _metrics()
                metrics["structural"]["contacts"][0].update(
                    {
                        "penetration_status": status,
                        "penetration_depth_m": lower,
                        "penetration_upper_bound_m": upper,
                        "overlap_triangle_pairs": overlaps,
                    }
                )
                report = evaluate_geometry_contract(
                    asset_spec=asset_spec,
                    part_manifest=manifest,
                    metrics=metrics,
                )
                self.assertFalse(report["passed"])
                self.assertEqual(report["penetrations"][0]["status"], "UNRESOLVED")

    def test_local_frame_rejects_singular_basis(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-singular"):
            LocalFrame(basis=((1, 0, 0), (1, 0, 0), (0, 0, 1)))


if __name__ == "__main__":
    unittest.main()
