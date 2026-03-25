---
created: 2026-03-25T02:00:38.280Z
title: Compare CPU vs GPU model performance for Windows Docker
area: tooling
files: []
---

## Problem

需要比較模型在 CPU 和 GPU 上的效能差異，並建立兩個 Windows Docker 版本以支援不同部署環境。目的是评估在无 GPU 的 Windows 环境下使用 CPU 运行的可行性。

## Solution

### 測試結果 (2026-03-25)

**系統配置:**
- CPU: 16 核心, 32 執行緒
- 記憶體: 47 GB
- GPU: 2x NVIDIA GeForce RTX 2080 Ti (22GB each)

**效能測試結果:**

| 模型 | 推理時間 | 吞吐量 | 相比 7b 加速 |
|------|----------|--------|--------------|
| qwen2.5:7b (GPU) | 2.34s | 7.24 tokens/s | 1.00x |
| qwen2.5:3b (GPU) | 1.26s | 7.98 tokens/s | 1.86x |
| qwen2.5:14b (GPU) | 5.28s | 2.87 tokens/s | 0.44x |

**結論:**
- qwen2.5:3b 是最快且性價比最高的選擇
- qwen2.5:14b 較慢，不建議用于 SOAP 生成
- CPU-only 測試需要透過 llama.cpp 直接實現（待續）

### 待辦事項
1. [x] 效能基準測試腳本建立 (`scripts/benchmark_ollama.py`)
2. [x] Ollama API 效能測試完成
3. [x] 測試結果記錄 (`benchmark_results.json`)
4. [x] Windows 部署腳本建立 (`scripts/deploy.bat`)
5. [x] 兩個 Docker 鏡像版本創建（CPU/GPU）
   - `docker-compose.cpu.yml` - CPU 版本
   - `docker-compose.gpu.yml` - GPU 版本