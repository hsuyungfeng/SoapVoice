#!/usr/bin/env python3
"""
Medical Service Item Workflow Integration
Integrates RAG search into medical service item processing
"""

import sys
import os
import json
import argparse
from pathlib import Path
from typing import List, Dict, Optional
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from optimized_hybrid_search import OptimizedHybridSearch


class MedicalServiceWorkflow:
    def __init__(
        self,
        tree_dir: str = None,
        doc_dir: str = None,
    ):
        base_dir = Path(__file__).parent.parent
        if tree_dir is None:
            tree_dir = str(base_dir / "PageIndex/results")
        if doc_dir is None:
            doc_dir = str(base_dir / "審查注意事項")

        self.searcher = OptimizedHybridSearch(tree_dir=tree_dir, doc_dir=doc_dir)
        self.cache_dir = base_dir / ".workflow_cache"
        self.cache_dir.mkdir(exist_ok=True)

    def lookup_payment_regulation(
        self, code: str = None, name: str = None, verbose: bool = False
    ) -> Dict:
        """
        Look up payment regulation for a medical service item

        Args:
            code: Medical service code (e.g., 48001C)
            name: Service name (e.g., 居家照護)
            verbose: Print detailed results

        Returns:
            Dict with regulation info and context
        """
        if not code and not name:
            return {"error": "Must provide code or name"}

        # Search
        if code:
            results = self.searcher.search_combined(query=name, code=code, top_k=5)
        else:
            results = self.searcher.search(name, top_k=5, method="hybrid")

        if not results:
            return {
                "found": False,
                "code": code,
                "name": name,
                "message": "No matching regulations found",
            }

        # Format results
        primary = results[0]
        context = self.searcher.generate_context(results, max_chars=1500)

        if verbose:
            print(f"\n=== Payment Regulation Lookup ===")
            print(f"Code: {code or 'N/A'}")
            print(f"Name: {name or 'N/A'}")
            print(f"Found in: {primary['doc_title']}")
            print(f"Section: {primary['title']}")
            print(f"Score: {primary['score']:.1f}")
            print(f"\n--- Relevant Content ---")
            print(context[:500] + "...")

        return {
            "found": True,
            "code": code,
            "name": name,
            "primary_doc": primary["doc_title"],
            "primary_section": primary["title"],
            "score": primary["score"],
            "context": context,
            "all_results": [
                {
                    "doc": r["doc_title"],
                    "section": r["title"],
                    "score": r["score"],
                }
                for r in results[:5]
            ],
        }

    def enrich_service_list(
        self,
        input_file: str,
        output_file: str = None,
        code_col: str = "代碼",
        name_col: str = "名稱",
        regulation_col: str = "支付規定",
    ) -> pd.DataFrame:
        """
        Enrich a list of medical service items with payment regulations

        Args:
            input_file: Path to input Excel/CSV file
            output_file: Path to output file (optional)
            code_col: Column name for service codes
            name_col: Column name for service names
            regulation_col: Column name for regulations

        Returns:
            Enriched DataFrame
        """
        print(f"Loading {input_file}...")

        # Load data
        if input_file.endswith(".csv"):
            df = pd.read_csv(input_file)
        else:
            df = pd.read_excel(input_file)

        print(f"Loaded {len(df)} rows")

        # Find code and name columns if not specified
        if code_col not in df.columns:
            for col in df.columns:
                if "code" in col.lower() or "代碼" in col or "項目" in col:
                    if df[col].dtype == object:
                        code_col = col
                        break

        if name_col not in df.columns:
            for col in df.columns:
                if "name" in col.lower() or "名稱" in col or "項目" in col:
                    name_col = col
                    break

        print(f"Using columns: code={code_col}, name={name_col}")

        # Add regulation column
        df[regulation_col] = ""
        df["規定來源"] = ""

        # Process each row
        for idx, row in df.iterrows():
            code = (
                str(row.get(code_col, "")).strip()
                if pd.notna(row.get(code_col))
                else None
            )
            name = (
                str(row.get(name_col, "")).strip()
                if pd.notna(row.get(name_col))
                else None
            )

            if code == "nan" or code == "None":
                code = None
            if name == "nan" or name == "None":
                name = None

            if not code and not name:
                continue

            if idx % 10 == 0:
                print(f"Processing row {idx + 1}/{len(df)}...")

            result = self.lookup_payment_regulation(code=code, name=name)

            if result.get("found"):
                df.at[idx, regulation_col] = result.get("context", "")[:500]
                df.at[idx, "規定來源"] = result.get("primary_doc", "")

        # Save output
        if output_file:
            if output_file.endswith(".csv"):
                df.to_csv(output_file, index=False, encoding="utf-8-sig")
            else:
                df.to_excel(output_file, index=False)
            print(f"Saved to {output_file}")

        return df

    def batch_lookup(self, items: List[Dict], output_file: str = None) -> List[Dict]:
        """
        Batch lookup for multiple service items

        Args:
            items: List of dicts with 'code' and/or 'name' keys
            output_file: Optional output file path

        Returns:
            List of results with regulations
        """
        results = []
        for i, item in enumerate(items):
            code = item.get("code")
            name = item.get("name")

            print(f"[{i + 1}/{len(items)}] Looking up: {code or name}")

            result = self.lookup_payment_regulation(code=code, name=name)
            result["item"] = item
            results.append(result)

        if output_file:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            print(f"Saved results to {output_file}")

        return results

    def interactive_lookup(self):
        """Interactive lookup mode"""
        print("\n=== Medical Service Payment Regulation Lookup ===")
        print("Enter medical code or service name to search")
        print("Type 'quit' or 'exit' to exit\n")

        while True:
            try:
                query = input("> ").strip()

                if query.lower() in ["quit", "exit", "q"]:
                    print("Goodbye!")
                    break

                if not query:
                    continue

                # Determine if it's a code or name
                import re

                is_code = bool(re.match(r"^[A-Z]?\d{4,7}[A-Z]?$", query, re.IGNORECASE))

                if is_code:
                    result = self.lookup_payment_regulation(code=query, verbose=True)
                else:
                    result = self.lookup_payment_regulation(name=query, verbose=True)

                if not result.get("found"):
                    print(f"\nNo regulations found for '{query}'")
                    print("Try a different search term or check the spelling\n")

            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"Error: {e}")


