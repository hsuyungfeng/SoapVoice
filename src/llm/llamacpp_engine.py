"""
使用 llama-cpp-python 載入本地 GGUF 模型進行推論
用於離線環境，不需要 Ollama
"""

import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent
MODELS_DIR = PROJECT_ROOT / "models"


@dataclass
class LlamaCppConfig:
    """LLM 配置"""

    model_path: str
    n_ctx: int = 4096
    n_threads: int = 4
    temperature: float = 0.3
    max_tokens: int = 512


class LlamaCppEngine:
    """使用 llama-cpp-python 的 LLM 引擎"""

    def __init__(self, config: LlamaCppConfig):
        self.config = config
        self._model = None
        self._load_model()

    def _load_model(self):
        """載入模型"""
        try:
            from llama_cpp import Llama

            logger.info(f"載入模型: {self.config.model_path}")
            self._model = Llama(
                model_path=self.config.model_path,
                n_ctx=self.config.n_ctx,
                n_threads=self.config.n_threads,
                temperature=self.config.temperature,
                verbose=False,
            )
            logger.info("模型載入成功")
        except Exception as e:
            logger.error(f"模型載入失敗: {e}")
            self._model = None

    def generate(self, prompt: str, max_tokens: Optional[int] = None) -> str:
        """生成文字

        Args:
            prompt: 輸入提示詞
            max_tokens: 最大生成 token 數

        Returns:
            生成的文字
        """
        if not self._model:
            return ""

        try:
            output = self._model(
                prompt,
                max_tokens=max_tokens or self.config.max_tokens,
                temperature=self.config.temperature,
                stop=["S:", "O:", "A:", "P:"],
            )
            return output["choices"][0]["text"].strip()
        except Exception as e:
            logger.error(f"生成失敗: {e}")
            return ""

    def generate_soap(self, transcript: str) -> Dict[str, Any]:
        """生成 SOAP 病歷

        Args:
            transcript: 醫療對話記錄

        Returns:
            SOAP 字典
        """
        prompt = f"""你是一個醫療病歷助手。請根據以下醫療對話生成 SOAP 病歷。

對話：{transcript}

請嚴格按照以下格式輸出：
S: [主訴]
O: [客觀檢查]
A: [評估/診斷]
P: [計畫]

"""

        response = self.generate(prompt)
        return self._parse_soap(response, transcript)

    def _parse_soap(self, response: str, transcript: str) -> Dict[str, Any]:
        """解析 SOAP 回應"""
        soap = {
            "subjective": "",
            "objective": "",
            "assessment": "",
            "plan": "",
            "raw_response": response,
        }

        lines = response.strip().split("\n")
        current_section = None

        for line in lines:
            line = line.strip()
            if line.startswith("S:"):
                current_section = "subjective"
            elif line.startswith("O:"):
                current_section = "objective"
            elif line.startswith("A:"):
                current_section = "assessment"
            elif line.startswith("P:"):
                current_section = "plan"
            elif current_section:
                soap[current_section] += line + "\n"

        for key in soap:
            soap[key] = soap[key].strip()

        return soap


def get_default_engine() -> Optional[LlamaCppEngine]:
    """取得預設引擎"""
    model_path = MODELS_DIR / "qwen2.5-7b-instruct-q4_k_m.gguf"

    if not model_path.exists():
        logger.warning(f"模型不存在: {model_path}")
        return None

    config = LlamaCppConfig(
        model_path=str(model_path),
        n_ctx=4096,
        n_threads=4,
        temperature=0.3,
        max_tokens=512,
    )

    return LlamaCppEngine(config)


def test_generation():
    """測試生成"""
    engine = get_default_engine()
    if not engine:
        print("無法載入模型")
        return

    transcript = "患者主訴心悸、胸悶兩個禮拜，晚上睡不好覺，有時呼吸喘。"

    result = engine.generate_soap(transcript)
    print("SOAP 結果:")
    print(f"S: {result.get('subjective', '')}")
    print(f"O: {result.get('objective', '')}")
    print(f"A: {result.get('assessment', '')}")
    print(f"P: {result.get('plan', '')}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_generation()
