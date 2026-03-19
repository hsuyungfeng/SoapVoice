# 🚀 SoapVoice 部署指南

**版本:** v1.0  
**日期:** 2026-03-13  
**適用環境:** Production (內網部署)

---

## 📋 部署前檢查清單

### 硬體需求

| 項目 | 最低需求 | 建議配置 |
|------|----------|----------|
| CPU | Ryzen 9 5950X (16C/32T) | Ryzen 9 7950X |
| RAM | 48GB | 64GB |
| GPU VRAM | 44GB (2x RTX 2080 Ti) | 48GB (2x RTX 3090) |
| SSD | 500GB | 1TB NVMe |
| 網路 | 1Gbps 內網 | 10Gbps 內網 |

### 軟體需求

- [ ] Ubuntu 24.04 LTS
- [ ] NVIDIA Driver ≥535
- [ ] CUDA 12.x
- [ ] Docker ≥24.0
- [ ] Docker Compose ≥2.20
- [ ] Ollama ≥0.1.0

### 模型需求

- [ ] qwen3.5:9b (6GB)
- [ ] qwen3.5:27b (17GB)
- [ ] glm-4.7-flash:latest (19GB)
- [ ] faster-whisper large-v3 (6GB)

---

## 🔧 部署步驟

### 步驟 1: 環境準備

```bash
# 1.1 更新系統
sudo apt update && sudo apt upgrade -y

# 1.2 安裝必要套件
sudo apt install -y curl git docker.io docker-compose

# 1.3 安裝 NVIDIA Container Toolkit
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt update
sudo apt install -y nvidia-container-toolkit
sudo systemctl restart docker

# 1.4 驗證 GPU
docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi
```

### 步驟 2: Ollama 安裝與模型下載

```bash
# 2.1 安裝 Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 2.2 啟動 Ollama 服務
sudo systemctl start ollama
sudo systemctl enable ollama

# 2.3 下載模型
ollama pull qwen3.5:9b
ollama pull qwen3.5:27b
ollama pull glm-4.7-flash:latest

# 2.4 驗證模型
ollama list
```

### 步驟 3: 應用程式部署

```bash
# 3.1 複製專案
cd /opt
git clone https://github.com/your-org/soapvoice.git
cd soapvoice

# 3.2 複製環境配置
cp .env.example .env

# 3.3 編輯環境配置
vim .env
# 修改以下配置:
# - JWT_SECRET_KEY=<強隨機字串>
# - DEFAULT_API_KEY=<強隨機字串>
# - CORS_ORIGINS=https://doctor-toolbox.com

# 3.4 產生 JWT Secret Key
openssl rand -hex 32

# 3.5 產生 API Key
openssl rand -base64 32
```

### 步驟 4: Docker 部署

```bash
# 4.1 建立網路
docker network create soapvoice-net

# 4.2 啟動服務 (生產環境)
docker compose -f docker-compose.prod.yml up -d

# 4.3 檢查服務狀態
docker compose ps

# 4.4 查看日誌
docker compose logs -f api
docker compose logs -f ollama
```

### 步驟 5: Nginx 配置

```bash
# 5.1 建立 Nginx 配置
sudo tee /etc/nginx/sites-available/soapvoice << 'EOF'
upstream soapvoice_api {
    least_conn;
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name soapvoice.local;

    location / {
        proxy_pass http://soapvoice_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /ws/ {
        proxy_pass http://soapvoice_api;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
EOF

# 5.2 啟用配置
sudo ln -s /etc/nginx/sites-available/soapvoice /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 步驟 6: SSL 配置 (選用)

```bash
# 6.1 安裝 Certbot
sudo apt install -y certbot python3-certbot-nginx

# 6.2 申請 SSL 證書
sudo certbot --nginx -d soapvoice.your-domain.com

# 6.3 自動續期
sudo crontab -e
# 加入：0 3 * * * certbot renew --quiet
```

---

## 🔍 監控與維護

### Prometheus + Grafana 監控

```bash
# 啟動監控服務
docker compose -f docker-compose.prod.yml --profile monitoring up -d

# 訪問 Grafana
# http://localhost:3000
# 預設帳號：admin / admin
```

### 日誌管理

```bash
# 查看 API 日誌
docker compose logs -f api

# 查看 Ollama 日誌
docker compose logs -f ollama

# 導出日誌
docker compose logs api > logs/api-$(date +%Y%m%d).log
```

### 備份策略

```bash
# 建立備份腳本
sudo tee /opt/soapvoice/scripts/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/var/backups/soapvoice"
DATE=$(date +%Y%m%d_%H%M%S)

# 備份資料庫
docker compose exec -T postgres pg_dump -U soapvoice > $BACKUP_DIR/db_$DATE.sql

# 備份配置文件
tar -czf $BACKUP_DIR/config_$DATE.tar.gz /opt/soapvoice/.env

# 清理舊備份 (保留 30 天)
find $BACKUP_DIR -name "*.sql" -mtime +30 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete
EOF

chmod +x /opt/soapvoice/scripts/backup.sh

# 設定定時備份
sudo crontab -e
# 加入：0 2 * * * /opt/soapvoice/scripts/backup.sh
```

---

## 🧪 部署驗證

### 健康檢查

```bash
# API 健康檢查
curl http://localhost:8000/health

# 臨床 NLP 健康檢查
curl http://localhost:8000/api/v1/clinical/health

# Ollama 服務檢查
curl http://localhost:11434/api/tags
```

### 功能測試

```bash
# 文本標準化測試
curl -X POST http://localhost:8000/api/v1/clinical/normalize \
  -H "Content-Type: application/json" \
  -d '{"text": "病人胸悶兩天還有點喘"}'

# ICD-10 分類測試
curl -X POST http://localhost:8000/api/v1/clinical/icd10 \
  -H "Content-Type: application/json" \
  -d '{"text": "病人胸悶，呼吸困難", "context": {"age": 45, "gender": "M"}}'
```

### 負載測試

```bash
# 使用 locust 進行負載測試
uv run locust -f scripts/load_test.py \
  --host=http://localhost:8000 \
  -u 50 \
  -r 10 \
  -t 60s
```

---

## 🔧 故障排除

### 問題 1: API 服務無法啟動

```bash
# 檢查日誌
docker compose logs api

# 檢查 GPU
nvidia-smi

# 重啟服務
docker compose restart api
```

### 問題 2: Ollama 模型載入失敗

```bash
# 檢查模型
ollama list

# 重新下載模型
ollama pull qwen3.5:9b

# 檢查 VRAM
nvidia-smi --query-gpu=memory.used,memory.total --format=csv
```

### 問題 3: Docker 容器崩潰

```bash
# 查看容器狀態
docker compose ps -a

# 查看崩潰日誌
docker compose logs --tail=100

# 重建容器
docker compose up -d --force-recreate
```

---

## 📞 支援管道

| 管道 | 聯絡方式 |
|------|----------|
| 技術文件 | /opt/soapvoice/docs/ |
| 問題追蹤 | GitHub Issues |
| 緊急聯絡 | tech@soapvoice.com |

---

**部署完成！** 🎉

下一步：
1. 執行醫師 beta 測試
2. 收集回饋並優化
3. 正式上線
