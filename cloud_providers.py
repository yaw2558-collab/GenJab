"""ตัวเจนรูปผ่าน API คลาวด์ของ GenJab Cloud — ไม่ต้องมีการ์ดจอ/โมเดลในเครื่อง.

ใช้แค่ไลบรารีมาตรฐาน (urllib) ไม่แตะ Tk — เทสได้โดยไม่เปิดหน้าต่าง.
ทุกผู้ให้บริการคืน list ของ bytes (ไฟล์รูป PNG/JPEG/WebP ดิบ) ให้ฝั่งแอปเปิดด้วย PIL เอง.

ผู้ให้บริการ:
- pollinations — ฟรี ไม่ต้องมีคีย์ (ใส่ token ได้ถ้ามี จะได้คิวเร็วขึ้น)
- openai       — gpt-image-1 (ต้องมี OPENAI_API_KEY)
- gemini       — Gemini image (ต้องมี GEMINI_API_KEY)
- stability    — Stable Image Core (ต้องมี STABILITY_API_KEY)
"""
import base64
import json
import os
import random
import urllib.error
import urllib.parse
import urllib.request
import uuid

RATIOS = ("1:1", "3:4", "4:3", "9:16", "16:9")
TIMEOUT = 180


class CloudError(Exception):
    """เจนไม่สำเร็จ — ข้อความเป็นภาษาไทยพร้อมโชว์ผู้ใช้ได้เลย."""


PROVIDERS = {
    "pollinations": {
        "label": "Pollinations (ฟรี ไม่ต้องมีคีย์)",
        "env": "POLLINATIONS_TOKEN",
        "key_required": False,
        "models": ["flux", "turbo", "kontext"],
        "negative": True,
        "max_count": 4,
        "key_url": "https://auth.pollinations.ai",
    },
    "openai": {
        "label": "OpenAI (gpt-image)",
        "env": "OPENAI_API_KEY",
        "key_required": True,
        "models": ["gpt-image-1", "gpt-image-1-mini"],
        "negative": False,
        "max_count": 4,
        "key_url": "https://platform.openai.com/api-keys",
    },
    "gemini": {
        "label": "Google Gemini",
        "env": "GEMINI_API_KEY",
        "key_required": True,
        "models": ["gemini-2.5-flash-image"],
        "negative": False,
        "max_count": 4,
        "key_url": "https://aistudio.google.com/apikey",
    },
    "stability": {
        "label": "Stability AI (Stable Image)",
        "env": "STABILITY_API_KEY",
        "key_required": True,
        "models": ["core", "ultra", "sd3.5-large", "sd3.5-large-turbo"],
        "negative": True,
        "max_count": 4,
        "key_url": "https://platform.stability.ai/account/keys",
    },
}

# ขนาดพิกเซลต่อสัดส่วน (ด้านยาว ~1024) — ใช้กับ pollinations
RATIO_PIXELS = {"1:1": (1024, 1024), "3:4": (768, 1024), "4:3": (1024, 768),
                "9:16": (576, 1024), "16:9": (1024, 576)}
# OpenAI รับแค่ 3 ขนาด — เลือกตัวที่ใกล้สัดส่วนที่สุด
OPENAI_SIZES = {"1:1": "1024x1024", "3:4": "1024x1536", "9:16": "1024x1536",
                "4:3": "1536x1024", "16:9": "1536x1024"}


def provider_ids():
    return list(PROVIDERS)


def label_to_id(label):
    for pid, p in PROVIDERS.items():
        if p["label"] == label:
            return pid
    raise KeyError(label)


def resolve_key(provider, key=""):
    """คีย์ที่พิมพ์ในแอปมาก่อน ไม่มีค่อยดูตัวแปรระบบ (env)."""
    key = (key or "").strip()
    return key or os.environ.get(PROVIDERS[provider]["env"], "").strip()


def _ratio(ratio):
    return ratio if ratio in RATIOS else "1:1"


def _seed(seed):
    """seed ว่าง/-1 = สุ่ม — คืน int เสมอเพื่อฝังในรูปได้."""
    try:
        s = int(seed)
    except (TypeError, ValueError):
        s = -1
    return random.randint(0, 2**31 - 1) if s < 0 else s