def main():
    parser = argparse.ArgumentParser(description="Medical Service Workflow Integration")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Lookup command
    lookup_parser = subparsers.add_parser("lookup", help="Single lookup")
    lookup_parser.add_argument("--code", "-c", help="Medical code")
    lookup_parser.add_argument("--name", "-n", help="Service name")
    lookup_parser.add_argument(
        "--verbose", "-v", action="store_true", help="Verbose output"
    )

    # Enrich command
    enrich_parser = subparsers.add_parser("enrich", help="Enrich Excel/CSV file")
    enrich_parser.add_argument("input", help="Input file")
    enrich_parser.add_argument("--output", "-o", help="Output file")
    enrich_parser.add_argument("--code-col", help="Code column name")
    enrich_parser.add_argument("--name-col", help="Name column name")

    # Batch command
    batch_parser = subparsers.add_parser("batch", help="Batch lookup from JSON")
    batch_parser.add_argument("input", help="Input JSON file")
    batch_parser.add_argument("--output", "-o", help="Output file")

    # Interactive command
    subparsers.add_parser("interactive", help="Interactive lookup mode")

    args = parser.parse_args()

    workflow = MedicalServiceWorkflow()

    if args.command == "lookup":
        result = workflow.lookup_payment_regulation(
            code=args.code, name=args.name, verbose=args.verbose
        )
        if result.get("found"):
            print(f"\nPrimary source: {result['primary_doc']}")
            print(f"Section: {result['primary_section']}")

    elif args.command == "enrich":
        df = workflow.enrich_service_list(
            input_file=args.input,
            output_file=args.output,
            code_col=args.code_col,
            name_col=args.name_col,
        )
        print(f"\nEnriched {len(df)} rows")

    elif args.command == "batch":
        with open(args.input, "r", encoding="utf-8") as f:
            items = json.load(f)
        results = workflow.batch_lookup(items, output_file=args.output)
        print(f"\nProcessed {len(results)} items")

    elif args.command == "interactive":
        workflow.interactive_lookup()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
