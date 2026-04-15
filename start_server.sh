#!/bin/bash
cd "$(dirname "$0")"
export USE_LLAMA_CPP=true
uv run uvicorn src.main:app --host 0.0.0.0 --port 8010 --log-level info 2>&1