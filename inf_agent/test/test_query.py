"""Tests for deterministic, domain-isolated, bounded query output."""

from __future__ import annotations

import json
from pathlib import Path

from helpers import TemporaryWorkspaceTestCase

from inf_agent.indexing.query import (
    IndexQueryError,
    documentation_query_result,
    query_api_symbols,
    query_document_routes,
    render_bounded_result,
)


class QueryTests(TemporaryWorkspaceTestCase):
    def _write_object_route(self) -> Path:
        path = (
            self.repo_root
            / "inf_agent"
            / "modeling_docs"
            / "asset_examples"
            / "objects"
            / "chair.md"
        )
        path.parent.mkdir(parents=True)
        path.write_text(
            """---
domain: object
id: office_chair
intent: office chair
aliases: ["chair", "seat"]
use_when: ["model a chair"]
avoid_when: ["model a table"]
summary: Build a procedural office chair.
---
# Office chair

Routing fixture body.
""",
            encoding="utf-8",
        )
        return path

    def test_document_query_returns_only_high_confidence_route(self) -> None:
        self._write_object_route()

        result = documentation_query_result(
            self.repo_root,
            "object",
            "chair",
            limit=3,
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["returned_count"], 1)
        self.assertEqual(result["matches"][0]["id"], "office_chair")
        self.assertGreaterEqual(result["matches"][0]["confidence"], 0.8)

    def test_unmatched_document_query_returns_no_plausible_fuzzy_match(self) -> None:
        self._write_object_route()

        matches = query_document_routes(
            self.repo_root,
            "object",
            "volcanic mushroom",
        )

        self.assertEqual(matches, [])

    def test_english_alias_requires_word_boundaries(self) -> None:
        self._write_object_route()

        matches = query_document_routes(self.repo_root, "object", "wheelchair")

        self.assertEqual(matches, [])

    def test_exact_module_symbol_filters_same_named_api_symbols(self) -> None:
        index = {
            "symbols": [
                {
                    "id": "one",
                    "name": "Factory",
                    "qualname": "package.one.Factory",
                    "module": "package.one",
                    "kind": "class",
                    "source_path": "package/one.py",
                    "api_docs": ["api_reference/function_api/one.md"],
                },
                {
                    "id": "two",
                    "name": "Factory",
                    "qualname": "package.two.Factory",
                    "module": "package.two",
                    "kind": "class",
                    "source_path": "package/two.py",
                    "api_docs": ["api_reference/function_api/two.md"],
                },
            ]
        }

        matches = query_api_symbols(index, "package.one:Factory")

        self.assertEqual([item["id"] for item in matches], ["one"])
        self.assertEqual(query_api_symbols(index, "Factory"), [])

    def test_rendered_result_never_exceeds_character_budget(self) -> None:
        records = [
            {
                "id": f"record_{index}",
                "name": "fixture",
                "description": "x" * 1000,
            }
            for index in range(5)
        ]

        rendered = render_bounded_result(
            query_type="asset",
            query="q" * 800,
            records=records,
            max_chars=800,
            requested_limit=5,
        )
        payload = json.loads(rendered)

        self.assertLessEqual(len(rendered), 800)
        self.assertLessEqual(len(payload["query"]), 500)
        self.assertTrue(payload["truncated"])
        self.assertLess(payload["returned_count"], 5)

    def test_too_small_character_budget_is_rejected(self) -> None:
        with self.assertRaisesRegex(IndexQueryError, "at least 512"):
            render_bounded_result(
                query_type="asset",
                query="chair",
                records=[],
                max_chars=511,
                requested_limit=1,
            )


if __name__ == "__main__":
    import unittest

    unittest.main()
