# SoapVoice 專案 Roadmap

**版本:** v0.1.0  
**創建日期:** 2026-02-26  
**深度:** Standard (5-8 phases)

---

## 階段總覽

- [x] **Phase 1: 專案基礎設施** - 硬體、軟體、开發環境就緒
- [ ] **Phase 2: AI 模型部署** - ASR 與 LLM 推理引擎運行
- [ ] **Phase 3: 醫療 NLP 引擎** - 術語標準化與 SOAP 分類
- [ ] **Phase 4: API 閘道與輸出** - REST/WebSocket API + SOAP 結構化輸出
- [ ] **Phase 5: 前端整合** - doctor-toolbox.com 整合
- [ ] **Phase 6: 測試與優化** - 完整測試覆蓋與效能優化
- [ ] **Phase 7: 部署上線** - 生產環境部署與監控

---

## 階段詳情

### Phase 1: 專案基礎設施

**目標:** 所有基礎設施就緒，開發環境可用

**依賴:** 無 (首個階段)

**需求:** SETUP-01, SETUP-02, SETUP-03, SETUP-04, SETUP-05

**成功標準** (what must be TRUE):
1. 硬體環境通過驗證 (GPU 可檢測、RAM ≥48GB、SSD ≥500GB)
2. NVIDIA 驅動與 CUDA 12.1+ 正確安裝並驗證
3. uv + Python 3.11 環境可運作
4. Docker 與 Docker Compose 可正常運行
5. Git repository 已設定並可追蹤版本

**Plans:** 3/3 plans complete

**Plan list:**
- [x] 01-01-PLAN.md — 硬體環境驗證腳本 (完成: 2026-03-02)
- [x] 01-02-PLAN.md — GPU/CUDA 與 Python 環境 (完成: 2026-03-02)
- [x] 01-03-PLAN.md — Docker 與 Git 配置 (完成: 2026-03-02)

---

### Phase 2: AI 模型部署

**目標:** 所有 AI 模型可獨立運行並通過基準測試

**依賴:** Phase 1

**需求:** ASR-01, ASR-02, ASR-03, ASR-04, LLM-01, LLM-02, LLM-03

**成功標準** (what must be TRUE):
1. Faster-Whisper large-v3 可進行語音辨識 (WER <5%)
2. 醫療詞彙可正確辨識 (自定義詞彙注入生效)
3. WebSocket 串流 pipeline 可即時回傳轉文字結果
4. GLM-4.7-Flash 可透過 vLLM 進行推理
5. 推理延遲目標達成 (<2s @ 95th percentile)

**Plans:** 4/4 plans

**Plan list:**
- [ ] 02-01-PLAN.md — Faster-Whisper large-v3 部署
- [ ] 02-02-PLAN.md — 醫療詞彙優化
- [ ] 02-03-PLAN.md — WebSocket 即時串流
- [ ] 02-04-PLAN.md — GLM-4.7-Flash 推理引擎

---

### Phase 3: 醫療 NLP 引擎

**目標:** 醫療語意標準化引擎可運作，術語轉換準確率達標

**依賴:** Phase 2

**需求:** NLP-01, NLP-02, NLP-03, NLP-04, NLP-05

**成功標準** (what must be TRUE):
1. 錯字自動修正常見醫療術語錯誤 (準確率 ≥95%)
2. 醫療術語標準化可將中文口語轉為專業英文 (準確率 ≥95%)
3. SOAP 分類可正確識別 S/O/A/P 區塊 (準確率 ≥90%)
4. ICD-10 代碼映射可針對常見症狀給出建議代碼
5. 專科分類可針對症狀組合建議專科

**Plans:** TBD

---

### Phase 4: API 閘道與輸出

**目標:** API 閘道、生認證、SOAP 結構化輸出

**依賴:** Phase 3

**需求:** API-01, API-02, API-03, API-04, API-05, API-06, SOAP-01, SOAP-02, SOAP-03

**成功標準** (what must be TRUE):
1. FastAPI REST endpoints 可處理臨床標準化請求
2. WebSocket 端點可支援即時語音串流
3. API Key 認證可阻擋未授權請求
4. Rate limiting 可防止滥用 (100 req/min)
5. OpenAPI/Swagger 文件可正常存取
6. SOAP 輸出為結構化 JSON 格式
7. 繁體中文對話摘要可正確生成

**Plans:** TBD

---

### Phase 5: 前端整合

**目標:** doctor-toolbox.com 可正常整合語音轉 SOAP 功能

**依賴:** Phase 4

**需求:** FRONT-01, FRONT-02, FRONT-03, FRONT-04

**成功標準** (what must be TRUE):
1. 前端可呼叫後端 API 進行語音處理
2. 語音錄製 UI 可正常運作 (一鍵開始/停止)
3. 即時轉文字結果可在 UI 上顯示
4. SOAP 編輯器可讓醫師手動調整輸出

**Plans:** TBD

---

### Phase 6: 測試與優化

**目標:** 測試通過、效能達標、安全無虞

**依賴:** Phase 5

**需求:** TEST-01, TEST-02, TEST-03, TEST-04

**成功標準** (what must be TRUE):
1. 單元測試覆蓋率 ≥80%
2. 整合測試覆蓋率 ≥70%
3. 負載測試可承受 100+ 並發請求
4. 醫療準確率驗證通過 (≥95%)
5. 端到端延遲 <3s (90th percentile)
6. 安全測試無 critical 問題

**Plans:** TBD

---

### Phase 7: 部署上線

**目標:** 生產環境可用、監控就緒

**依賴:** Phase 6

**需求:** DEPLOY-01, DEPLOY-02, DEPLOY-03, DEPLOY-04

**成功標準** (what must be TRUE):
1. Docker Compose 可一键啟動所有服務
2. Nginx 反向代理正確設定 (內網 192.168.x.x)
3. Prometheus + Grafana 監控儀表板可運作
4. 健康檢查端點回傳正確狀態
5. 系統可用性 ≥99.5%

**Plans:** TBD

---

## 進度表

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. 專案基礎設施 | 3/3 | Complete    | 2026-03-02 |
| 2. AI 模型部署 | 0/4 | Not started | - |
| 3. 醫療 NLP 引擎 | 0/5 | Not started | - |
| 4. API 閘道與輸出 | 0/9 | Not started | - |
| 5. 前端整合 | 0/4 | Not started | - |
| 6. 測試與優化 | 0/4 | Not started | - |
| 7. 部署上線 | 0/4 | Not started | - |

---

## 覆蓋率

**總需求:** 38 個
**已映射:** 38 個 (100%)
**P0 需求:** 34 個
**P1 需求:** 4 個 (NLP-04, NLP-05, API-06, LLM-02)

---

## 備註

- 本 roadmap 基於 OpnusPlan.md v0.1.0 衍生的需求
- 階段順序遵循自然依賴關係
- 成功標準採用 goal-backward 方式從用戶視角定義
