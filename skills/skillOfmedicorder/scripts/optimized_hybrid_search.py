#!/usr/bin/env python3
"""
Optimized Hybrid RAG Search with LLM-driven title recognition
Features:
- Enhanced scoring algorithm with multiple signals
- LLM-powered title extraction and validation
- Medical code detection
- Relevance ranking
- Persistent caching for performance
"""

import sys
import os
import json
import glob
import time
import re
import hashlib
import pickle
import numpy as np
import ollama
from pathlib import Path
from typing import List, Dict, Optional, Tuple


class SearchCache:
    """Persistent cache for search results"""

    def __init__(self, cache_dir: str = "./.search_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.memory_cache = {}
        self.max_memory_items = 100
        self.max_age_hours = 24

    def _get_cache_path(self, key: str) -> Path:
        """Get file path for cache key"""
        key_hash = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{key_hash}.pkl"

    def get(self, key: str) -> Optional[Dict]:
        """Get cached result"""
        # Check memory cache first
        if key in self.memory_cache:
            return self.memory_cache[key]

        # Check disk cache
        cache_path = self._get_cache_path(key)
        if cache_path.exists():
            try:
                age_hours = (time.time() - cache_path.stat().st_mtime) / 3600
                if age_hours < self.max_age_hours:
                    with open(cache_path, "rb") as f:
                        data = pickle.load(f)
                    # Also store in memory
                    if len(self.memory_cache) < self.max_memory_items:
                        self.memory_cache[key] = data
                    return data
                else:
                    cache_path.unlink(missing_ok=True)
            except Exception:
                pass

        return None

    def set(self, key: str, data: Dict):
        """Set cached result"""
        # Update memory cache
        self.memory_cache[key] = data
        if len(self.memory_cache) > self.max_memory_items:
            # Remove oldest item
            oldest = next(iter(self.memory_cache))
            del self.memory_cache[oldest]

        # Update disk cache
        cache_path = self._get_cache_path(key)
        try:
            with open(cache_path, "wb") as f:
                pickle.dump(data, f)
        except Exception as e:
            print(f"Cache write error: {e}")

    def clear(self):
        """Clear all caches"""
        self.memory_cache.clear()
        for cache_file in self.cache_dir.glob("*.pkl"):
            cache_file.unlink(missing_ok=True)

    def stats(self) -> Dict:
        """Get cache statistics"""
        disk_items = len(list(self.cache_dir.glob("*.pkl")))
        return {
            "memory_items": len(self.memory_cache),
            "disk_items": disk_items,
            "max_age_hours": self.max_age_hours,
        }


class OptimizedHybridSearch:
    def __init__(
        self,
        tree_dir: str = "./PageIndex/results",
        doc_dir: str = "./審查注意事項",
        cache_dir: str = None,
    ):
        self.tree_dir = tree_dir
        self.doc_dir = doc_dir
        self.trees = []
        self.embed_model = "nomic-embed-text:latest"
        self.llm_model = "qwen2.5:14b"

        # Initialize cache
        if cache_dir is None:
            cache_dir = os.path.join(os.path.dirname(__file__), ".search_cache")
        self.cache = SearchCache(cache_dir)

        self._load_trees()
        self._load_documents()

    def _load_trees(self):
        """Load all tree structures"""
        tree_files = glob.glob(os.path.join(self.tree_dir, "*_tree.json"))
        for tree_file in tree_files:
            try:
                with open(tree_file, "r", encoding="utf-8") as f:
                    tree = json.load(f)
                    self.trees.append(tree)
            except Exception as e:
                print(f"Error loading {tree_file}: {e}")
        print(f"Loaded {len(self.trees)} tree structures")

    def _load_documents(self):
        """Load raw documents for fallback"""
        self.documents = {}
        for root, _, files in os.walk(self.doc_dir):
            for f in files:
                if f.endswith((".pdf", ".docx", ".doc")):
                    path = os.path.join(root, f)
                    name = os.path.splitext(f)[0]
                    self.documents[name] = path
        print(f"Loaded {len(self.documents)} documents")

    def search(self, query: str, top_k: int = 5, method: str = "hybrid") -> List[Dict]:
        """Search using specified method with caching"""
        # Check cache for tree and hybrid methods (not for vector due to embedding variations)
        if method in ["tree", "hybrid"]:
            cache_key = f"search:{query}:{method}:{top_k}"
            cached = self.cache.get(cache_key)
            if cached:
                return cached

        if method == "tree":
            results = self._tree_search(query, top_k)
        elif method == "vector":
            results = self._vector_search(query, top_k)
        elif method == "llm":
            results = self._llm_enhanced_search(query, top_k)
        else:
            results = self._hybrid_search(query, top_k)

        # Cache results for appropriate methods
        if method in ["tree", "hybrid"] and results:
            cache_key = f"search:{query}:{method}:{top_k}"
            self.cache.set(cache_key, results)

        return results

    def _calculate_tree_score(
        self,
        title: str,
        text: str,
        query: str,
        query_lower: str,
        keywords: list,
        codes: list,
        synonyms: list = None,
    ) -> Tuple[float, list]:
        """
        Calculate tree-based relevance score with multiple signals
        Returns (score, matched_reasons)
        """
        score = 0.0
        matched = []

        title_lower = title.lower()
        text_lower = text.lower()

        # 1. Exact phrase match (highest weight)
        if query_lower in title_lower:
            score += 30
            matched.append("exact_title")
        elif query_lower in text_lower:
            score += 15
            matched.append("exact_content")

        # 2. Medical code match (highest priority)
        for code in codes:
            if code in title_lower:
                score += 50
                matched.append(f"code_title:{code}")
            elif code in text_lower:
                score += 30
                matched.append(f"code_text:{code}")

        # 3. Keyword match (secondary)
        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower in title_lower:
                score += 8
                matched.append(f"kw_title:{kw}")
            if kw_lower in text_lower:
                score += 3
                matched.append(f"kw_text:{kw}")

        # 3.5. Synonym expansion match
        if synonyms:
            for syn in synonyms:
                syn_lower = syn.lower()
                if syn_lower in title_lower:
                    score += 5  # Lower weight for synonyms
                    matched.append(f"synonym_title:{syn}")
                if syn_lower in text_lower:
                    score += 2
                    matched.append(f"synonym_text:{syn}")

        # 3.6. Fuzzy match for typos
        fuzzy_title = self._fuzzy_match(title_lower, query_lower)
        if fuzzy_title > 0.7:
            score += fuzzy_title * 10
            matched.append(f"fuzzy_title:{fuzzy_title:.2f}")

        fuzzy_text = self._fuzzy_match(text_lower[:500], query_lower)
        if fuzzy_text > 0.6:
            score += fuzzy_text * 5
            matched.append(f"fuzzy_text:{fuzzy_text:.2f}")

        # 4. Section header detection
        section_patterns = [
            r"第[一二三四五六七八九十零]+[章節部篇]",
            r"\([一二三四五六七八九十零]+\)",
            r"^\d+\.",
            r"^[甲乙丙丁戊己庚辛壬癸]+、",
        ]
        for pattern in section_patterns:
            if re.search(pattern, title):
                score += 5
                matched.append("section_header")
                break

        # 5. Title quality score
        title_length = len(title)
        if 4 <= title_length <= 30:
            score += 3
            matched.append("good_title_length")

        # 6. Content density (keyword density in text)
        query_words = query_lower.split()
        all_terms = query_words + (synonyms if synonyms else [])
        if all_terms and text:
            density = (
                sum(text_lower.count(w.lower()) for w in all_terms if len(w) > 1)
                / len(text)
                * 1000
            )
            score += min(density, 10)  # Cap at 10
            if density > 1:
                matched.append("high_density")

        return score, matched

    def _tree_search(self, query: str, top_k: int = 5) -> List[Dict]:
        """Tree-based search with optimized scoring and synonym expansion"""
        query_lower = query.lower()
        keywords = self._extract_keywords(query)
        codes = self._extract_medical_codes(query)
        synonyms = self._expand_synonyms(query)

        results = []
        for tree in self.trees:
            doc_title = tree.get("title", "")
            nodes = tree.get("nodes", [])

            for node in nodes:
                title = node.get("title", "")
                text = node.get("text", "")
                start_index = node.get("start_index", 0)

                score, matched = self._calculate_tree_score(
                    title, text, query, query_lower, keywords, codes, synonyms
                )

                if score > 0:
                    results.append(
                        {
                            "score": score,
                            "title": title,
                            "doc_title": doc_title,
                            "page": start_index,
                            "text": text[:500],
                            "matched": list(set(matched))[:5],
                            "method": "tree",
                        }
                    )

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def _vector_search(self, query: str, top_k: int = 5) -> List[Dict]:
        """Vector-based semantic search"""
        try:
            query_embedding = ollama.embeddings(
                model=self.embed_model, prompt=query[:500]
            )["embedding"]
        except Exception as e:
            print(f"Embedding error: {e}")
            return []

        results = []
        for tree in self.trees:
            doc_title = tree.get("title", "")
            nodes = tree.get("nodes", [])

            for node in nodes:
                title = node.get("title", "")
                text = node.get("text", "")

                if not text:
                    continue

                try:
                    node_embedding = ollama.embeddings(
                        model=self.embed_model, prompt=text[:500]
                    )["embedding"]

                    similarity = self._cosine_similarity(
                        query_embedding, node_embedding
                    )

                    if similarity > 0.25:  # Lowered threshold
                        results.append(
                            {
                                "score": similarity * 100,
                                "title": title,
                                "doc_title": doc_title,
                                "page": node.get("start_index", 0),
                                "text": text[:500],
                                "matched": ["semantic"],
                                "method": "vector",
                            }
                        )
                except Exception as e:
                    continue

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def _llm_enhanced_search(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        LLM-enhanced search with intelligent title recognition
        Uses LLM to identify relevant sections based on query intent
        """
        # First get tree search results
        tree_results = self._tree_search(query, top_k * 3)

        if not tree_results:
            return []

        # Use LLM to re-rank based on semantic relevance
        ranked_results = self._llm_rerank(query, tree_results, top_k)
        return ranked_results

    def _llm_rerank(self, query: str, candidates: List[Dict], top_k: int) -> List[Dict]:
        """Use LLM to re-rank search results"""
        if not candidates:
            return []

        # Prepare context for LLM
        context = f"Query: {query}\n\nCandidates:\n"
        for i, r in enumerate(candidates[:10]):
            context += f"{i + 1}. Doc: {r['doc_title']}, Section: {r['title']}\n"
            context += f"   Content: {r['text'][:200]}...\n\n"

        prompt = f"""Given a query and candidate search results, rank them by relevance.

{context}

Rank the candidates by how well they answer the query. Consider:
1. Direct mention of key terms
2. Logical relevance to the query intent
3. Content quality and completeness

Output ONLY a JSON array of indices in ranked order:
[1, 3, 2, 5, 4, ...]

Most relevant first."""

        try:
            response = ollama.chat(
                model=self.llm_model,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.1, "num_ctx": 2048, "num_predict": 256},
            )
            content = response["message"]["content"].strip()

            # Parse rankings
            rankings = json.loads(content)

            # Re-rank
            reranked = []
            for idx in rankings[:top_k]:
                if 0 < idx <= len(candidates):
                    r = candidates[idx - 1].copy()
                    r["llm_ranked"] = True
                    reranked.append(r)

            return reranked
        except Exception as e:
            print(f"LLM rerank error: {e}")
            return candidates[:top_k]

    def _llm_extract_titles(self, text: str, max_items: int = 10) -> List[Dict]:
        """
        Use LLM to extract structured titles from raw text
        Returns list of {"structure": "1.1", "title": "...", "page": 1}
        """
        prompt = f"""Extract section titles from this document text.
Output ONLY valid JSON array:
[
    {{"s": "1", "t": "Section Title", "p": 1}},
    ...
]

Text (first 2000 chars):
{text[:2000]}

Output ONLY the JSON array."""

        try:
            response = ollama.chat(
                model=self.llm_model,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.0, "num_ctx": 2048, "num_predict": 512},
            )
            content = response["message"]["content"].strip()

            # Clean JSON
            content = re.sub(r"```json\s*", "", content)
            content = re.sub(r"```\s*", "", content)
            content = content.strip()

            result = json.loads(content)
            return result[:max_items]
        except Exception as e:
            print(f"LLM title extraction error: {e}")
            return []

    def _hybrid_search(self, query: str, top_k: int = 5) -> List[Dict]:
        """Enhanced hybrid search combining multiple signals"""
        tree_results = self._tree_search(query, top_k * 3)
        vector_results = self._vector_search(query, top_k * 3)

        # Normalize scores to same scale
        max_tree = max((r["score"] for r in tree_results), default=1)
        max_vector = max((r["score"] for r in vector_results), default=1)

        seen = {}

        # Process tree results
        for r in tree_results:
            key = f"{r['doc_title']}:{r['title']}"
            normalized_score = (r["score"] / max_tree) * 50  # 0-50 scale
            r["tree_score"] = normalized_score
            r["vector_score"] = 0
            r["combined_score"] = normalized_score * 1.2  # Slight boost for tree
            r["final_score"] = r["combined_score"]
            seen[key] = r

        # Process vector results
        for r in vector_results:
            key = f"{r['doc_title']}:{r['title']}"
            normalized_score = (r["score"] / max_vector) * 50  # 0-50 scale
            if key in seen:
                seen[key]["vector_score"] = normalized_score
                seen[key]["combined_score"] += normalized_score
                seen[key]["final_score"] = seen[key]["combined_score"] / 2
                seen[key]["matched"].extend(r["matched"])
            else:
                r["tree_score"] = 0
                r["vector_score"] = normalized_score
                r["combined_score"] = normalized_score
                r["final_score"] = normalized_score
                seen[key] = r

        # Sort by final score
        results = list(seen.values())
        results.sort(key=lambda x: x["final_score"], reverse=True)
        return results[:top_k]

    def search_by_code(self, code: str, top_k: int = 5) -> List[Dict]:
        """Optimized medical code search with caching"""
        # Check cache
        cache_key = f"code:{code}:{top_k}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached

        results = []
        code_lower = code.lower()

        for tree in self.trees:
            doc_title = tree.get("title", "")
            nodes = tree.get("nodes", [])

            for node in nodes:
                title = node.get("title", "")
                text = node.get("text", "")

                # Check for code in various formats
                code_formats = [
                    code,
                    code.lower(),
                    code.upper(),
                    f"({code})",
                    f"({code})",
                ]

                found = False
                for fmt in code_formats:
                    if fmt in text or fmt in title:
                        found = True
                        break

                if found:
                    snippet = self._extract_snippet(text, code)

                    # Smart scoring
                    score = 50
                    if code in title:
                        score += 40
                    if code in snippet[:200]:  # Code near start
                        score += 10

                    # Check for payment info near code
                    payment_patterns = [r"點", r"支付", r"健保", r"给付"]
                    for pat in payment_patterns:
                        if re.search(pat, snippet[:500]):
                            score += 5
                            break

                    results.append(
                        {
                            "score": score,
                            "code": code,
                            "title": title,
                            "doc_title": doc_title,
                            "page": node.get("start_index", 0),
                            "text": snippet,
                            "method": "code_search",
                        }
                    )

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def search_combined(
        self, query: str = None, code: str = None, top_k: int = 5
    ) -> List[Dict]:
        """
        Combined search - search by both query and code
        Returns unified results with relevance scoring
        """
        all_results = []
        seen_keys = set()

        # Search by code first (highest priority)
        if code:
            code_results = self.search_by_code(code, top_k=top_k)
            for r in code_results:
                key = f"{r['doc_title']}:{r['title']}"
                if key not in seen_keys:
                    all_results.append(r)
                    seen_keys.add(key)

        # Search by query
        if query:
            query_results = self._hybrid_search(query, top_k=top_k)
            for r in query_results:
                key = f"{r['doc_title']}:{r['title']}"
                if key not in seen_keys:
                    r["query_search"] = True
                    all_results.append(r)
                    seen_keys.add(key)

        # Re-sort combined results
        all_results.sort(key=lambda x: x["score"], reverse=True)
        return all_results[:top_k]

    def _extract_keywords(self, text: str) -> list:
        """Extract keywords from query"""
        patterns = [
            r"全民健康保險",
            r"西醫",
            r"中醫",
            r"牙醫",
            r"改善方案",
            r"[\(\)（）]",
            r"[0-9]+",
        ]
        result = text
        for p in patterns:
            result = re.sub(p, " ", result)

        words = re.findall(r"[\u4e00-\u9fff]{2,}|[\w]{3,}", result)
        return words

    def _extract_medical_codes(self, text: str) -> list:
        """Extract medical procedure codes"""
        patterns = [
            r"[A-Z]\d{4,6}[A-Z]?",  # e.g., 48001C, A1234B
            r"\d{5,7}[A-Z]?",  # e.g., 48001C
            r"[A-Z]{2,}\d+",  # e.g., DRG123
            r"[A-Z]\d{3}[A-Z]?",  # e.g., A123B
            r"[A-Z]{2}\d{4}",  # e.g., AB1234
        ]
        codes = []
        for p in patterns:
            codes.extend(re.findall(p, text))
        return codes

    def _expand_synonyms(self, query: str) -> List[str]:
        """
        Expand query with synonyms and related terms for medical domain
        """
        synonyms = {
            "巡迴醫療": ["居家", "照護", "門診", "山地", "離島"],
            "居家照護": ["居家", "護理", "照護", "在宅"],
            "手術": ["處置", "治療", "手術費"],
            "檢查": ["檢驗", "化驗", "篩檢"],
            "注射": ["施打", "打針", "針劑"],
            "牙醫": ["牙科", "齒科", "牙齒"],
            "眼科": ["眼睛", "視力", "眼科"],
            "精神科": ["心理", "精神", "心智"],
            "安寧": ["末期", "緩和", "安寧療護"],
            "住院": ["病房", "入院", "病床"],
            "急診": ["緊急", "急迫"],
            "復健": ["復健科", "物理治療", "職能治療"],
            "中醫": ["傳統醫學", "針灸", "中藥"],
            "藥品": ["藥物", "藥費", "用藥"],
            "材料": ["衛材", "敷料", "器械"],
        }

        expanded = [query]
        for key, values in synonyms.items():
            if key in query or query in key:
                expanded.extend(values)

        return list(set(expanded))

    def _fuzzy_match(self, text: str, query: str, threshold: float = 0.8) -> float:
        """
        Simple fuzzy matching for Chinese text
        Returns similarity score 0-1
        """
        text_lower = text.lower()
        query_lower = query.lower()

        # Direct substring check
        if query_lower in text_lower:
            return 1.0

        # Character-level similarity
        common = 0
        for char in query_lower:
            if char in text_lower:
                common += 1

        return common / len(query_lower) if query_lower else 0

    def _cosine_similarity(self, a, b):
        """Calculate cosine similarity"""
        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0
        return dot_product / (norm_a * norm_b)

    def _extract_snippet(self, text: str, code: str, context: int = 300) -> str:
        """Extract snippet around code with context"""
        idx = text.lower().find(code.lower())
        if idx == -1:
            return text[:500]

        start = max(0, idx - context)
        end = min(len(text), idx + len(code) + context)

        snippet = text[start:end]
        if start > 0:
            snippet = "..." + snippet
        if end < len(text):
            snippet = snippet + "..."

        return snippet

    def generate_context(self, results: List[Dict], max_chars: int = 3000) -> str:
        """Generate context string from search results"""
        context_parts = []
        total_chars = 0

        for r in results:
            part = f"[{r['doc_title']}] {r['title']}\n{r['text'][:500]}\n"
            if total_chars + len(part) > max_chars:
                break
            context_parts.append(part)
            total_chars += len(part)

        return "\n---\n".join(context_parts)


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python optimized_hybrid_search.py <query>")
        print(
            "  python optimized_hybrid_search.py <query> --method tree|vector|hybrid|llm"
        )
        print("  python optimized_hybrid_search.py --code 48001C")
        print("  python optimized_hybrid_search.py --combined 居家照護 --code 48001C")
        sys.exit(1)

    # Parse arguments
    query = None
    code = None
    method = "hybrid"
    top_k = 5

    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == "--code":
            code = sys.argv[i + 1] if i + 1 < len(sys.argv) else ""
            i += 2
        elif sys.argv[i] == "--method":
            method = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--top":
            top_k = int(sys.argv[i + 1])
            i += 2
        elif sys.argv[i] == "--combined":
            query = sys.argv[i + 1] if i + 1 < len(sys.argv) else ""
            code = (
                sys.argv[i + 2]
                if i + 2 < len(sys.argv) and not sys.argv[i + 2].startswith("--")
                else None
            )
            if code:
                i += 3
            else:
                i += 2
        else:
            query = sys.argv[i]
            i += 1

    # Initialize searcher
    base_dir = Path(__file__).parent.parent
    searcher = OptimizedHybridSearch(
        tree_dir=str(base_dir / "PageIndex/results"),
        doc_dir=str(base_dir / "審查注意事項"),
    )

    print(f"Query: {query or 'N/A'}")
    print(f"Code: {code or 'N/A'}")
    print(f"Method: {method}")
    print("=" * 60)

    if code and query:
        results = searcher.search_combined(query=query, code=code, top_k=top_k)
    elif code:
        results = searcher.search_by_code(code, top_k=top_k)
    else:
        results = searcher.search(query, top_k=top_k, method=method)

    print(f"\nFound {len(results)} results:\n")

    for i, r in enumerate(results, 1):
        print(f"{i}. Score: {r['score']:.1f}")
        print(f"   Doc: {r['doc_title']}")
        print(f"   Section: {r['title']}")
        print(f"   Page: {r.get('page', 'N/A')}")
        if "code" in r:
            print(f"   Code: {r['code']}")
        print(f"   Method: {r.get('method', 'unknown')}")
        print(f"   Matched: {', '.join(r.get('matched', [])[:3])}")
        print(f"   Text: {r['text'][:150]}...")
        print()


if __name__ == "__main__":
    main()
