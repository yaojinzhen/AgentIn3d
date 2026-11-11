"""Instance-bound contacts, penetration exemptions and declared gap measurements."""

import copy
import unittest
from test_geometry_validation import _contracts, _metrics
from inf_agent.geometry.validation import evaluate_geometry_contract


class InstanceMeasurementTests(unittest.TestCase):
    def evaluate(self, spec, manifest, metrics):
        return evaluate_geometry_contract(
            asset_spec=spec, part_manifest=manifest, metrics=metrics
        )

    def repeated(self):
        spec, manifest = _contracts()
        metrics = _metrics()
        spec["required_parts"][1].update(minimum_count=2, maximum_count=2)
        instance = copy.deepcopy(metrics["part_registry"]["registrations"][1])
        instance.update(registration_id="handle_002", registration_index=3)
        metrics["part_registry"]["registrations"].append(instance)
        island = copy.deepcopy(metrics["evaluated_mesh_islands"][1])
        island.update(
            island_id="handle2", registration_id="handle_002", registration_indices=[3]
        )
        metrics["evaluated_mesh_islands"].append(island)
        metrics["structural"]["contacts"][0].update(
            left_registration_id="body_001", right_registration_id="handle_001"
        )
        return spec, manifest, metrics

    def test_other_instance_contact_cannot_satisfy_attachment(self):
        spec, manifest, metrics = self.repeated()
        metrics["part_registry"]["attachments"][0]["child_registration_id"] = (
            "handle_002"
        )
        report = self.evaluate(spec, manifest, metrics)
        self.assertFalse(report["passed"])
        self.assertFalse(report["attachments"][0]["passed"])

    def test_wrong_instance_identity_cannot_satisfy_attachment(self):
        spec, manifest, metrics = self.repeated()
        metrics["part_registry"]["attachments"][0]["child_registration_id"] = "body_001"
        self.assertFalse(self.evaluate(spec, manifest, metrics)["passed"])

    def test_penetration_exemption_only_covers_declared_instances(self):
        spec, manifest, metrics = self.repeated()
        spec["geometry_exemptions"] = [
            {"kind": "penetration", "target_id": "handle_to_body"}
        ]
        manifest["parts"][1]["exemptions"] = ["penetration:handle_to_body"]
        contact = copy.deepcopy(metrics["structural"]["contacts"][0])
        contact.update(right_registration_id="handle_002", penetration_depth_m=0.08)
        metrics["structural"]["contacts"].append(contact)
        report = self.evaluate(spec, manifest, metrics)
        self.assertFalse(report["passed"])
        self.assertFalse(report["penetrations"][0]["exempt"])

    def test_each_repeated_attachment_has_independent_result(self):
        spec, manifest, metrics = self.repeated()
        spec["attachment_constraints"].append(
            dict(spec["attachment_constraints"][0], attachment_id="handle2_to_body")
        )
        metrics["part_registry"]["attachments"].append(
            dict(
                metrics["part_registry"]["attachments"][0],
                attachment_id="handle2_to_body",
                child_registration_id="handle_002",
            )
        )
        contacts = metrics["structural"]["contacts"]
        contacts.append(
            dict(
                contacts[0],
                right_registration_id="handle_002",
                surface_distance_m=0.5,
                within_tolerance=False,
            )
        )
        report = self.evaluate(spec, manifest, metrics)
        self.assertEqual(
            [item["passed"] for item in report["attachments"]], [True, False]
        )
        self.assertEqual(
            [item["gap_m"] for item in report["attachments"]], [0.001, 0.5]
        )

    def test_anchor_owned_by_sibling_fails_attachment_record(self):
        spec, manifest, metrics = self.repeated()
        spec["attachment_constraints"][0]["require_anchors"] = True
        metrics["part_registry"]["anchors"] = [
            dict(anchor_id="child", registration_id="handle_002"),
            dict(anchor_id="parent", registration_id="body_001"),
        ]
        metrics["part_registry"]["attachments"][0].update(
            child_anchor_id="child", parent_anchor_id="parent"
        )
        report = self.evaluate(spec, manifest, metrics)
        self.assertFalse(report["attachments"][0]["passed"])
        self.assertTrue(
            any("anchor" in error for error in report["attachments"][0]["errors"])
        )

    def test_penetration_between_same_semantic_part_instances_is_not_skipped(self):
        spec, manifest, metrics = self.repeated()
        metrics["structural"]["contacts"].append(
            dict(
                left_part_id="handle",
                right_part_id="handle",
                left_registration_id="handle_001",
                right_registration_id="handle_002",
                surface_distance_m=0,
                within_tolerance=True,
                penetration_depth_m=0.08,
            )
        )
        self.assertFalse(self.evaluate(spec, manifest, metrics)["passed"])

    def spaced(self, minimum=0.01, maximum=0.02, gap=0.015):
        spec, manifest = _contracts()
        metrics = _metrics()
        spec["attachment_constraints"][0].update(
            kind="spaced", minimum_gap_m=minimum, maximum_gap_m=maximum
        )
        metrics["part_registry"]["attachments"][0].update(
            kind="spaced", minimum_gap_m=minimum, maximum_gap_m=maximum
        )
        metrics["structural"]["contacts"][0].update(
            left_registration_id="body_001",
            right_registration_id="handle_001",
            within_tolerance=False,
            surface_distance_m=gap,
        )
        spec["geometry_exemptions"] = [
            {"kind": "non_contact", "target_id": "handle_to_body"}
        ]
        manifest["parts"][1]["exemptions"] = ["non_contact:handle_to_body"]
        return spec, manifest, metrics

    def test_registry_cannot_widen_design_gap_bounds(self):
        spec, manifest, metrics = self.spaced(gap=0.15)
        metrics["part_registry"]["attachments"][0].update(
            minimum_gap_m=0.1, maximum_gap_m=0.2
        )
        self.assertFalse(self.evaluate(spec, manifest, metrics)["passed"])

    def test_spaced_boundaries_and_invalid_units(self):
        for minimum, maximum, gap, passed in [
            (0.01, 0.02, 0.01, True),
            (0.01, 0.02, 0.02, True),
            (0.01, 0.02, 0.021, False),
            ("1cm", 0.02, 0.015, False),
            (-1, 0.02, 0.015, False),
            (0.02, 0.01, 0.015, False),
        ]:
            with self.subTest(minimum=minimum, maximum=maximum, gap=gap):
                self.assertEqual(
                    self.evaluate(*self.spaced(minimum, maximum, gap))["passed"], passed
                )


if __name__ == "__main__":
    unittest.main()
