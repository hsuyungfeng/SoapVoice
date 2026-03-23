#!/usr/bin/env python3
"""
FastAPI REST API for Hybrid RAG Search
Provides REST endpoints for medical document search
"""

import sys
import os
import hashlib
import json
import time
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime, timedelta

import uvicorn
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))
from optimized_hybrid_search import OptimizedHybridSearch

# Initialize FastAPI app
app = FastAPI(
    title="醫療審查注意事項搜尋 API",
    description="提供醫療服務給付項目的樹狀結構搜尋 API",
    version="1.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize searcher
BASE_DIR = Path(__file__).parent.parent
SEARCHER = OptimizedHybridSearch(
    tree_dir=str(BASE_DIR / "PageIndex/results"),
    doc_dir=str(BASE_DIR / "審查注意事項"),
)


# Request/Response models
class SearchRequest(BaseModel):
    query: Optional[str] = None
    code: Optional[str] = None
    method: str = "hybrid"
    top_k: int = 5


class SearchResult(BaseModel):
    score: float
    title: str
    doc_title: str
    page: int
    text: str
    matched: List[str]
    method: str
    code: Optional[str] = None


class SearchResponse(BaseModel):
    query: str
    code: Optional[str]
    method: str
    total_results: int
    results: List[Dict]
    cached: bool = False
    processing_time_ms: float


class HealthResponse(BaseModel):
    status: str
    trees_loaded: int
    documents_loaded: int
    uptime_seconds: float


# Simple in-memory cache
class SearchCache:
    def __init__(self, max_age_seconds: int = 3600):
        self.cache: Dict[str, tuple] = {}
        self.max_age = max_age_seconds

    def _make_key(self, query: str, code: str, method: str, top_k: int) -> str:
        key = f"{query}:{code}:{method}:{top_k}"
        return hashlib.md5(key.encode()).hexdigest()

    def get(self, query: str, code: str, method: str, top_k: int) -> Optional[Dict]:
        key = self._make_key(query, code, method, top_k)
        if key in self.cache:
            data, timestamp = self.cache[key]
            if time.time() - timestamp < self.max_age:
                return data
            else:
                del self.cache[key]
        return None

    def set(self, query: str, code: str, method: str, top_k: int, data: Dict):
        key = self._make_key(query, code, method, top_k)
        self.cache[key] = (data, time.time())

    def clear(self):
        self.cache.clear()

    def stats(self) -> Dict:
        return {
            "total_entries": len(self.cache),
            "max_age_seconds": self.max_age,
        }


# Global cache instance
SEARCH_CACHE = SearchCache(max_age_seconds=3600)
START_TIME = time.time()


@app.get("/", response_model=Dict)
async def root():
    """API root endpoint"""
    return {
        "name": "醫療審查注意事項搜尋 API",
        "version": "1.0.0",
        "endpoints": {
            "search": "/search?query=關鍵詞",
            "code_search": "/code/48001C",
            "combined": "/combined?query=關鍵詞&code=48001C",
            "health": "/health",
        },
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        trees_loaded=len(SEARCHER.trees),
        documents_loaded=len(SEARCHER.documents),
        uptime_seconds=time.time() - START_TIME,
    )


@app.get("/search", response_model=SearchResponse)
async def search(
    query: str = Query(..., description="搜尋關鍵詞"),
    method: str = Query("hybrid", description="搜尋方法: tree, vector, hybrid"),
    top_k: int = Query(5, ge=1, le=20, description="返回結果數量"),
) -> SearchResponse:
    """
    搜尋醫療文件

    - **query**: 搜尋關鍵詞
    - **method**: 搜尋方法 (tree/vector/hybrid)
    - **top_k**: 返回結果數量 (1-20)
    """
    start_time = time.time()

    # Check cache
    cached = SEARCH_CACHE.get(query, None, method, top_k)
    if cached:
        return SearchResponse(
            query=query,
            code=None,
            method=method,
            total_results=len(cached["results"]),
            results=cached["results"],
            cached=True,
            processing_time_ms=(time.time() - start_time) * 1000,
        )

    # Perform search
    try:
        results = SEARCHER.search(query, top_k=top_k, method=method)

        # Format results
        formatted_results = []
        for r in results:
            formatted_results.append(
                {
                    "score": round(r.get("score", 0), 2),
                    "title": r.get("title", ""),
                    "doc_title": r.get("doc_title", ""),
                    "page": r.get("page", 0),
                    "text": r.get("text", "")[:500],
                    "matched": r.get("matched", [])[:3],
                    "method": r.get("method", ""),
                }
            )

        # Cache results
        SEARCH_CACHE.set(query, None, method, top_k, {"results": formatted_results})

        return SearchResponse(
            query=query,
            code=None,
            method=method,
            total_results=len(formatted_results),
            results=formatted_results,
            cached=False,
            processing_time_ms=(time.time() - start_time) * 1000,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/code/{code}", response_model=SearchResponse)
async def search_by_code(
    code: str,
    top_k: int = Query(5, ge=1, le=20, description="返回結果數量"),
) -> SearchResponse:
    """
    根據醫療代碼搜尋

    - **code**: 醫療服務代碼
    - **top_k**: 返回結果數量 (1-20)
    """
    start_time = time.time()

    # Check cache
    cached = SEARCH_CACHE.get("", code, "code", top_k)
    if cached:
        return SearchResponse(
            query="",
            code=code,
            method="code",
            total_results=len(cached["results"]),
            results=cached["results"],
            cached=True,
            processing_time_ms=(time.time() - start_time) * 1000,
        )

    try:
        results = SEARCHER.search_by_code(code, top_k=top_k)

        formatted_results = []
        for r in results:
            formatted_results.append(
                {
                    "score": round(r.get("score", 0), 2),
                    "title": r.get("title", ""),
                    "doc_title": r.get("doc_title", ""),
                    "page": r.get("page", 0),
                    "text": r.get("text", "")[:500],
                    "matched": r.get("matched", [])[:3],
                    "method": "code_search",
                    "code": code,
                }
            )

        # Cache results
        SEARCH_CACHE.set("", code, "code", top_k, {"results": formatted_results})

        return SearchResponse(
            query="",
            code=code,
            method="code",
            total_results=len(formatted_results),
            results=formatted_results,
            cached=False,
            processing_time_ms=(time.time() - start_time) * 1000,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/combined", response_model=SearchResponse)
async def combined_search(
    query: str = Query(None, description="搜尋關鍵詞"),
    code: str = Query(None, description="醫療代碼"),
    top_k: int = Query(5, ge=1, le=20, description="返回結果數量"),
) -> SearchResponse:
    """
    組合搜尋（關鍵詞 + 代碼）

    - **query**: 搜尋關鍵詞
    - **code**: 醫療服務代碼
    - **top_k**: 返回結果數量 (1-20)
    """
    start_time = time.time()

    if not query and not code:
        raise HTTPException(status_code=400, detail="必須提供 query 或 code")

    # Check cache
    cache_key = f"{query}:{code}"
    cached = SEARCH_CACHE.get(cache_key, "", "combined", top_k)
    if cached:
        return SearchResponse(
            query=query or "",
            code=code or None,
            method="combined",
            total_results=len(cached["results"]),
            results=cached["results"],
            cached=True,
            processing_time_ms=(time.time() - start_time) * 1000,
        )

    try:
        results = SEARCHER.search_combined(
            query=query or None,
            code=code or None,
            top_k=top_k,
        )

        formatted_results = []
        for r in results:
            formatted_results.append(
                {
                    "score": round(r.get("score", 0), 2),
                    "title": r.get("title", ""),
                    "doc_title": r.get("doc_title", ""),
                    "page": r.get("page", 0),
                    "text": r.get("text", "")[:500],
                    "matched": r.get("matched", [])[:3],
                    "method": r.get("method", "combined"),
                    "code": code,
                }
            )

        # Cache results
        SEARCH_CACHE.set(
            cache_key, "", "combined", top_k, {"results": formatted_results}
        )

        return SearchResponse(
            query=query or "",
            code=code or None,
            method="combined",
            total_results=len(formatted_results),
            results=formatted_results,
            cached=False,
            processing_time_ms=(time.time() - start_time) * 1000,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/context")
async def get_context(
    query: str = Query(..., description="搜尋關鍵詞"),
    code: str = Query(None, description="醫療代碼"),
    max_chars: int = Query(2000, ge=100, le=10000, description="最大字元數"),
) -> Dict:
    """
    取得搜尋結果的合併上下文

    - **query**: 搜尋關鍵詞
    - **code**: 醫療服務代碼
    - **max_chars**: 最大字元數 (100-10000)
    """
    try:
        results = SEARCHER.search_combined(
            query=query,
            code=code,
            top_k=5,
        )

        context = SEARCHER.generate_context(results, max_chars=max_chars)

        return {
            "query": query,
            "code": code,
            "context": context,
            "num_results": len(results),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/cache/clear")
async def clear_cache():
    """清除搜尋快取"""
    SEARCH_CACHE.clear()
    return {"message": "快取已清除", "stats": SEARCH_CACHE.stats()}


@app.get("/cache/stats")
async def cache_stats():
    """取得快取統計"""
    return SEARCH_CACHE.stats()


def main():
    """Run the API server"""
    print("=" * 60)
    print("醫療審查注意事項搜尋 API")
    print("=" * 60)
    print(f"Tree structures loaded: {len(SEARCHER.trees)}")
    print(f"Documents loaded: {len(SEARCHER.documents)}")
    print()
    print("API Endpoints:")
    print("  GET /search?query=居家照護&method=hybrid&top_k=5")
    print("  GET /code/48001C?top_k=5")
    print("  GET /combined?query=手術&code=48001C&top_k=5")
    print("  GET /health")
    print()
    print("Starting server on http://0.0.0.0:8000")

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
