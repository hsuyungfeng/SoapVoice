"""
ASR 工具模組

提供語音辨識相關的通用輔助函式。
"""

import re


def filter_hallucinations(text: str) -> str:
    """過濾常見的 ASR 幻覺與無效字元。

    檢查文字是否包含已知的幻覺黑名單字詞，或者是單純重複的標點符號。
    如果判定為幻覺，則回傳空字串；否則回傳原始文字的去除首尾空白版本。

    Args:
        text: 原始識別文字

    Returns:
        過濾後的文字，若整句判定為幻覺則回傳空字串
    """
    text = text.strip()
    if not text:
        return ""

    # 檢查是否為重複的標點符號幻覺 (如 ". . . . .")
    if re.match(r'^[\.\s。，,！？!\?\-]+$', text):
        return ""

    # 擴大的幻覺黑名單
    hallucination_blacklist = [
        "谢谢", "謝謝", "字幕", "志愿者", "感謝", "感谢", "Watching", "Amara.org",
        "李宗盛", "杨茜茜", "楊茜茜", "訂閱", "订阅", "剧场", "劇場", "MING PAO",
        "CANADA", "TORONTO", "明報", "多倫多", "Zhang", "Today", "Kyi-day",
        "killed", "Sysh", "recently", "you're-must", "fashow", "chou yin", "chowl",
        "jank", "tureen", "tut-tut", "hush-x", "gawonged"
    ]

    for black_word in hallucination_blacklist:
        if black_word.lower() in text.lower():
            return ""

    return text