def _http(req):
    """ยิง request แล้วคืน (bytes, content-type) — แปลงข้อผิดพลาดเป็น CloudError ภาษาไทย."""
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return r.read(), r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        body = e.read()[:600].decode("utf-8", "replace")
        raise CloudError(_http_hint(e.code, body)) from e
    except urllib.error.URLError as e:
        raise CloudError(f"ต่อเน็ตไม่ได้: {e.reason}") from e
    except TimeoutError as e:
        raise CloudError("รอนานเกินไป เซิร์ฟเวอร์ไม่ตอบ ลองใหม่อีกที") from e


def _http_hint(code, body):
    msg = _error_message(body)
    if code in (401, 403):
        hint = "คีย์ API ไม่ถูกต้องหรือไม่มีสิทธิ์"
    elif code == 402:
        hint = "เครดิตหมด ต้องเติมเงินในบัญชีผู้ให้บริการ"
    elif code == 429:
        hint = "ยิงถี่เกินไป/โควตาเต็ม รอสักพักแล้วลองใหม่"
    elif code == 400:
        hint = "คำขอไม่ผ่าน (prompt อาจโดนกรองเนื้อหา หรือค่าไม่ถูกต้อง)"
    elif code >= 500:
        hint = "เซิร์ฟเวอร์ผู้ให้บริการมีปัญหา ลองใหม่อีกที"
    else:
        hint = "เจนไม่สำเร็จ"
    return f"{hint} (HTTP {code})" + (f"\n{msg}" if msg else "")


def _error_message(body):
    """ดึงข้อความ error จาก JSON ของผู้ให้บริการ — อ่านไม่ออกคืนข้อความดิบสั้น ๆ."""
    try:
        d = json.loads(body)
    except ValueError:
        return body.strip()[:200]
    if isinstance(d, dict):
        err = d.get("error", d)
        if isinstance(err, dict):
            return str(err.get("message") or err.get("name") or "")[:300]
        if isinstance(err, str):
            return err[:300]
        errs = d.get("errors")
        if isinstance(errs, list) and errs:
            return str(errs[0])[:300]
    return ""


def _check_image(data, ctype=""):
    if ctype.startswith("image/") or data[:8] == b"\x89PNG\r\n\x1a\n" or data[:3] == b"\xff\xd8\xff" \
            or data[8:12] == b"WEBP":
        return data
    raise CloudError("ผู้ให้บริการไม่ได้ส่งรูปกลับมา: " + data[:200].decode("utf-8", "replace"))


# ---------------- ผู้ให้บริการแต่ละเจ้า ----------------

def pollinations_request(prompt, *, negative="", ratio="1:1", seed=0, model="flux", key=""):
    w, h = RATIO_PIXELS[_ratio(ratio)]
    q = {"width": w, "height": h, "seed": seed, "model": model or "flux",
         "nologo": "true", "private": "true", "safe": "false"}
    if negative:
        q["negative_prompt"] = negative
    url = ("https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt, safe="")
           + "?" + urllib.parse.urlencode(q))
    headers = {"User-Agent": "GenJab-Cloud/1.0"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    return urllib.request.Request(url, headers=headers)


def gen_pollinations(prompt, *, negative, ratio, seed, model, key, count):
    out = []
    for i in range(count):
        data, ctype = _http(pollinations_request(prompt, negative=negative, ratio=ratio,
                                                 seed=seed + i, model=model, key=key))
        out.append(_check_image(data, ctype))
    return out


def openai_request(prompt, *, ratio="1:1", model="gpt-image-1", key="", count=1):
    body = {"model": model or "gpt-image-1", "prompt": prompt, "n": count,
            "size": OPENAI_SIZES[_ratio(ratio)]}
    return urllib.request.Request(
        "https://api.openai.com/v1/images/generations",
        data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})


def parse_openai(data):
    d = json.loads(data)
    imgs = []
    for item in d.get("data") or []:
        if item.get("b64_json"):
            imgs.append(base64.b64decode(item["b64_json"]))
        elif item.get("url"):
            raw, ctype = _http(urllib.request.Request(item["url"]))
            imgs.append(_check_image(raw, ctype))
    if not imgs:
        raise CloudError("OpenAI ไม่ได้ส่งรูปกลับมา")
    return imgs


def gen_openai(prompt, *, negative, ratio, seed, model, key, count):
    data, _ = _http(openai_request(prompt, ratio=ratio, model=model, key=key, count=count))
    return parse_openai(data)


