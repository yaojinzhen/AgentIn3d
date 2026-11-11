"""Knowledge query paths and typed references round-trip through the source reader."""

import unittest
from pathlib import Path
from inf_agent.indexing.query import documentation_query_result
from inf_agent.knowledge.resolver import read_knowledge


class KnowledgeRoundTripTests(unittest.TestCase):
    def test_reference_kinds_do_not_masquerade_as_reader_symbols(self):
        from inf_agent.indexing.query import _readable_references

        root = Path(__file__).resolve().parents[2]
        result = _readable_references(
            root,
            dict(
                documents=["asset_examples/objects/apple_fruit.md#苹果原生参考"],
                source_symbols=[
                    "infinigen/assets/objects/fruits/apple.py:FruitFactoryApple",
                    "infinigen/assets/objects",
                    "infinigen.core.util.blender",
                    "infinigen/core/nodes/node_wrangler.py:83",
                    "bpy.types.Mesh.from_pydata",
                ],
            ),
        )
        self.assertEqual(
            [r["kind"] for r in result["source_references"]],
            [
                "repository_symbol",
                "repository_directory",
                "repository_module",
                "source_location",
                "external_api",
            ],
        )
        self.assertEqual(
            result["source_symbols"],
            ["infinigen.assets.objects.fruits.apple:FruitFactoryApple"],
        )
        self.assertEqual(result["source_references"][3]["source_line"], 83)
        self.assertEqual(result["document_heading"], "苹果原生参考")

    def test_real_query_results_can_be_read_directly(self):
        root = Path(__file__).resolve().parents[2]
        for domain, query in [
            ("object", "apple"),
            ("pattern", "curve sweep"),
            ("material", "wood"),
            ("api", "NodeWrangler"),
            ("api", "from_pydata"),
        ]:
            with self.subTest(domain=domain, query=query):
                matches = documentation_query_result(root, domain, query)["matches"]
                self.assertTrue(matches)
                if domain == "object" or query == "NodeWrangler":
                    self.assertTrue(matches[0]["source_symbols"])
                for match in matches:
                    self.assertEqual(match["document_path"], match["documents"][0])
                    for document in match["documents"]:
                        self.assertNotIn("#", document)
                        self.assertTrue(
                            read_knowledge(root, document=document)["content"]
                        )
                    for symbol in match["source_symbols"]:
                        self.assertTrue(read_knowledge(root, symbol=symbol)["content"])


if __name__ == "__main__":
    unittest.main()
