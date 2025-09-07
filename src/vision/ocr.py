# ============================ [01] VISION OCR (optional) — START ============================
"""
의존성 없는 CI 안전 기본형.
- pytesseract / PIL(Pillow)이 설치되어 있으면 사용
- 없으면 빈 문자열("")을 반환 (앱에서는 '텍스트를 찾지 못함'으로 처리)
"""

from __future__ import annotations


def extract_text(file_path: str) -> str:
    try:
        from PIL import Image  # type: ignore
        import pytesseract  # type: ignore

        img = Image.open(file_path)
        txt = pytesseract.image_to_string(img, lang="eng+kor")
        return (txt or "").strip()
    except Exception:
        # 의존성이 없거나 오류일 경우 빈 문자열
        return ""
# ============================= [01] VISION OCR (optional) — END =============================