def gemini_request(prompt, *, ratio="1:1", model="gemini-2.5-flash-image", key=""):
    model = model or "gemini-2.5-flash-image"
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["IMAGE"],
                                 "imageConfig": {"aspectRatio": _ratio(ratio)}}}
    return urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{urllib.parse.quote(model)}:generateContent",
        data=json.dumps(body).encode(), method="POST",
        headers={"x-goog-api-key": key, "Content-Type": "application/json"})


def parse_gemini(data):
    d = json.loads(data)
    imgs, texts = [], []
    for cand in d.get("candidates") or []:
        for part in (cand.get("content") or {}).get("parts") or []:
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                imgs.append(base64.b64decode(inline["data"]))
            elif part.get("text"):
                texts.append(part["text"])
    if not imgs:
        reason = (d.get("promptFeedback") or {}).get("blockReason") or " ".join(texts)[:200]
        raise CloudError("Gemini ไม่ได้ส่งรูปกลับมา" + (f": {reason}" if reason else ""))
    return imgs


def gen_gemini(prompt, *, negative, ratio, seed, model, key, count):
    out = []
    for _ in range(count):  # Gemini เจนทีละรูปต่อคำขอ
        data, _ = _http(gemini_request(prompt, ratio=ratio, model=model, key=key))
        out.extend(parse_gemini(data)[:1])
    return out


def _multipart(fields):
    boundary = uuid.uuid4().hex
    parts = []
    for name, value in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n')
    parts.append(f"--{boundary}--\r\n")
    return "".join(parts).encode("utf-8"), f"multipart/form-data; boundary={boundary}"


def stability_request(prompt, *, negative="", ratio="1:1", seed=0, model="core", key=""):
    model = model or "core"
    fields = {"prompt": prompt, "aspect_ratio": _ratio(ratio), "seed": seed, "output_format": "png"}
    if negative:
        fields["negative_prompt"] = negative
    if model.startswith("sd3"):
        endpoint = "sd3"
        fields["model"] = model
    else:
        endpoint = model  # core / ultra
    body, ctype = _multipart(fields)
    return urllib.request.Request(
        f"https://api.stability.ai/v2beta/stable-image/generate/{endpoint}",
        data=body, method="POST",
        headers={"Authorization": f"Bearer {key}", "Accept": "image/*", "Content-Type": ctype})


def gen_stability(prompt, *, negative, ratio, seed, model, key, count):
    out = []
    for i in range(count):
        data, ctype = _http(stability_request(prompt, negative=negative, ratio=ratio,
                                              seed=seed + i, model=model, key=key))
        out.append(_check_image(data, ctype))
    return out


_GENERATORS = {"pollinations": gen_pollinations, "openai": gen_openai,
               "gemini": gen_gemini, "stability": gen_stability}


def generate(provider, prompt, *, negative="", ratio="1:1", seed=-1, model="", key="", count=1):
    """เจนรูป คืน (list ของ bytes รูป, seed ที่ใช้จริง).

    ตรวจค่าก่อนยิงเน็ต — prompt ว่าง / ไม่มีคีย์ / ผู้ให้บริการไม่รู้จัก ขึ้น CloudError ทันที."""
    if provider not in PROVIDERS:
        raise CloudError(f"ไม่รู้จักผู้ให้บริการ: {provider}")
    prompt = (prompt or "").strip()
    if not prompt:
        raise CloudError("พิมพ์คำบรรยายภาพก่อน")
    info = PROVIDERS[provider]
    key = resolve_key(provider, key)
    if info["key_required"] and not key:
        raise CloudError(f"{info['label']} ต้องใส่คีย์ API ก่อน (หรือตั้งตัวแปร {info['env']})\n"
                         f"ขอคีย์ได้ที่ {info['key_url']}")
    try:
        count = int(count)
    except (TypeError, ValueError):
        count = 1
    count = max(1, min(count, info["max_count"]))
    seed = _seed(seed)
    negative = (negative or "").strip() if info["negative"] else ""
    imgs = _GENERATORS[provider](prompt, negative=negative, ratio=_ratio(ratio), seed=seed,
                                 model=(model or "").strip() or info["models"][0], key=key, count=count)
    return imgs, seed
