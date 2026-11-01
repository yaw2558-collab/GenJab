"""แปล prompt ภาษาไทยเป็นอังกฤษด้วย Meta Llama API ก่อนส่งไปเจนรูป (urllib ล้วน ไม่แตะ Tk).

คีย์: ช่องในแอป หรือตัวแปร LLAMA_API_KEY — เปลี่ยนรุ่นได้ด้วย LLAMA_MODEL.
ใช้ endpoint แบบ OpenAI-compatible ของ Llama API; อ่านคำตอบแบบ native ของ Llama ได้ด้วย."""
import json
import os
import re
import urllib.request

from cloud_providers import CloudError, _http

LLAMA_URL = "https://api.llama.com/compat/v1/chat/completions"
LLAMA_ENV = "LLAMA_API_KEY"
LLAMA_KEY_URL = "https://llama.developer.meta.com"
DEFAULT_LLAMA_MODEL = "Llama-4-Maverick-17B-128E-Instruct-FP8"

_THAI = re.compile(r"[฀-๿]")

SYSTEM_PROMPT = (
    "You translate prompts for an AI image generator from Thai to English. "
    "Reply with ONLY the English prompt: no quotes, no explanations, no prefixes. "
    "Keep any English words, names, numbers and style tags as they are. "
    "Keep the meaning and level of detail; write it as a natural image-generation prompt. "
    "Thai cultural terms (e.g. Songkran, Loy Krathong, tuk-tuk) may be kept as romanized words."
)


def has_thai(text):
    return bool(_THAI.search(text or ""))


def llama_key(key=""):
    return (key or "").strip() or os.environ.get(LLAMA_ENV, "").strip()


def llama_model():
    return os.environ.get("LLAMA_MODEL", "").strip() or DEFAULT_LLAMA_MODEL


def translate_request(text, key, model=None):
    body = {"model": model or llama_model(), "temperature": 0.2, "max_tokens": 400,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                         {"role": "user", "content": text}]}
    return urllib.request.Request(
        LLAMA_URL, data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})


def parse_translation(data):
    """รับได้ทั้งแบบ OpenAI (choices) และแบบ native ของ Llama (completion_message)."""
    try:
        d = json.loads(data)
    except ValueError as e:
        raise CloudError("Llama ตอบกลับมาอ่านไม่ออก") from e
    text = ""
    choices = d.get("choices") or []
    if choices:
        text = ((choices[0] or {}).get("message") or {}).get("content") or ""
    if not text:
        content = (d.get("completion_message") or {}).get("content")
        if isinstance(content, dict):
            text = content.get("text") or ""
        elif isinstance(content, str):
            text = content
    if isinstance(text, list):  # บางรุ่นคืนเป็น list ของ part
        text = " ".join(p.get("text", "") for p in text if isinstance(p, dict))
    text = text.strip().strip('"').strip()
    if text.lower().startswith("english prompt:"):
        text = text[len("english prompt:"):].strip()
    if not text:
        raise CloudError("Llama ไม่ได้ส่งคำแปลกลับมา")
    return text


def translate(text, key=""):
    """แปลไทยเป็นอังกฤษ — ข้อความที่ไม่มีอักษรไทยคืนเดิมทันที (ไม่ยิงเน็ต ไม่เสียเงิน)."""
    text = (text or "").strip()
    if not has_thai(text):
        return text
    key = llama_key(key)
    if not key:
        raise CloudError(f"การแปลไทยต้องใส่คีย์ Meta Llama ก่อน (หรือตั้งตัวแปร {LLAMA_ENV})\n"
                         f"ขอคีย์ได้ที่ {LLAMA_KEY_URL}")
    try:
        data, _ = _http(translate_request(text, key))
    except CloudError as e:
        raise CloudError(f"แปลด้วย Llama ไม่สำเร็จ: {e}") from e
    return parse_translation(data)
