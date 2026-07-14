import json
import logging
from pathlib import Path
from typing import List, Dict

logger = logging.getLogger(__name__)


class ConfigManager:
    """設定檔管理器 (管理診所與醫師資訊)"""

    def __init__(self, config_path: str = "config.json"):
        self.config_path = Path(config_path)
        self.config = {
            "clinic": {"name": "", "institution_code": ""},
            "doctors": [],  # list of {"name": "...", "id_card": "..."}
            "last_selected_doctor_index": 0,
            "asr_backend": "whisper",
        }
        self.load()

    def load(self):
        """從硬碟載入設定"""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Merge data with defaults
                    if "clinic" in data:
                        self.config["clinic"].update(data["clinic"])
                    if "doctors" in data:
                        self.config["doctors"] = data["doctors"]
                    if "last_selected_doctor_index" in data:
                        self.config["last_selected_doctor_index"] = data[
                            "last_selected_doctor_index"
                        ]
                    if "asr_backend" in data:
                        self.config["asr_backend"] = data["asr_backend"]
            except Exception as e:
                logger.error(f"無法讀取設定檔: {e}")

    def save(self):
        """儲存設定至硬碟"""
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logger.error(f"無法儲存設定檔: {e}")

    def update_clinic(self, name: str, institution_code: str):
        self.config["clinic"]["name"] = name
        self.config["clinic"]["institution_code"] = institution_code
        self.save()

    def add_doctor(self, name: str, id_card: str):
        self.config["doctors"].append({"name": name, "id_card": id_card})
        self.save()

    def remove_doctor(self, index: int):
        if 0 <= index < len(self.config["doctors"]):
            self.config["doctors"].pop(index)
            if self.config["last_selected_doctor_index"] >= len(self.config["doctors"]):
                self.config["last_selected_doctor_index"] = 0
            self.save()

    def set_selected_doctor(self, index: int):
        if 0 <= index < len(self.config["doctors"]):
            self.config["last_selected_doctor_index"] = index
            self.save()

    def get_selected_doctor_index(self) -> int:
        return self.config.get("last_selected_doctor_index", 0)

    def get_doctors(self) -> List[Dict[str, str]]:
        return self.config["doctors"]

    def get_clinic(self) -> Dict[str, str]:
        return self.config["clinic"]

    def set_asr_backend(self, backend: str):
        self.config["asr_backend"] = backend
        self.save()

    def get_asr_backend(self) -> str:
        return self.config.get("asr_backend", "whisper")
