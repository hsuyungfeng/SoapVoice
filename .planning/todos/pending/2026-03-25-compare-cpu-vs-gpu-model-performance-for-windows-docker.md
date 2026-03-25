---
created: 2026-03-25T02:00:38.280Z
title: Compare CPU vs GPU model performance for Windows Docker
area: tooling
files: []
---

## Problem

需要比較模型在 CPU 和 GPU 上的效能差異，並建立兩個 Windows Docker 版本以支援不同部署環境。目的是评估在无 GPU 的 Windows 环境下使用 CPU 运行的可行性。

## Solution

TBD - 需要：
1. 建立效能基准测试脚本（CPU vs GPU）
2. 创建两个 Docker 镜像版本
3. 配置 CPU-only 模式（使用 llama.cpp CPU 推理）
4. 记录测试结果（延迟、吞吐量、资源使用）
5. 编写 Windows 部署脚本