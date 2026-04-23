# GPU + LLM 基準測試指南

## 概述

此基準測試將在 **RTX 2080 Ti (22GB VRAM)** 上全面測試 SoapVoice 的效能，包括：

1. **ASR 測試** (Faster-Whisper Medium @ CUDA)
   - 8 個醫療語音樣本
   - 測量：延遲時間、實時因子 (RTF)、轉錄品質

2. **LLM 測試** (6 個模型對比)
   - Gemma 4 E4B (Q4_K_M GGUF, 5.1GB)
   - Qwen 3.6:Latest (Ollama)
   - Qwen 3.5:35B (Ollama)
   - Gemma 4:31B (Ollama)
   - Gemma 4:26B (Ollama)
   - Gemma 4:E4B (Ollama)
   
   - 測量：SOAP 生成耗時、Token/秒、SOAP 品質

3. **輸出**：`benchmarks/GPUllmcompare.md`

---

## 前置條件

### 1. 環境變數設定

確保 `.env` 已配置 GPU：

```bash
WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=float16
LLAMA_N_GPU_LAYERS=-1
USE_LLAMA_CPP=true
LLAMA_MODEL_PATH=models/gemma-4-E4B-it-Q4_K_M.gguf
```

### 2. llama-cpp-python 編譯（CUDA 支援）

```bash
cd /home/hsu/Desktop/SoapVoice

# 確保 CUDA 12.2 + CUDA Toolkit 已安裝
export CUDA_PATH=/usr/local/cuda

# 編譯 llama-cpp-python with CUDA
CMAKE_ARGS="-DGGML_CUDA=on" pip install llama-cpp-python --upgrade --force-reinstall --no-cache-dir
```

驗證：
```bash
python -c "import llama_cpp; print(llama_cpp.GGML_CUDA)"  # 應該輸出 True
```

### 3. Ollama 設定（Qwen 和 Gemma 模型）

```bash
# 確保 Ollama 運行在 localhost:11434
ollama serve &

# 拉取測試模型（若未安裝）
ollama pull qwen3.6:latest
ollama pull qwen3.5:35b
ollama pull gemma4:31b
ollama pull gemma4:26b
ollama pull gemma4:e4b

# 驗證
curl http://localhost:11434/api/tags | jq .models
```

### 4. 專案依賴

```bash
cd /home/hsu/Desktop/SoapVoice
uv sync
```

---

## 執行基準測試

### 方法 A：完整自動化測試（推薦）

```bash
cd /home/hsu/Desktop/SoapVoice
python scripts/gpu_llm_benchmark.py
```

**預期耗時**：
- ASR 測試：~5-10 分鐘（8 個音檔）
- LLM 測試（6 個模型）：~30-60 分鐘
- **總耗時**：40-70 分鐘

### 方法 B：分步驟測試

若想分開測試或調試，修改 `gpu_llm_benchmark.py` 中的 `LLM_MODELS` 列表，只保留要測試的模型：

```python
# 只測試 Gemma 4 E4B
LLM_MODELS = [
    {
        "name": "Gemma 4 E4B (Q4_K_M, 5.1GB GGUF)",
        "type": "llama_cpp",
        "model_path": "models/gemma-4-E4B-it-Q4_K_M.gguf",
        "n_gpu_layers": -1,
    },
]
```

然後執行：
```bash
python scripts/gpu_llm_benchmark.py
```

---

## 監控 GPU 使用情況

在另一個終端實時監控：

```bash
# 監控 NVIDIA GPU
watch -n 1 nvidia-smi

# 或單次查看
nvidia-smi dmon
```

預期：
- **Gemma 4 E4B**: ~15-18 GB VRAM
- **Qwen 3.5:35B**: ~20-22 GB VRAM（可能需要 CPU offload）
- **ASR + LLM 同時運行**: 最多 22 GB

---

## 結果解讀

測試完成後會生成 `benchmarks/GPUllmcompare.md`，包含：

### 1. ASR 效能表

| 指標 | 說明 |
|------|------|
| **RTF** | Real-Time Factor（1.0 = 實時，< 1 = 超實時） |
| **ASR 耗時** | 音檔轉文字時間 |
| **轉錄字數** | 識別的漢字數 |

範例：
```
chest_pain.wav: 30.5s → 3.2s (RTF: 0.105) → 適合臨床使用
```

