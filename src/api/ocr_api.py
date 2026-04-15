import io
import logging
import numpy as np
from PIL import Image
from fastapi import APIRouter, File, Form, UploadFile, HTTPException

from src.nlp.ocr_parser import OCRParser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ocr", tags=["OCR"])

@router.post("/process")
async def process_ocr(
    image: UploadFile = File(...),
    engine: str = Form("easyocr"),
    device: str = Form("cpu")
):
    """
    接收圖片上傳並進行 OCR 識別
    """
    try:
        content = await image.read()
        img_pil = Image.open(io.BytesIO(content))
        if img_pil.mode == 'RGBA':
            background = Image.new("RGB", img_pil.size, (255, 255, 255))
            background.paste(img_pil, mask=img_pil.split()[3])
            img_pil = background
        else:
            img_pil = img_pil.convert("RGB")
            
        img_np = np.array(img_pil)
        
        # 根據參數設定選擇模型
        vision_model = "glm-ocr"
        if engine == "vision":
            # 如果後端支援多種選擇，未來可從這裡動態指派 model
            pass 
        
        parser = OCRParser(vision_model=vision_model)
        
        if engine == "easyocr":
            if not parser.HAS_EASYOCR:
                return {
                    "status": "error",
                    "text": "",
                    "detail": "EasyOCR 無法啟動或缺乏依賴 (可能由於 PyTorch CUDA/cuDNN 缺失或版本問題)",
                    "engine_requested": engine,
                    "device": device
                }
                
            reader = parser._get_reader()
            if reader:
                result = reader.readtext(img_np, detail=0)
                text = " ".join(result)
            else:
                text = "EasyOCR 模型初始化失敗，請檢查後端日誌"
        elif engine in ["vision", "glm-ocr", "gemma4:e4b", "gemma4:e2b"]:
            # 動態傳遞選擇的 Vision 模型給 Ollama
            target_model = engine if engine != "vision" else "glm-ocr"
            text = parser._ocr_with_ollama_vision(img_np, model=target_model)
        else:
            text = parser._try_ocr_methods(img_np)
        
        return {
            "status": "success",
            "text": text,
            "engine_requested": engine,
            "device": device
        }

    except Exception as e:
        logger.error(f"OCR process failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
