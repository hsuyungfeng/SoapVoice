#!/usr/bin/env python3
"""
Test suite for Hybrid RAG Search
Validates search accuracy with known test cases
"""

import sys
import os
import json
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from optimized_hybrid_search import OptimizedHybridSearch


class SearchAccuracyTester:
    def __init__(self):
        base_dir = Path(__file__).parent.parent
        self.searcher = OptimizedHybridSearch(
            tree_dir=str(base_dir / "PageIndex/results"),
            doc_dir=str(base_dir / "審查注意事項"),
        )
        self.results = []

    def run_test(
        self,
        query: str,
        expected_doc: str = None,
        expected_section: str = None,
        method: str = "hybrid",
    ) -> dict:
        """Run a single test case"""
        results = self.searcher.search(query, top_k=5, method=method)

        passed = False
        matched_doc = None
        matched_section = None
        rank = None

        if results:
            # Check if expected document is in top results
            for i, r in enumerate(results, 1):
                if expected_doc and expected_doc in r.get("doc_title", ""):
                    passed = True
                    matched_doc = r["doc_title"]
                    matched_section = r.get("title", "")
                    rank = i
                    break

        return {
            "query": query,
            "method": method,
            "expected_doc": expected_doc,
            "expected_section": expected_section,
            "passed": passed,
            "rank": rank,
            "matched_doc": matched_doc,
            "matched_section": matched_section,
            "top_result": results[0]["doc_title"] if results else None,
            "top_score": results[0]["score"] if results else 0,
        }

    def test_keyword_search(self):
        """Test keyword-based searches"""
        test_cases = [
            {
                "query": "居家照護",
                "expected_doc": "居家照護",
                "description": "搜尋居家照護應找到相關文件",
            },
            {
                "query": "巡迴醫療",
                "expected_doc": "巡迴",
                "description": "搜尋巡迴醫療",
            },
            {
                "query": "牙醫",
                "expected_doc": "牙醫",
                "description": "搜尋牙醫應找到牙醫文件",
            },
            {
                "query": "眼科",
                "expected_doc": "眼科",
                "description": "搜尋眼科應找到眼科文件",
            },
            {
                "query": "手術",
                "expected_doc": "手術",
                "description": "搜尋手術應找到手術文件",
            },
            {
                "query": "安寧療護",
                "expected_doc": "安寧",
                "description": "搜尋安寧療護",
            },
            {"query": "注射", "expected_doc": "注射", "description": "搜尋注射"},
            {"query": "檢查", "expected_doc": "檢查", "description": "搜尋檢查"},
            {
                "query": "精神醫療",
                "expected_doc": "精神",
                "description": "搜尋精神醫療",
            },
            {"query": "DRG", "expected_doc": "DRG", "description": "搜尋 DRG 分類"},
        ]

        results = []
        for tc in test_cases:
            result = self.run_test(
                tc["query"], tc["expected_doc"], tc.get("expected_section")
            )
            result["description"] = tc["description"]
            results.append(result)

        return results

    def test_code_search(self):
        """Test medical code searches"""
        test_cases = [
            {"code": "48001C", "description": "手術代碼"},
            {"code": "48011C", "description": "手術加成代碼"},
            {"code": "62001C", "description": "皮膚科代碼"},
            {"code": "63001C", "description": "乳房代碼"},
            {"code": "A001", "description": "診察費代碼"},
            {"code": "B001", "description": "檢驗代碼"},
        ]

        results = []
        for tc in test_cases:
            search_results = self.searcher.search_by_code(tc["code"], top_k=5)

            passed = False
            rank = None
            if search_results:
                for i, r in enumerate(search_results, 1):
                    if (
                        tc["code"].lower() in r.get("text", "").lower()
                        or tc["code"].lower() in r.get("title", "").lower()
                    ):
                        passed = True
                        rank = i
                        break

            results.append(
                {
                    "query": tc["code"],
                    "description": tc["description"],
                    "method": "code_search",
                    "passed": passed,
                    "rank": rank,
                    "top_result": search_results[0]["doc_title"]
                    if search_results
                    else None,
                    "has_code": tc["code"] in search_results[0]["text"]
                    if search_results
                    else False,
                }
            )

        return results

    def test_combined_search(self):
        """Test combined query + code searches"""
        test_cases = [
            {"query": "手術", "code": "48001C", "description": "手術代碼相關"},
            {"query": "居家", "code": None, "description": "居家相關"},
            {"query": "牙醫", "code": "62001C", "description": "牙科代碼"},
        ]

        results = []
        for tc in test_cases:
            if tc["code"]:
                search_results = self.searcher.search_combined(
                    query=tc["query"], code=tc["code"], top_k=5
                )
            else:
                search_results = self.searcher.search(tc["query"], top_k=5)

            passed = False
            if search_results:
                doc_match = tc["query"] in search_results[0].get("doc_title", "")
                if tc["code"]:
                    code_match = any(
                        tc["code"] in r.get("text", "") for r in search_results[:3]
                    )
                    passed = doc_match or code_match
                else:
                    passed = doc_match

            results.append(
                {
                    "query": tc["query"],
                    "code": tc["code"],
                    "description": tc["description"],
                    "method": "combined",
                    "passed": passed,
                    "top_result": search_results[0]["doc_title"]
                    if search_results
                    else None,
                }
            )

        return results

    def test_method_comparison(self):
        """Compare different search methods"""
        queries = ["居家照護", "手術費用", "牙醫審查"]

        results = []
        for query in queries:
            row = {"query": query}

            for method in ["tree", "vector", "hybrid"]:
                method_results = self.searcher.search(query, top_k=5, method=method)
                row[f"{method}_count"] = len(method_results)
                row[f"{method}_top"] = (
                    method_results[0]["doc_title"][:20] if method_results else None
                )
                row[f"{method}_score"] = (
                    method_results[0]["score"] if method_results else 0
                )

            results.append(row)

        return results

    def run_all_tests(self):
        """Run all test suites"""
        print("=" * 60)
        print("Search Accuracy Test Suite")
        print("=" * 60)

        all_results = {
            "keyword_search": self.test_keyword_search(),
            "code_search": self.test_code_search(),
            "combined_search": self.test_combined_search(),
            "method_comparison": self.test_method_comparison(),
        }

        # Print summary
        print("\n### Keyword Search Results ###")
        passed = sum(1 for r in all_results["keyword_search"] if r["passed"])
        total = len(all_results["keyword_search"])
        print(f"Passed: {passed}/{total} ({passed / total * 100:.1f}%)")
        for r in all_results["keyword_search"]:
            status = "✓" if r["passed"] else "✗"
            print(
                f"  {status} {r['description']}: rank={r['rank']}, doc={r.get('top_result', 'N/A')[:30]}"
            )

        print("\n### Code Search Results ###")
        passed = sum(1 for r in all_results["code_search"] if r["passed"])
        total = len(all_results["code_search"])
        print(f"Passed: {passed}/{total} ({passed / total * 100:.1f}%)")
        for r in all_results["code_search"]:
            status = "✓" if r["passed"] else "✗"
            print(
                f"  {status} {r['description']}: rank={r['rank']}, code_in_text={r.get('has_code', False)}"
            )

        print("\n### Combined Search Results ###")
        passed = sum(1 for r in all_results["combined_search"] if r["passed"])
        total = len(all_results["combined_search"])
        print(f"Passed: {passed}/{total} ({passed / total * 100:.1f}%)")
        for r in all_results["combined_search"]:
            status = "✓" if r["passed"] else "✗"
            print(
                f"  {status} {r['description']}: doc={r.get('top_result', 'N/A')[:30]}"
            )

        print("\n### Method Comparison ###")
        for r in all_results["method_comparison"]:
            print(f"  Query: {r['query']}")
            print(
                f"    Tree:   score={r['tree_score']:.1f}, top={r.get('tree_top', 'N/A')}"
            )
            print(
                f"    Vector: score={r['vector_score']:.1f}, top={r.get('vector_top', 'N/A')}"
            )
            print(
                f"    Hybrid: score={r['hybrid_score']:.1f}, top={r.get('hybrid_top', 'N/A')}"
            )

        # Save results
        output_dir = Path(__file__).parent.parent / "PageIndex"
        output_file = output_dir / "test_results.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(all_results, f, indent=2, ensure_ascii=False)
        print(f"\nResults saved to: {output_file}")

        return all_results


def main():
    tester = SearchAccuracyTester()
    results = tester.run_all_tests()

    # Calculate overall accuracy
    total_passed = (
        sum(1 for r in results["keyword_search"] if r["passed"])
        + sum(1 for r in results["code_search"] if r["passed"])
        + sum(1 for r in results["combined_search"] if r["passed"])
    )
    total_tests = (
        len(results["keyword_search"])
        + len(results["code_search"])
        + len(results["combined_search"])
    )

    print("\n" + "=" * 60)
    print(
        f"Overall Accuracy: {total_passed}/{total_tests} ({total_passed / total_tests * 100:.1f}%)"
    )
    print("=" * 60)


if __name__ == "__main__":
    main()
