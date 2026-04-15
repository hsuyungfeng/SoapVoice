#!/usr/bin/env python3
"""
SoapVoice Offline Server
使用 llama.cpp + GGUF 模型，完全離線運行
"""

import argparse
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_MODELS = {
    "qwen2.5-7b": "models/Qwen2.5-7B-Instruct-Q4_K_M.gguf",
    "qwen2.5-3b": "models/qwen2.5-3b-instruct-q4_k_m.gguf",
}


def get_model_path(model_name: str) -> Path:
    """取得模型路徑"""
    if model_name in DEFAULT_MODELS:
        return Path(DEFAULT_MODELS[model_name])
    return Path(model_name)


def check_models():
    """檢查可用模型"""
    print("=== 可用 GGUF 模型 ===")
    models_dir = Path("models")

    gguf_files = list(models_dir.glob("*.gguf"))
    if gguf_files:
        for f in gguf_files:
            size_mb = f.stat().st_size / 1024 / 1024
            print(f"  {f.name} ({size_mb:.1f} MB)")
    else:
        print("  無 GGUF 模型檔案")

    return gguf_files


def run_server(model: str, port: int = 8080, context: int = 2048, threads: int = 8):
    """使用 llama-cpp-python 啟動伺服器"""
    from src.llm.llama_engine import LlamaConfig, LlamaEngine

    model_path = get_model_path(model)
    if not model_path.exists():
        logger.error(f"模型檔案不存在: {model_path}")
        sys.exit(1)

    logger.info(f"啟動伺服器 with {model_path.name}")
    logger.info(f"Port: {port}, Context: {context}, Threads: {threads}")

    config = LlamaConfig(
        model_path=str(model_path),
        n_ctx=context,
        n_threads=threads,
        n_gpu_layers=0,  # CPU only
        max_tokens=512,
        temperature=0.3,
    )

    engine = LlamaEngine(config)
    engine.initialize()

    logger.info("LLM 引擎初始化完成")
    logger.info(f"伺服器就緒，可處理請求")

    # 簡易互動測試
    while True:
        try:
            user_input = input("\n輸入文字 (輸入 'quit' 離開): ").strip()
            if user_input.lower() in ["quit", "exit", "q"]:
                break

            if user_input:
                result = engine.generate(user_input, max_tokens=200)
                print(f"\n回應: {result[:500]}")
        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"Error: {e}")

    logger.info("伺服器停止")


def run_cli(model: str, text: str):
    """單次 SOAP 生成"""
    from src.llm.llama_engine import LlamaConfig, LlamaEngine
    from src.nlp.terminology_mapper import MedicalTerminologyMapper

    model_path = get_model_path(model)
    if not model_path.exists():
        logger.error(f"模型檔案不存在: {model_path}")
        sys.exit(1)

    logger.info(f"載入模型: {model_path.name}")

    config = LlamaConfig(
        model_path=str(model_path),
        n_ctx=512,
        n_threads=8,
        n_gpu_layers=0,
        max_tokens=256,
    )

    engine = LlamaEngine(config)
    engine.initialize()

    # 術語標準化
    mapper = MedicalTerminologyMapper()
    _, mappings = mapper.map_text(text)
    term_list = ", ".join([m.standard for m in mappings])

    # 生成 SOAP
    prompt = f"""Convert to SOAP format (English):
Patient: {text}
Terms: {term_list}
S: chest tightness
O: no specific findings
A: R07.89
P: follow-up"""

    result = engine.generate(prompt)
    print(f"\n=== SOAP 病歷 ({model_path.name}) ===")
    print(result[:500])


def main():
    parser = argparse.ArgumentParser(description="SoapVoice Offline Server")
    parser.add_argument("--check", action="store_true", help="檢查可用模型")
    parser.add_argument("--model", "-m", default="qwen2.5-7b", help="選擇模型")
    parser.add_argument("--port", "-p", type=int, default=8080, help="伺服器連接埠")
    parser.add_argument("--text", "-t", help="直接輸入文字生成 SOAP")
    parser.add_argument("--context", "-c", type=int, default=2048, help="Context 大小")
    parser.add_argument("--threads", type=int, default=8, help="執行緒數")

    args = parser.parse_args()

    if args.check:
        check_models()
    elif args.text:
        run_cli(args.model, args.text)
    else:
        run_server(args.model, args.port, args.context, args.threads)


if __name__ == "__main__":
    main()
