"""
SoapVoice Phase 8.2 - 螢幕擷取 + OCR 病患資訊模組

功能：
- 擷取螢幕畫面
- 使用 EasyOCR 識別病患資訊
- 解析姓名、身分證、生日、病歷號、時間、醫師
"""

import os
import sys
import logging
import time
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
import json
import re

logger = logging.getLogger(__name__)

# 可選依賴
HAS_EASYOCR = False
HAS_PYTESSERACT = False

try:
    import easyocr
    HAS_EASYOCR = True
except ImportError:
    easyocr = None

try:
    import pytesseract
    HAS_PYTESSERACT = True
except ImportError:
    pytesseract = None


@dataclass
class PatientInfo:
    """病患資訊"""

    name: str = ""
    birthday: str = ""
    id_number: str = ""
    medical_record_number: str = ""
    doctor: str = ""
    timestamp: str = ""


class ScreenCapture:
    """螢幕擷取"""

    def __init__(self, output_dir: str = "data/recordings"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._mss = None

    def _init_mss(self):
        """初始化 mss"""
        if self._mss is None:
            try:
                import mss

                self._mss = mss.mss()
                return True
            except ImportError:
                logger.error("mss not installed")
                return False
            except Exception as e:
                logger.error(f"mss init failed: {e}")
                return False
        return True

    def capture_screen(self, output_file: Optional[str] = None) -> str:
        """擷取主螢幕

        Returns:
            圖檔路徑
        """
        if not self._init_mss():
            return ""

        if output_file is None:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            output_file = self.output_dir / f"screenshot_{timestamp}.png"

        try:
            monitor = self._mss.monitors[1]  # 主螢幕
            screenshot = self._mss.grab(monitor)

            # 轉換為 PNG
            from PIL import Image

            img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)
            img.save(output_file, "PNG")

            logger.info(f"Screenshot saved: {output_file}")
            return str(output_file)

        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return ""

    def capture_region(self, x: int, y: int, width: int, height: int, output_file: str = "") -> str:
        """擷取特定區域

        Args:
            x, y: 起始位置
            width, height: 區域大小
            output_file: 輸出檔案
        """
        if not self._init_mss():
            return ""

        if not output_file:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            output_file = self.output_dir / f"screenshot_{timestamp}.png"

        try:
            monitor = {"left": x, "top": y, "width": width, "height": height}
            screenshot = self._mss.grab(monitor)

            from PIL import Image

            img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)
            img.save(output_file, "PNG")

            logger.info(f"Region screenshot saved: {output_file}")
            return str(output_file)

        except Exception as e:
            logger.error(f"Region capture failed: {e}")
            return ""


