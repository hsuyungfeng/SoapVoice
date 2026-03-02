# SoapVoice 專案狀態

**版本:** v0.1.0  
**更新日期:** 2026-03-02

---

## 項目參考

**項目名稱:** SoapVoice - 醫療語音轉 SOAP 病歷系統

**核心價值:**
- 減少 60-80% 病歷撰寫時間
- 標準化醫療術語
- 本地部署保護患者隱私

**當前焦點:** Phase 2: AI 模型部署

---

## 當前位置

**階段:** Phase 2: AI 模型部署
**計劃:** 02-02
**狀態:** Complete

**進度條:** ██████░░░ 2/4 plans complete

---

## 效能指標

| 指標 | 目標值 | 當前值 | 狀態 |
|------|--------|--------|------|
| ASR 詞錯率 (WER) | <5% | - | Pending |
| 醫療術語準確率 | ≥95% | - | Pending |
| SOAP 分類準確率 | ≥92% | - | Pending |
| 端到端延遲 | <3s | - | Pending |
| 系統可用性 | ≥99.5% | - | Pending |

---

## 累積上下文

### 已做決定

1. **技術選型:** FastAPI + Faster-Whisper + Qwen3-32B + GLM-4.7-Flash
2. **部署策略:** Docker Compose + Nginx 內網部署
3. **認證方式:** API Key + JWT
4. **依賴管理:** uv (Python)
5. **GPU 分配:** GPU0: Qwen3-32B, GPU1: Whisper large-v3
6. **GPU 環境:** CUDA 12.2 + NVIDIA Driver 535.288.01
7. **開發環境:** uv + Python 3.13 虛擬環境
8. **ASR 引擎:** Faster-Whisper large-v3 (CTranslate2 加速)
9. **語音辨識:** 支援中英文自動偵測
10. **詞彙優化:** MedicalVocabulary 類 + 2294 詞彙庫

### 待辦事項

- [x] 完成 Phase 1: 專案基礎設施
- [ ] 完成 Phase 2: AI 模型部署
- [ ] 完成 Phase 3: 醫療 NLP 引擎
- [ ] 完成 Phase 4: API 閘道與輸出
- [ ] 完成 Phase 5: 前端整合
- [ ] 完成 Phase 6: 測試與優化
- [ ] 完成 Phase 7: 部署上線

### 阻擋項目

無 (項目初始階段)

---

## 會話連續性

**文檔參考:**
- `.planning/PROJECT.md` - 核心價值
- `.planning/REQUIREMENTS.md` - 需求規格
- `.planning/ROADMAP.md` - 階段規劃
- `.planning/STATE.md` - 當前狀態
- `OpnusPlan.md` - 詳細執行計劃
- `clinic-promot.md` - 技術規格與系統提示

**相關文件:**
- `DailyProgress.md` - 每日進度追蹤
