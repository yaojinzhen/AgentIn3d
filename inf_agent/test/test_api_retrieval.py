"""Common API queries must expose their actual matching evidence."""

import json
import subprocess
import sys
import unittest
from pathlib import Path

from inf_agent.indexing.query import IndexQueryError, documentation_query_result
from inf_agent.knowledge.resolver import read_knowledge

ROOT = Path(__file__).resolve().parents[2]


class RetrievalTests(unittest.TestCase):
    def query(self, text, **kwargs):
        return documentation_query_result(ROOT, "api", text, **kwargs)["matches"]

    def test_external_mesh_api_has_explicit_alias(self):
        result = self.query("from_pydata")[0]
        self.assertEqual(result["id"], "documented:bpy.types.Mesh.from_pydata")
        self.assertEqual(result["match_type"], "alias")
        self.assertIn("from_pydata", result["why"])
        self.assertLess(result["confidence"], 1)
        self.assertEqual(result["source_symbols"], [])
        self.assertEqual(result["source_references"][0]["kind"], "external_api")

    def test_common_identifiers_find_owner_document(self):
        cases = [
            ("NodeWrangler", "node_wrangler_usage.md"),
            ("NodeWrangler.new_node", "node_wrangler_usage.md"),
            ("object_from_VF", "attributes_and_mesh_data.md"),
            ("Nodes.Math", "math_logic_nodes.md"),
        ]
        for query, document in cases:
            with self.subTest(query=query):
                result = self.query(query)[0]
                self.assertEqual(result["match_type"], "exact_symbol")
                self.assertTrue(result["document_path"].endswith(document), result)
                self.assertTrue(
                    read_knowledge(ROOT, document=result["document_path"])["content"]
                )
                for symbol in result["source_symbols"]:
                    self.assertTrue(read_knowledge(ROOT, symbol=symbol)["content"])

    def test_common_material_node_and_operation_queries(self):
        cases = [
            ("Nodes.SetMaterial", "exact_symbol", "material_nodes.md"),
            ("ShaderNodeMix", "alias", "color_processing_nodes.md"),
            (
                "infinigen.core.surface:assign_material",
                "exact_symbol",
                "surface_material_ops.md",
            ),
            ("curve sweep", "operation_route", "blender_helper_objects.md"),
            ("curve_sweep", "operation_route", "blender_helper_objects.md"),
            ("material assignment", "operation_route", "surface_material_ops.md"),
            ("revolve", "operation_route", "attributes_and_mesh_data.md"),
            ("Mesh.from_pydata", "alias", "assets_object_mesh_helpers.md"),
            ("from pydata", "alias", "assets_object_mesh_helpers.md"),
        ]
        for query, match_type, document in cases:
            with self.subTest(query=query):
                result = self.query(query)[0]
                self.assertEqual(result["match_type"], match_type)
                self.assertTrue(result["document_path"].endswith(document), result)

    def test_qualified_method_round_trips(self):
        query = "infinigen.core.nodes.node_wrangler:NodeWrangler.new_node"
        result = self.query(query)[0]
        self.assertEqual(result["id"], query)
        self.assertEqual(result["match_type"], "exact_symbol")

    def test_identifier_fragments_do_not_claim_exactness(self):
        self.assertEqual(self.query("from_unknown_pydata"), [])
        matches = self.query("wrangler")
        self.assertTrue(matches)
        self.assertTrue(all(item["match_type"] == "token_related" for item in matches))
        self.assertTrue(all(item["confidence"] <= 0.6 for item in matches))

    def test_operation_and_exact_external_api_are_distinct(self):
        operation = self.query("profile revolve")[0]
        self.assertEqual(operation["match_type"], "operation_route")
        self.assertIn("route_match_type", operation)
        external = self.query("bpy.types.Mesh.from_pydata")[0]
        self.assertEqual(external["match_type"], "exact_documented_interface")
        self.assertEqual(external["confidence"], 1)

    def test_cli_limit_example_has_no_eight_kib_truncation(self):
        output = subprocess.check_output(
            [
                sys.executable,
                "-B",
                "-m",
                "inf_agent.cli",
                "query",
                "api",
                "--query",
                "wrangler",
                "--limit",
                "8",
            ],
            cwd=ROOT,
            encoding="utf-8",
        )
        result = json.loads(output)
        self.assertEqual(result["returned_count"], 8)
        self.assertGreater(len(output.encode("utf-8")), 8192)

    def test_limit_is_configurable_and_validated(self):
        self.assertGreater(len(self.query("wrangler", limit=8)), 3)
        with self.assertRaisesRegex(IndexQueryError, "at least 1"):
            self.query("NodeWrangler", limit=0)
