---
created: 2026-03-24T10:24:06.573Z
title: 前端整合與開發測試網頁整合麥克風收音
area: ui
files:
  - src/api/websocket.py:234
---

## Problem

需要建立網頁前端介面，整合麥克風收音功能，讓使用者可以透過瀏覽器錄製語音並轉換為 SOAP 病歷。目前已有 WebSocket 串流轉錄功能（src/api/websocket.py:234），但缺少前端網頁介面。

## Solution

TBD - 需要評估技術選項：
1. Web Audio API + MediaRecorder
2. 現有 WebSocket 串流架構整合
3. 前端框架選擇（React/Vue/原生 HTML）
