# 效能優化指南

## 效能目標

| 指標 | 目標 | 現況 |
|------|------|------|
| ASR 延遲 | <500ms | - |
| LLM 推理 | <2s | - |
| API 回應 | <3s | - |
| 吞吐量 | ≥50 req/s | - |

---

## 優化策略

### 1. 模型優化

#### 1.1 Ollama 模型配置

```bash
# 使用較小的模型進行快速推理
ollama pull qwen3.5:27b  # 27B 參數版本
ollama pull glm-4.7-flash:latest  # 快速推理
```

#### 1.2 模型參數調整

```yaml
# config/models.yaml
llm:
  model: "qwen3.5:35b"  # 主模型
  fallback_models:
    - "qwen3.5:27b"  # 較小模型
    - "glm-4.7-flash"  # 快速模型
  num_ctx: 4096  # 減少上下文長度
  num_gpu: 1  # 使用單一 GPU
```

### 2. 快取優化

#### 2.1 Redis 快取

```python
# 使用 Redis 快取常見查詢
import redis

redis_client = redis.Redis(host='localhost', port=6379, db=0)

# 快取醫療術語映射
def get_cached_term(term):
    cached = redis_client.get(f"term:{term}")
    if cached:
        return cached.decode('utf-8')
    # 查詢資料庫並快取
    result = lookup_term(term)
    redis_client.setex(f"term:{term}", 3600, result)
    return result
```

#### 2.2 LRU Cache

```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def classify_soap_category(text: str) -> str:
    """SOAP 分類快取"""
    return classifier.classify(text).category
```

### 3. 資料庫優化

#### 3.1 索引優化

```sql
-- ICD-10 代碼索引
CREATE INDEX idx_icd10_code ON icd10_codes (code);
CREATE INDEX idx_icd10_category ON icd10_codes (category);

-- 醫療術語索引
CREATE INDEX idx_term_category ON medical_terms (category);
CREATE INDEX idx_term_original ON medical_terms (original_text);
```

#### 3.2 查詢優化

```python
# 使用批次查詢代替多次單筆查詢
def get_terms_batch(terms: List[str]) -> List[TermMapping]:
    placeholders = ','.join('?' * len(terms))
    cursor.execute(
        f"SELECT * FROM medical_terms WHERE original_text IN ({placeholders})",
        terms
    )
    return cursor.fetchall()
```

### 4. API 優化

#### 4.1 非同步處理

```python
from fastapi import BackgroundTasks

@app.post("/api/v1/clinical/soap/generate")
async def generate_soap(
    request: SOAPGenerateRequest,
    background_tasks: BackgroundTasks
):
    # 非同步處理耗時操作
    background_tasks.add_task(log_request, request)
    return await soap_generator.generate(request)
```

#### 4.2 回應壓縮

```python
from fastapi.middleware.gzip import GZipMiddleware

app.add_middleware(GZipMiddleware, minimum_size=1000)
```

### 5. 負載平衡

#### 5.1 多實例部署

```yaml
# docker-compose.prod.yml
services:
  api:
    deploy:
      replicas: 3
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
```

#### 5.2 Nginx 負載平衡

```nginx
upstream soapvoice_api {
    least_conn;
    server api1:8000;
    server api2:8000;
    server api3:8000;
}

server {
    location /api/ {
        proxy_pass http://soapvoice_api;
    }
}
```

### 6. 監控與分析

#### 6.1 Prometheus 指標

```python
from prometheus_client import Counter, Histogram

# 定義指標
REQUEST_COUNT = Counter('api_requests_total', 'Total API requests')
REQUEST_LATENCY = Histogram('api_request_latency_seconds', 'API request latency')

# 記錄指標
@REQUEST_LATENCY.time()
def process_request():
    pass
```

#### 6.2 效能分析

```bash
# 使用 cProfile 分析效能
python -m cProfile -o output.prof src/main.py

# 使用 snakeviz 查看結果
uv run snakeviz output.prof
```

---

## 效能測試

### 基準測試

```bash
# 使用 locust 進行負載測試
uv run locust -f scripts/load_test.py \
    --host=http://localhost:8000 \
    -u 100 \
    -r 10 \
    -t 60s
```

### 效能回歸測試

```bash
# 執行效能測試並比較結果
uv run pytest tests/test_performance.py --benchmark
```

---

## 常見問題排查

### 問題 1: LLM 推理過慢

**可能原因:**
- 模型過大
- GPU 記憶體不足
- 上下文過長

**解決方案:**
1. 使用較小的模型 (qwen3.5:27b)
2. 減少 num_ctx 參數
3. 啟用 GPU 加速

### 問題 2: API 回應延遲高

**可能原因:**
- 資料庫查詢慢
- 網路延遲
- 資源競爭

**解決方案:**
1. 優化資料庫查詢
2. 啟用快取
3. 增加實例數量

### 問題 3: 記憶體洩漏

**可能原因:**
- 未釋放的資源
- 快取無限制增長

**解決方案:**
1. 使用 context manager
2. 設置 LRU cache 上限
3. 定期重啟服務

---

## 效能檢查清單

- [ ] 模型參數已優化
- [ ] Redis 快取已啟用
- [ ] 資料庫索引已建立
- [ ] API 非同步處理
- [ ] 回應壓縮已啟用
- [ ] 負載平衡已配置
- [ ] 監控指標已設置
- [ ] 效能測試已執行
