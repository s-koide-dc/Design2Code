# -*- coding: utf-8 -*-
import unittest

from src.code_generation.design_ops_resolver import DesignOpsResolver


class TestDesignOpsResolverAssets(unittest.TestCase):
    def test_dictionary_glosses_expand_candidate_query_without_replacing_source_text(self):
        resolver = object.__new__(DesignOpsResolver)
        resolver._last_stats = {"dictionary_terms": 0}
        context = {
            "analysis": {
                "topics": [
                    {"text": "取得", "meaning": "acquisition; fetch"},
                    {"text": "商品", "meaning": "commodity; product"},
                ],
                "syntax_tree": [],
            }
        }

        query = resolver._build_query_from_context(context, "商品を取得する")

        self.assertIn("取得", query)
        self.assertIn("acquisition; fetch", query)
        self.assertIn("commodity; product", query)
        self.assertIn("商品を取得する", query)
        self.assertEqual(resolver._last_stats["dictionary_terms"], 2)
