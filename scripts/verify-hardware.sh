#!/bin/bash

# SoapVoice 硬體環境驗證腳本
# 驗證 GPU、RAM、儲存是否符合專案需求

set -e

# 輸出 JSON 格式結果
output_json() {
    local gpu_passed=$1
    local gpu_count=$2
    local gpu_total_vram=$3
    local ram_passed=$4
    local ram_total=$5
    local storage_passed=$6
    local storage_available=$7
    
    # 計算 overall passed
    local overall="true"
    if [ "$gpu_passed" != "true" ] || [ "$ram_passed" != "true" ] || [ "$storage_passed" != "true" ]; then
        overall="false"
    fi
    
    cat << EOF
{
  "success": $overall,
  "gpu": {
    "passed": $gpu_passed,
    "count": $gpu_count,
    "total_vram_gb": $gpu_total_vram,
    "required": 44,
    "message": "GPU 數量: $gpu_count, 總 VRAM: ${gpu_total_vram}GB"
  },
  "ram": {
    "passed": $ram_passed,
    "total_gb": $ram_total,
    "required": 48,
    "message": "總記憶體: ${ram_total}GB"
  },
  "storage": {
    "passed": $storage_passed,
    "available_gb": $storage_available,
    "required": 500,
    "message": "可用儲存空間: ${storage_available}GB"
  }
}
EOF
}

# 1. GPU 檢測
detect_gpu() {
    local gpu_count=0
    local total_vram_gb=0
    
    if command -v nvidia-smi &> /dev/null; then
        # 檢測 NVIDIA GPU 數量
        gpu_count=$(nvidia-smi --list-gpus | wc -l)
        
        # 計算總 VRAM
        if [ "$gpu_count" -gt 0 ]; then
            local vram_mb=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | awk '{sum+=$1} END {print sum}')
            total_vram_gb=$((vram_mb / 1024))
        fi
        
        if [ "$gpu_count" -ge 1 ] && [ "$total_vram_gb" -ge 44 ]; then
            echo "GPU: 通過 - 數量: $gpu_count, VRAM: ${total_vram_gb}GB"
            return 0
        else
            echo "GPU: 未通過 - 數量: $gpu_count, VRAM: ${total_vram_gb}GB (需要 ≥44GB)"
            return 1
        fi
    else
        echo "GPU: 未通過 - nvidia-smi 不可用"
        return 1
    fi
}

# 2. RAM 檢測
detect_ram() {
    local total_kb=0
    
    if [ -f /proc/meminfo ]; then
        total_kb=$(grep MemTotal /proc/meminfo | awk '{print $2}')
    elif command -v free &> /dev/null; then
        total_kb=$(free -b | grep Mem: | awk '{print $2}')
    else
        echo "RAM: 無法檢測"
        return 1
    fi
    
    local total_gb=$((total_kb / 1024 / 1024))
    
    if [ "$total_gb" -ge 48 ]; then
        echo "RAM: 通過 - ${total_gb}GB"
        return 0
    else
        echo "RAM: 未通過 - ${total_gb}GB (需要 ≥48GB)"
        return 1
    fi
}

# 3. 儲存檢測
detect_storage() {
    local available_kb=0
    local path="${1:-/}"
    
    if [ -d "$path" ]; then
        available_kb=$(df -B1 "$path" | awk 'NR==2 {print $4}')
        available_gb=$((available_kb / 1024 / 1024 / 1024))
        
        if [ "$available_gb" -ge 500 ]; then
            echo "儲存: 通過 - ${available_gb}GB 可用"
            return 0
        else
            echo "儲存: 未通過 - ${available_gb}GB 可用 (需要 ≥500GB)"
            return 1
        fi
    else
        echo "儲存: 路徑不存在: $path"
        return 1
    fi
}

# 主函數
main() {
    local gpu_passed="false"
    local ram_passed="false"
    local storage_passed="false"
    local gpu_count=0
    local gpu_total_vram=0
    local ram_total=0
    local storage_available=0
    
    # 檢測 GPU
    if command -v nvidia-smi &> /dev/null; then
        gpu_count=$(nvidia-smi --list-gpus | wc -l)
        if [ "$gpu_count" -gt 0 ]; then
            local vram_mb=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | awk '{sum+=$1} END {print sum}')
            gpu_total_vram=$((vram_mb / 1024))
            if [ "$gpu_total_vram" -ge 44 ]; then
                gpu_passed="true"
            fi
        fi
    fi
    
    # 檢測 RAM
    if [ -f /proc/meminfo ]; then
        local total_kb=$(grep MemTotal /proc/meminfo | awk '{print $2}')
        ram_total=$((total_kb / 1024 / 1024))
        if [ "$ram_total" -ge 48 ]; then
            ram_passed="true"
        fi
    fi
    
    # 檢測儲存
    local available_kb=$(df -B1 / | awk 'NR==2 {print $4}')
    storage_available=$((available_kb / 1024 / 1024 / 1024))
    if [ "$storage_available" -ge 500 ]; then
        storage_passed="true"
    fi
    
    # 輸出 JSON
    output_json "$gpu_passed" "$gpu_count" "$gpu_total_vram" "$ram_passed" "$ram_total" "$storage_passed" "$storage_available"
}

main "$@"