### 2. LLM 效能表

| 指標 | 說明 |
|------|------|
| **SOAP 耗時** | SOAP 生成時間 |
| **Token/秒** | 每秒生成的 token 數（越高越好） |
| **總耗時** | 所有測試檔案的累計時間 |

範例：
```
Gemma 4 E4B: 8.5s, 328 tokens → 38.6 token/秒
Qwen 3.5:35B: 12.2s, 412 tokens → 33.8 token/秒
```

### 3. 效能排名

最快的模型排在前面，方便選擇：

```
1. Gemma 4 E4B: 38.6 token/秒 ✅ 推薦
2. Qwen 3.6:Latest: 35.2 token/秒
3. Qwen 3.5:35B: 33.8 token/秒
...
```

### 4. SOAP 品質評估

手動查看樣本 SOAP，評估醫學準確性、結構化程度等。

---

## 常見問題

### Q: 「CUDA out of memory」

**A**: 模型超過 22GB。解決方案：
1. 減少 `n_gpu_layers`（部分層 offload 至 CPU）
2. 使用量化版本（Q4、Q5）
3. 測試更小的模型（Gemma 4:26B 而非 35B）

```python
# 修改 n_gpu_layers
{
    "name": "Qwen 3.5:35B (Partial GPU)",
    "type": "ollama",
    "model_id": "qwen3.5:35b",
    "n_gpu_layers": 50,  # 不是 -1（全部），而是 50（一半）
}
```

### Q: 「Ollama 連接失敗」

**A**: 確保 Ollama 運行：
```bash
ollama serve &  # 後台啟動
curl http://localhost:11434/api/tags  # 驗證連接
```

### Q: 「模型未下載」

**A**: 手動拉取：
```bash
ollama pull qwen3.5:35b
ollama pull gemma4:31b
# 等待完成...
```

### Q: 「Whisper 超時」

**A**: 調整超時時間（編輯 `gpu_llm_benchmark.py`）：
```python
segments, info = self.asr_model.transcribe(
    str(audio_path),
    language="zh",
    patience=2.0  # 預設 1.0，增加以容忍較長音檔
)
```

---

## 進階自訂

### 修改測試音檔列表

編輯 `gpu_llm_benchmark.py`：

```python
TEST_AUDIO_FILES = [
    "chest_pain.wav",
    "respiratory.wav",
    # 加入自己的音檔...
]
```

### 修改 SOAP 提示詞

編輯 `_build_soap_prompt` 方法：

```python
def _build_soap_prompt(self, transcript: str, context: str = "") -> str:
    return f"""你是醫療記錄員。根據患者諮詢記錄生成繁體中文結構化 SOAP 記錄。

患者描述：
{transcript}

...
"""
```

### 新增自訂模型

```python
LLM_MODELS.append({
    "name": "My Custom Model",
    "type": "llama_cpp",
    "model_path": "models/my-model.gguf",
    "n_gpu_layers": -1,
})
```

---

## 預期結果（參考）

**RTX 2080 Ti 22GB 上的預期效能**：

| 模型 | 類型 | SOAP 耗時 | Token/秒 | VRAM |
|------|------|---------|---------|------|
| Gemma 4 E4B | GGUF | 8-12s | 35-40 | 5GB |
| Qwen 3.6 | Ollama | 10-15s | 30-35 | 12GB |
| Qwen 3.5:35B | Ollama | 12-18s | 25-30 | 22GB |
| Gemma 4:31B | Ollama | 11-16s | 28-33 | 20GB |

**ASR** (Faster-Whisper Medium):
- RTF: 0.05-0.10 (實時的 5-10 倍快速)
- 1 分鐘音檔: 3-5 秒

---

## 報告生成

測試完成後自動生成：

```
/home/hsu/Desktop/SoapVoice/benchmarks/GPUllmcompare.md
```

查看報告：
```bash
cat /home/hsu/Desktop/SoapVoice/benchmarks/GPUllmcompare.md
```

或用 Markdown 閱讀器打開。

---

## 支援

若測試失敗，收集日誌：

```bash
python scripts/gpu_llm_benchmark.py 2>&1 | tee benchmark.log
```

提供 `benchmark.log` 以協助調試。

---

**祝測試順利！** 🚀
