import logging
import json
import time
import os

import numpy as np

# 初始化標誌
HAS_MSS = False
HAS_EASYOCR = False
HAS_PYTESSERACT = False
HAS_TESSERACT = False
HAS_OLLAMA_VISION = False

# 嘗試導入 mss
try:
    import mss

    HAS_MSS = True
except ImportError:
    mss = None

# 嘗試導入 easyocr
try:
    import easyocr

    HAS_EASYOCR = True
except ImportError:
    easyocr = None

# 嘗試導入 pytesseract
try:
    import pytesseract

    HAS_PYTESSERACT = True
except ImportError:
    pytesseract = None

# 嘗試導入 tesseract
try:
    import tesseract

    HAS_TESSERACT = True
except ImportError:
    tesseract = None

# 嘗試導入 requests (用於 Ollama API)
try:
    import requests

    HAS_OLLAMA_VISION = True
except ImportError:
    requests = None

logger = logging.getLogger(__name__)


class OCRParser:
    def __init__(self, vision_model: str = "glm-ocr"):
        self.reader = None
        self.vision_model = vision_model
        self.ollama_url = "http://localhost:11434/api/generate"
        self.vision_models = ["glm-ocr", "gemma4:e2b", "gemma4:e4b", "qwen3-vl:4b"]
        # 複製全域標誌到實例
        self.HAS_MSS = HAS_MSS
        self.HAS_EASYOCR = HAS_EASYOCR
        self.HAS_PYTESSERACT = HAS_PYTESSERACT
        self.HAS_TESSERACT = HAS_TESSERACT
        self.HAS_OLLAMA_VISION = HAS_OLLAMA_VISION

        # 如果使用 llama.cpp 則禁用需要網路/下載的 OCR 方法（全離線模式）
        use_llama_cpp = os.getenv("USE_LLAMA_CPP", "false").lower() == "true"
        if use_llama_cpp:
            self.HAS_OLLAMA_VISION = False
            self.HAS_EASYOCR = False  # EasyOCR 需要下載模型，不符合全離線需求
            logging.getLogger(__name__).info(
                f"離線模式啟用: 禁用 Ollama Vision 與 EasyOCR，使用 Tesseract 主力 OCR"
            )

    def _get_reader(self):
        if self.reader is None:
            if self.HAS_EASYOCR:
                try:
                    logger.info("初始化 EasyOCR (首次可能需下載模型)...")
                    # 支援繁體中文與英文
                    self.reader = easyocr.Reader(["ch_tra", "en"], gpu=False)
                except Exception as e:
                    logger.warning(f"EasyOCR 初始化失敗: {e}")
                    self.reader = None
            else:
                logger.warning("EasyOCR 未安裝，將使用備用方案")
                self.reader = None
        return self.reader

    def capture_screen_to_text(self) -> str:
        """擷取主螢幕並轉為純文字"""
        logger.info("擷取主螢幕畫面...")

        # 檢查截圖套件
        if not self.HAS_MSS:
            logger.error("mss 套件未安裝，無法截圖")
            return ""

        try:
            with mss.mss() as sct:
                # 擷取第 1 個螢幕 (主螢幕)
                if len(sct.monitors) < 2:
                    logger.error("沒有可用的螢幕監視器")
                    return ""

                monitor = sct.monitors[1]
                screenshot = sct.grab(monitor)

                if screenshot is None:
                    logger.error("截圖失敗，返回 None")
                    return ""

                # 檢查截圖尺寸
                if screenshot.width == 0 or screenshot.height == 0:
                    logger.error(f"截圖尺寸無效: {screenshot.width}x{screenshot.height}")
                    return ""

                # 轉成 numpy array
                img_np = np.array(screenshot)

                # 檢查 numpy array 是否有效
                if img_np is None or img_np.size == 0:
                    logger.error("numpy array 轉換失敗或為空")
                    return ""

                logger.debug(
                    f"截圖成功，尺寸: {screenshot.width}x{screenshot.height}, numpy shape: {img_np.shape}, dtype: {img_np.dtype}"
                )

                # 如果影像太大，縮小以節省記憶體並加速 OCR
                scale_factor = 0.5  # 縮小一半
                if img_np.shape[0] > 1920 or img_np.shape[1] > 1920:
                    try:
                        from PIL import Image

                        # 將 numpy array 轉為 PIL Image
                        if img_np.shape[2] == 4:  # RGBA 轉 RGB
                            img_pil = Image.fromarray(img_np, mode="RGBA").convert("RGB")
                        else:
                            img_pil = Image.fromarray(img_np)

                        new_width = int(img_pil.width * scale_factor)
                        new_height = int(img_pil.height * scale_factor)
                        img_pil = img_pil.resize((new_width, new_height), Image.Resampling.LANCZOS)

                        # 轉回 numpy array
                        img_np = np.array(img_pil)
                        logger.debug(
                            f"影像已縮小至: {new_width}x{new_height}, 新 shape: {img_np.shape}"
                        )
                    except Exception as e:
                        logger.warning(f"影像縮小失敗，使用原尺寸: {e}")

                # 嘗試多種 OCR 方案
                text = self._try_ocr_methods(img_np)
                return text

        except Exception as e:
            logger.error(f"OCR 截圖轉換失敗: {e}")
            import traceback

            logger.error(traceback.format_exc())
            return ""

    def _try_ocr_methods(self, image_np):
        """嘗試多種 OCR 方法（按照 AGENTS.md 的優先順序）"""
        # 方法 1: pytesseract（主力 OCR 引擎，全離線）
        if self.HAS_PYTESSERACT:
            try:
                logger.info("嘗試使用 pytesseract (主力 OCR)...")
                # 轉換為 PIL Image
                from PIL import Image

                img_pil = Image.fromarray(image_np)
                text = pytesseract.image_to_string(img_pil, lang="chi_tra+eng")
                if text.strip():
                    logger.info(f"pytesseract 成功，文字長度: {len(text)}")
                    return text
                else:
                    logger.warning("pytesseract 返回空文字，嘗試備援方案")
            except Exception as e:
                logger.warning(f"pytesseract 失敗: {e}")

        # 方法 2: Ollama Vision Model（備援，僅當未禁用時）
        if self.HAS_OLLAMA_VISION:
            for model in self.vision_models:
                try:
                    logger.info(f"嘗試使用 Ollama Vision ({model}) 備援...")
                    text = self._ocr_with_ollama_vision(image_np, model)
                    if text and len(text.strip()) > 50:
                        logger.info(f"Ollama Vision ({model}) 成功，文字長度: {len(text)}")
                        return text
                    else:
                        logger.warning(f"Ollama Vision ({model}) 回應過短，嘗試下一個模型")
                except Exception as e:
                    logger.warning(f"Ollama Vision ({model}) 失敗: {e}")
                    continue

        # 方法 3: EasyOCR（最後備援，可能需要下載模型）
        if self.HAS_EASYOCR:
            try:
                logger.info("嘗試使用 EasyOCR（最後備援）...")
                reader = self._get_reader()
                if reader:
                    result = reader.readtext(image_np, detail=0)
                    text = " ".join(result)
                    if text.strip():
                        logger.info(f"EasyOCR 成功，文字長度: {len(text)}")
                        return text
                    else:
                        logger.warning("EasyOCR 返回空文字")
            except Exception as e:
                logger.warning(f"EasyOCR 失敗: {e}")

        # 方法 4: 純文字備用
        logger.warning("所有 OCR 方法都失敗，返回空文字")
        return ""

    def _ocr_with_ollama_vision(self, image_np: np.ndarray, model: str = None) -> str:
        """使用 Ollama Vision 模型進行 OCR"""
        import base64
        from io import BytesIO
        from PIL import Image

        model = model or self.vision_model

        # 轉換為 PNG
        if image_np.shape[2] == 4:
            image_rgb = image_np[:, :, :3]
        else:
            image_rgb = image_np

        img_pil = Image.fromarray(image_rgb)
        buffer = BytesIO()
        img_pil.save(buffer, format="PNG")
        img_base64 = base64.b64encode(buffer.getvalue()).decode()

        # 呼叫 Ollama API
        payload = {
            "model": model,
            "prompt": "請提取圖片中所有的文字內容，直接輸出純文字即可，不要有任何解釋。",
            "images": [img_base64],
        }

        response = requests.post(self.ollama_url, json=payload, stream=True, timeout=60)
        result = []
        for line in response.iter_lines():
            if line:
                data = json.loads(line)
                if "response" in data:
                    result.append(data["response"])
                if data.get("done", False):
                    break

        return "".join(result)

    def build_extraction_prompt(self, ocr_text: str, doctor_names: list) -> str:
        """建立給 LLM 的抽取 Prompt"""
        doctors_str = ", ".join(doctor_names) if doctor_names else "無提供"

        prompt = f"""
你是一個強大的醫療記錄讀寫助手。
下面是一段從醫療軟體螢幕截圖上透過 OCR 抽取出來的雜亂文字。
請你從這段文字中，辨識並提取出以下病患與看診資訊，並嚴格以 JSON 格式輸出：
- "patient_name": 病患姓名
- "patient_id": 身分證或病歷號
- "birth_date": 生日
- "record_time": 紀錄時間或看診時間
- "doctor_name": 醫師姓名 (請與這份已知醫師名單進行比對，若文字中有相符的名字，請填寫相符的名字。已知醫師名單: {doctors_str})

# 雜亂的 OCR 文字：
{ocr_text}

# 輸出要求：
嚴格只輸出一個 JSON 物件，不要有任何其他解釋或 markdown 標記。若找不到某個欄位，請將其值設為空字串 ""。
"""
        return prompt
