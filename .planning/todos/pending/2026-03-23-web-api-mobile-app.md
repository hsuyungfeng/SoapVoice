---
created: 2026-03-23T10:57:00.000Z
title: Web API for mobile app integration
area: api
files:
  - src/api/rest.py
  - src/main.py
---

## Problem

需要提供 Web API 供手機 App 調用
實現語音轉 SOAP 病歷的遠端服務

## Solution

1. 評估現有 API 端點：
   - `/clinical/normalize` - 術語標準化
   - `/icd10` - ICD-10 分類
   - `/soap/generate` - SOAP 生成

2. 新增 API 端點：
   - POST `/api/v1/transcribe` - 音頻轉文字
   - POST `/api/v1/process` - 完整流程（轉錄 + SOAP）
   - POST `/api/v1/symptom-extract` - 症狀提取
   - POST `/api/v1/icd-classify` - ICD 分類

3. API 设计：
   - RESTful 風格
   - 認證：API Key / JWT
   -  rate limiting
   - OpenAPI 文件

**Status:** 可選功能，取決於需求