class PatientInfoOCR:
    """病患資訊 OCR 識別"""

    def __init__(self, mode: str = "auto"):
        """
        Args:
            mode: "auto" (優先用 Tesseract), "tesseract", "easyocr"
        """
        self.mode = mode
        self.easy_reader = None
        self._init_engines()

    def _init_engines(self):
        """初始化 OCR 引擎"""
        # 1. 檢查 Tesseract
        if HAS_PYTESSERACT:
            try:
                # 嘗試執行一次以確認路徑
                tess_ver = pytesseract.get_tesseract_version()
                logger.info(f"Tesseract detected: {tess_ver}")
            except Exception as e:
                logger.warning(f"pytesseract installed but bin not found: {e}")
                # 繼續，但在執行時會失敗

        # 2. 只有在模式要求或 Tesseract 不可用時初始化 EasyOCR
        if self.mode == "easyocr" or (self.mode == "auto" and not HAS_PYTESSERACT):
            self._init_easyocr()

    def _init_easyocr(self):
        """初始化 EasyOCR reader (重量級)"""
        if HAS_EASYOCR and self.easy_reader is None:
            try:
                logger.info("Initializing EasyOCR reader (Traditional Chinese + English)...")
                self.easy_reader = easyocr.Reader(["ch_tra", "en"], gpu=False, verbose=False)
            except Exception as e:
                logger.error(f"EasyOCR init failed: {e}")

    def recognize_from_file(self, image_path: str) -> List[Tuple]:
        """從檔案識別
        Returns:
            [(text, bounding_box, confidence), ...]
            注意內容格式儘量與 EasyOCR 保持一致以便相容解析邏輯
        """
        # 方法 1: Tesseract (優先)
        if (self.mode == "auto" or self.mode == "tesseract") and HAS_PYTESSERACT:
            try:
                logger.info("Using Tesseract-OCR...")
                from PIL import Image
                img = Image.open(image_path)
                data = pytesseract.image_to_data(img, lang="chi_tra+eng", output_type=pytesseract.Output.DICT)
                
                results = []
                for i in range(len(data['text'])):
                    text = data['text'][i].strip()
                    if text:
                        # 模擬 EasyOCR 格式: (bounding_box, text, confidence)
                        # bbox [[x,y], [x+w,y], [x+w,y+h], [x,y+h]]
                        x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
                        bbox = [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]
                        conf = float(data['conf'][i]) / 100.0
                        results.append((bbox, text, conf))
                
                if results:
                    return results
                logger.warning("Tesseract found no text, failing over...")
            except Exception as e:
                logger.warning(f"Tesseract OCR failed: {e}")

        # 方法 2: EasyOCR (備援)
        if HAS_EASYOCR:
            if self.easy_reader is None:
                self._init_easyocr()
            if self.easy_reader:
                try:
                    logger.info("Using EasyOCR...")
                    raw_results = self.easy_reader.readtext(image_path)
                    # EasyOCR 格式本身就是 [ (bbox, text, conf), ... ]
                    # 這裡統一回傳格式
                    results = []
                    for r in raw_results:
                        results.append((r[0], r[1], r[2]))
                    return results
                except Exception as e:
                    logger.error(f"EasyOCR failed: {e}")

        logger.error("No OCR engine available or all failed")
        return []

    def recognize_from_array(self, image_array) -> List[Tuple]:
        """從圖像陣列識別"""
        if HAS_EASYOCR:
            if self.easy_reader is None:
                self._init_easyocr()
            if self.easy_reader:
                return self.easy_reader.readtext(image_array)
        return []

    def extract_patient_info(self, ocr_results: List[Tuple]) -> PatientInfo:
        """從 OCR 結果解析病患資訊"""
        patient = PatientInfo()

        # 合併所有識別文字
        all_text = " ".join([r[1] for r in ocr_results])

        # 解析各欄位
        patient.name = self._extract_name(ocr_results, all_text)
        patient.id_number = self._extract_id_number(ocr_results, all_text)
        patient.birthday = self._extract_birthday(ocr_results, all_text)
        patient.medical_record_number = self._extract_mrn(ocr_results, all_text)
        patient.doctor = self._extract_doctor(ocr_results, all_text)
        patient.timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

        logger.info(f"Extracted patient: {patient.name}, ID: {patient.id_number}")

        return patient

    def _extract_name(self, results: List[Tuple], all_text: str) -> str:
        """解析姓名"""
        name_keywords = ["姓名", "name", "病患姓名", "患者姓名", "病人"]

        for keyword in name_keywords:
            for r in results:
                if keyword in r[1]:
                    # 嘗試取得下一個文字塊作為名字
                    idx = results.index(r)
                    if idx + 1 < len(results):
                        return results[idx + 1][1].strip()

        # 如果沒找到關鍵字，嘗試找常見名字格式
        # 例如：2-4個中文字
        pattern = r"[\u4e00-\u9fff]{2,4}"
        matches = re.findall(pattern, all_text)
        if matches:
            return matches[0]

        return ""

    def _extract_id_number(self, results: List[Tuple], all_text: str) -> str:
        """解析身份證號"""
        id_keywords = ["身份證", "ID", "身份證號", "身分證", "的身份字號"]

        for keyword in id_keywords:
            for r in results:
                if keyword in r[1]:
                    # 找下一個可能是身份證的格式
                    idx = results.index(r)
                    for i in range(idx + 1, min(idx + 4, len(results))):
                        text = results[i][1].strip()
                        # 匹配身份證格式 (A開頭+9位數)
                        if re.match(r"^[A-Z][0-9]{9}$", text):
                            return text

        # 直接搜尋身份證格式
        pattern = r"[A-Z][0-9]{9}"
        matches = re.findall(pattern, all_text)
        if matches:
            return matches[0]

        return ""

    def _extract_birthday(self, results: List[Tuple], all_text: str) -> str:
        """解析生日"""
        date_keywords = ["生日", "出生", "birth", "生年月日", "出生日期", "DATE"]

        for keyword in date_keywords:
            for r in results:
                if keyword in r[1]:
                    idx = results.index(r)
                    for i in range(idx + 1, min(idx + 3, len(results))):
                        text = results[i][1].strip()
                        # 匹配日期格式
                        if re.match(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}", text):
                            return text
                        if re.match(r"\d{1,2}[-/]\d{1,2}[-/]\d{4}", text):
                            return text

        # 直接搜尋日期格式
        patterns = [
            r"\d{4}[-/]\d{1,2}[-/]\d{1,2}",
            r"\d{1,2}[-/]\d{1,2}[-/]\d{4}",
        ]
        for pattern in patterns:
            matches = re.findall(pattern, all_text)
            if matches:
                return matches[0]

        return ""

    def _extract_mrn(self, results: List[Tuple], all_text: str) -> str:
        """解析病歷號"""
        mrn_keywords = ["病歷號", "病案號", "MRN", "chart", "病號", "就診號", "號碼"]

        for keyword in mrn_keywords:
            for r in results:
                if keyword in r[1]:
                    idx = results.index(r)
                    for i in range(idx + 1, min(idx + 3, len(results))):
                        text = results[i][1].strip()
                        # 匹配病歷號格式 (數字或英數混合)
                        if re.match(r"^[A-Z0-9]{4,12}$", text):
                            return text

        # 搜尋常見病歷號格式
        pattern = r"[A-Z]{1,3}[0-9]{4,8}"
        matches = re.findall(pattern, all_text)
        if matches:
            return matches[0]

        return ""

    def _extract_doctor(self, results: List[Tuple], all_text: str) -> str:
        """解析醫師姓名"""
        doc_keywords = ["醫師", "醫生", "doctor", "主治", "負責醫師", "主治醫師"]

        for keyword in doc_keywords:
            for r in results:
                if keyword in r[1]:
                    idx = results.index(r)
                    if idx + 1 < len(results):
                        # 醫師名字通常是 2-4個字
                        name = results[idx + 1][1].strip()
                        if 1 < len(name) <= 5:
                            return name

        # 嘗試找常見醫師結尾
        pattern = r"[\u4e00-\u9fff]{2,4}醫師"
        matches = re.findall(pattern, all_text)
        if matches:
            return matches[0].replace("醫師", "")

        return ""


