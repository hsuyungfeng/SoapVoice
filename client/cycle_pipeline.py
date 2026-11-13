"""Phase 31: 綠燈後完整生命週期流程 (D-31-23, D-31-24, D-31-25).

包含：
- map_lan_result_to_draft: LAN 結果轉換為循環草稿 payload
- CyclePipeline:
  1. finalize: 確認所有分段抵達 server 並比對串接音訊 PCM 雜湊
  2. 生成 SOAP: 以串接後 full.wav 與截圖透過 generate_fn 產生 SOAP
  3. 送出草稿: POST /api/cycles/{cycle_id}/draft
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx

from client.audio_recorder import concat_segments, pcm_sha256
from client.segment_store import SegmentStore

logger = logging.getLogger("soapvoice.cycle_pipeline")


def map_lan_result_to_draft(
    lan_result: Dict[str, Any],
    *,
    cycle_id: str,
    patient_ref: str,
    case_id: str,
    visit_date: str,
    order_code: Optional[str] = None,
) -> Tuple[Dict[str, Any], List[str]]:
    """將 LAN 處理結果轉換為契約 §2 規範之循環草稿 JSON。

    回傳：
        (payload, extras_missing): payload 字典與缺少的欄位名稱清單。
    """
    extras_missing: List[str] = []

    # 1. SOAP 字典映射
    raw_soap = lan_result.get("soap") or {}
    if isinstance(raw_soap, dict):
        s_val = str(raw_soap.get("s") or raw_soap.get("Subjective") or "")
        o_val = str(raw_soap.get("o") or raw_soap.get("Objective") or "")
        a_val = str(raw_soap.get("a") or raw_soap.get("Assessment") or "")
        p_val = str(raw_soap.get("p") or raw_soap.get("Plan") or "")
    else:
        s_val, o_val, a_val, p_val = str(raw_soap), "", "", ""

    soap_dict = {"s": s_val, "o": o_val, "a": a_val, "p": p_val}

    # 2. 逐字稿
    transcript = str(lan_result.get("transcript") or "")

    # 3. 中文摘要 (A-31-13b: 若無則空字串並記 missing，絕不以英文翻譯捏造)
    if "summary_zh" in lan_result and lan_result["summary_zh"]:
        summary_zh = str(lan_result["summary_zh"])
    else:
        summary_zh = ""
        extras_missing.append("summary_zh")

    # 4. 過去病史
    if "past_history" in lan_result and lan_result["past_history"]:
        past_history = str(lan_result["past_history"])
    elif "history" in lan_result and lan_result["history"]:
        past_history = str(lan_result["history"])
    else:
        past_history = ""
        extras_missing.append("past_history")

    # 5. 建議項 (ICD-10, 醫囑, 藥物)
    raw_icd = lan_result.get("icd10_codes") or lan_result.get("icd10")
    if raw_icd:
        icd10_list = [c["code"] if isinstance(c, dict) and "code" in c else str(c) for c in raw_icd]
    else:
        icd10_list = []
        extras_missing.append("suggestions.icd10")

    raw_orders = lan_result.get("medical_orders") or lan_result.get("orders")
    if raw_orders:
        orders_list = [str(o) for o in raw_orders]
    else:
        orders_list = []
        extras_missing.append("suggestions.orders")

    raw_meds = lan_result.get("drug_recommendations") or lan_result.get("drugs") or lan_result.get("meds")
    if raw_meds:
        meds_list = [str(m) for m in raw_meds]
    else:
        meds_list = []
        extras_missing.append("suggestions.meds")

    payload: Dict[str, Any] = {
        "session_id": cycle_id,
        "case_id": case_id,
        "patient_ref": patient_ref,
        "visit_date": visit_date,
        "soap": soap_dict,
        "transcript": transcript,
        "extras": {
            "summary_zh": summary_zh,
            "past_history": past_history,
            "suggestions": {
                "icd10": icd10_list,
                "orders": orders_list,
                "meds": meds_list,
            },
        },
    }
    if order_code:
        payload["order_code"] = order_code

    return payload, extras_missing


class CyclePipeline:
    """協調整個錄音循環綠燈後推進流程之 Pipeline。"""

    def __init__(
        self,
        store: SegmentStore,
        *,
        base_url: str,
        api_key: str,
        http: Optional[httpx.Client] = None,
        generate_fn: Optional[Callable[[str, str, str, str], Dict[str, Any]]] = None,
    ):
        self.store = store
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._http = http
        self.generate_fn = generate_fn

    def _get_client(self) -> httpx.Client:
        if self._http is not None:
            return self._http
        return httpx.Client(timeout=15.0)

    def advance(self, cycle_id: str) -> str:
        """推進特定循環流程至多一步。

        回傳當前循環所處狀態：
        - UPLOADING: 尚有未傳完分段或 finalize 缺段
        - GENERATING: 已 finalize，SOAP 產生中或草稿送出中
        - SUBMITTED: 草稿已成功送達 server
        - ERROR: 發生不可自癒之致命錯誤
        """
        m = self.store.load(cycle_id)
        if not m:
            return "ERROR"
        if m.draft_submitted:
            return "SUBMITTED"

        # ── 步驟 1: Finalize ──────────────────────────────────────────
        if not m.finalized:
            pending = self.store.pending_chunks(cycle_id)
            if m.total_chunks is None or len(pending) > 0:
                return "UPLOADING"

            c_dir = self.store.open_cycle(cycle_id)
            chunk_paths = []
            for seq in range(m.total_chunks):
                p = Path(m.chunks[str(seq)]["path"])
                if not p.is_absolute():
                    p = c_dir / p
                chunk_paths.append(p)
            audio_sha = pcm_sha256(chunk_paths)

            client = self._get_client()
            should_close = self._http is None
            try:
                url = f"{self.base_url}/api/cycles/{cycle_id}/finalize"
                payload = {"total_chunks": m.total_chunks, "audio_sha256": audio_sha}
                headers = {"X-API-Key": self.api_key}
                resp = client.post(url, json=payload, headers=headers)

                if resp.status_code == 200:
                    self.store.mark_finalized(cycle_id)
                    logger.info("循環 %s 音訊串接確認完成 (finalize)", cycle_id)
                    return "GENERATING"
                elif resp.status_code == 409:
                    # server 缺段，重設未 acked 讓 uploader 補傳
                    resp_data = resp.json()
                    missing = resp_data.get("missing", [])
                    if missing:
                        self.store.reset_ack(cycle_id, [int(x) for x in missing])
                    return "UPLOADING"
                elif resp.status_code == 422:
                    self.store.set_error(cycle_id, f"Finalize 422: {resp.text}")
                    return "ERROR"
                else:
                    logger.warning("Finalize 回應狀態 %s: %s", resp.status_code, resp.text)
                    return "UPLOADING"
            except (httpx.RequestError, OSError) as exc:
                logger.warning("Finalize 網路異常: %s", exc)
                return "UPLOADING"
            finally:
                if should_close:
                    client.close()

        # ── 步驟 2: 以完整音檔產生 SOAP ──────────────────────────────
        if not m.generation_done:
            c_dir = self.store.open_cycle(cycle_id)
            result_file = c_dir / "lan_result.json"

            # 冪等檢查：已落地結果直接讀取
            if result_file.is_file():
                self.store.mark_generation_done(cycle_id)
                return "GENERATING"

            if not self.generate_fn:
                self.store.set_error(cycle_id, "未設定 generate_fn")
                return "ERROR"

            full_wav = c_dir / "full.wav"
            if not full_wav.is_file():
                concat_segments(c_dir, full_wav)

            ctx = self.store.get_context(cycle_id) or {}
            screenshot_path = ctx.get("screenshot_path", "")
            patient_name = ctx.get("patient_name", "")
            doctor_name = ctx.get("doctor_name", "")

            try:
                lan_res = self.generate_fn(str(full_wav), str(screenshot_path), patient_name, doctor_name)
                result_file.write_text(json.dumps(lan_res, ensure_ascii=False, indent=2), encoding="utf-8")
                self.store.mark_generation_done(cycle_id)
                logger.info("循環 %s SOAP 生成完畢", cycle_id)
                return "GENERATING"
            except Exception as exc:
                logger.error("循環 %s SOAP 生成失敗: %s", cycle_id, exc)
                # 保持 GENERATING、記 last_error，不刪任何檔案 (Test 7)
                with self.store._lock:
                    m = self.store.load(cycle_id)
                    if m:
                        m.last_error = f"Generate failed: {exc}"
                        self.store._save_manifest_unlocked(m)
                return "GENERATING"

        # ── 步驟 3: 送出草稿 ──────────────────────────────────────────
        if not m.draft_submitted:
            c_dir = self.store.open_cycle(cycle_id)
            result_file = c_dir / "lan_result.json"
            if not result_file.is_file():
                return "GENERATING"

            lan_res = json.loads(result_file.read_text(encoding="utf-8"))
            ctx = self.store.get_context(cycle_id) or {}

            patient_ref = ctx.get("patient_ref", "anon_ref")
            case_id = ctx.get("case_id", f"case_{cycle_id[:8]}")
            visit_date = ctx.get("visit_date", "2026-11-12")
            order_code = ctx.get("order_code")

            payload, missing_fields = map_lan_result_to_draft(
                lan_res,
                cycle_id=cycle_id,
                patient_ref=patient_ref,
                case_id=case_id,
                visit_date=visit_date,
                order_code=order_code,
            )

            if missing_fields:
                with self.store._lock:
                    cur_m = self.store.load(cycle_id)
                    if cur_m:
                        cur_m.extras_missing = missing_fields
                        self.store._save_manifest_unlocked(cur_m)

            client = self._get_client()
            should_close = self._http is None
            try:
                url = f"{self.base_url}/api/cycles/{cycle_id}/draft"
                headers = {"X-API-Key": self.api_key}
                resp = client.post(url, json=payload, headers=headers)

                if resp.status_code in (200, 201):
                    draft_data = resp.json()
                    draft_id = draft_data.get("draft_id") or ""
                    self.store.mark_draft_submitted(cycle_id, draft_id)
                    logger.info("循環 %s 草稿已成功送達 (draft_id=%s)", cycle_id, draft_id)
                    return "SUBMITTED"
                elif resp.status_code == 409:
                    self.store.set_error(cycle_id, f"Draft submission rejected (409): {resp.text}")
                    return "ERROR"
                else:
                    logger.warning("Draft submission failed: %s", resp.status_code)
                    return "GENERATING"
            except (httpx.RequestError, OSError) as exc:
                logger.warning("Draft submission network error: %s", exc)
                return "GENERATING"
            finally:
                if should_close:
                    client.close()

        return "SUBMITTED"