class CaptureWorkflow:
    """擷取工作流程"""

    def __init__(self):
        self.screen_capture = ScreenCapture()
        self.ocr = PatientInfoOCR()
        self.last_image_file = ""
        self.last_patient_info = PatientInfo()

    def capture_and_extract(self) -> PatientInfo:
        """執行擷取+識別流程

        Returns:
            病患資訊
        """
        # 1. 擷取螢幕
        logger.info("Capturing screen...")
        self.last_image_file = self.screen_capture.capture_screen()

        if not self.last_image_file:
            logger.error("Screenshot failed")
            return PatientInfo()

        # 2. OCR 識別
        logger.info("Running OCR...")
        ocr_results = self.ocr.recognize_from_file(self.last_image_file)

        if not ocr_results:
            logger.warning("No text found in screenshot")
            return PatientInfo()

        # 3. 解析病患資訊
        logger.info("Extracting patient info...")
        self.last_patient_info = self.ocr.extract_patient_info(ocr_results)

        return self.last_patient_info

    def get_last_results(self) -> dict:
        """取得最後結果"""
        return {
            "image_file": self.last_image_file,
            "patient_info": {
                "name": self.last_patient_info.name,
                "birthday": self.last_patient_info.birthday,
                "id_number": self.last_patient_info.id_number,
                "medical_record_number": self.last_patient_info.medical_record_number,
                "doctor": self.last_patient_info.doctor,
                "timestamp": self.last_patient_info.timestamp,
            },
            "ocr_raw": self.last_image_file,
        }


def main():
    """測試擷取流程"""
    import argparse

    parser = argparse.ArgumentParser(description="Screen Capture + OCR")
    parser.add_argument("--capture", action="store_true", help="Capture and extract")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    if args.capture:
        workflow = CaptureWorkflow()

        print("準備擷取螢幕，請確保病患資訊在畫面上...")
        time.sleep(2)  # 讓使用者準備

        patient = workflow.capture_and_extract()

        print("\n=== 識別結果 ===")
        print(f"姓名: {patient.name}")
        print(f"生日: {patient.birthday}")
        print(f"身份證: {patient.id_number}")
        print(f"病歷號: {patient.medical_record_number}")
        print(f"醫師: {patient.doctor}")
        print(f"時間: {patient.timestamp}")


if __name__ == "__main__":
    main()
