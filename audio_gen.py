"""เพลงประกอบคลิป — เจนเพลงด้วย audio.cpp (มากับ Amuse 4.0) แล้วรวมเข้าคลิปด้วย ffmpeg.

โมเดล: Stable Audio 3 Small Music (`stable-audio-3-small-music-q8_0.gguf`) ใน models/audio/
ข้างโปรแกรม (หรือ env GENJAB_AUDIO_MODEL). ตัวรัน: audiocpp.dll ของ Amuse
(`RuntimeAudioCpp/vulkan`, หรือ env GENJAB_AUDIOCPP_DIR).

เรียก DLL ตรงผ่าน ctypes (ABI 0.4): registry → model_load → session("gen", "offline", vulkan)
→ request(text + options) → run → PCM float. ปล่อยโมเดลทิ้งหลังเจนทุกครั้ง (คืน VRAM ให้โมเดลรูป).
WAV เขียนเป็น float32 ตรง ๆ ไม่ต้องใช้ numpy — ffmpeg อ่านได้.
"""
import ctypes
import glob
import os
import re
import struct
import subprocess
import tempfile
import threading

AUDIOCPP_ENV = "GENJAB_AUDIOCPP_DIR"
AUDIO_MODEL_ENV = "GENJAB_AUDIO_MODEL"
AMUSE_AUDIOCPP = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Amuse", "RuntimeAudioCpp", "vulkan")
MUSIC_MODEL_GLOB = "stable-audio-3-small-music*.gguf"
MUSIC_HINT = ("ต้องมีโมเดลเพลง stable-audio-3-small-music-q8_0.gguf "
              "(huggingface.co/audio-cpp/audio.cpp-gguf โฟลเดอร์ Stable-Audio-3-Small-Music-GGUF) "
              "ใน models/audio/ ข้างโปรแกรม")
RUNTIME_HINT = "ต้องมี audio.cpp ของ Amuse 4.0 (%LOCALAPPDATA%\\Amuse\\RuntimeAudioCpp\\vulkan)"
MAX_SECS = 120  # Stable Audio 3 Small Music ยาวสุดตามค่าตั้งต้นของ Amuse
FADE_SECS = 1.5

SCOPE_REQUEST, SCOPE_SESSION, SCOPE_LOAD = 0, 1, 2

# ชื่อ option ที่อยากตั้ง → ชื่อที่อาจใช้จริงในแต่ละตระกูล (เลือกตัวแรกที่โมเดลประกาศไว้)
OPTION_ALIASES = {
    # stable_audio (audio.cpp 0.9.6) ประกาศ duration_sec / num_inference_steps / guidance_scale / seed
    "duration": ("duration_sec", "duration", "seconds", "audio_length", "duration_seconds", "length"),
    "steps": ("num_inference_steps", "steps", "num_steps", "inference_steps", "sample_steps"),
    "seed": ("seed",),
    "cfg": ("cfg_scale", "guidance_scale", "cfg", "guidance"),
    "negative": ("negative_prompt", "negative"),
}


class AudioError(RuntimeError):
    pass


def audiocpp_dir():
    env = os.environ.get(AUDIOCPP_ENV, "")
    d = env or AMUSE_AUDIOCPP
    return d if os.path.isfile(os.path.join(d, "audiocpp.dll")) else ""


def music_model():
    """path โมเดลเพลง — ไม่มีคืนสตริงว่าง."""
    env = os.environ.get(AUDIO_MODEL_ENV, "")
    if env:
        return env if os.path.isfile(env) else ""
    import generate
    cands = [os.path.join(generate.app_dir(), "models", "audio"),
             os.path.join(generate.AMUSE_MODELS, "audio"),
             os.path.join(generate.AMUSE_MODELS, "Audio")]
    for d in cands:
        hits = sorted(glob.glob(os.path.join(d, "**", MUSIC_MODEL_GLOB), recursive=True))
        if hits:
            return hits[0]
    return ""


def available():
    return bool(audiocpp_dir() and music_model())


# ---------------------------------------------------------------- ctypes
_LIB = None
_LIB_LOCK = threading.Lock()
_DLL_HANDLES = []


def _lib():
    """โหลด audiocpp.dll ครั้งเดียว + ประกาศชนิดฟังก์ชันที่ใช้."""
    global _LIB
    with _LIB_LOCK:
        if _LIB is not None:
            return _LIB
        d = audiocpp_dir()
        if not d:
            raise AudioError(RUNTIME_HINT)
        if hasattr(os, "add_dll_directory"):
            _DLL_HANDLES.append(os.add_dll_directory(d))
        L = ctypes.CDLL(os.path.join(d, "audiocpp.dll"))
        vp, cp, sz, i = ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t, ctypes.c_int
        P = ctypes.POINTER
        sig = {
            "audiocpp_abi_version": (ctypes.c_uint32, []),
            "audiocpp_last_error": (cp, []),
            "audiocpp_status_string": (cp, [i]),
            "audiocpp_options_create": (vp, []),
            "audiocpp_options_set": (i, [vp, cp, cp]),
            "audiocpp_options_free": (None, [vp]),
            "audiocpp_registry_create": (i, [cp, P(vp)]),
            "audiocpp_registry_free": (None, [vp]),
            "audiocpp_model_load": (i, [vp, cp, vp, vp, P(vp)]),
            "audiocpp_model_free": (None, [vp]),
            "audiocpp_model_family": (cp, [vp]),
            "audiocpp_model_supports": (i, [vp, cp, cp]),
            "audiocpp_model_option_count": (sz, [vp, i]),
            "audiocpp_model_option": (i, [vp, i, sz, P(cp), P(cp), P(cp), P(cp), P(cp), P(cp), P(i)]),
            "audiocpp_session_create": (i, [vp, cp, cp, vp, vp, P(vp)]),
            "audiocpp_session_free": (None, [vp]),
            "audiocpp_session_run": (i, [vp, vp, P(vp)]),
            "audiocpp_request_create": (vp, []),
            "audiocpp_request_free": (None, [vp]),
            "audiocpp_request_set_text": (i, [vp, cp, cp]),
            "audiocpp_request_set_option": (i, [vp, cp, cp]),
            "audiocpp_result_free": (None, [vp]),
            "audiocpp_result_audio": (i, [vp, P(P(ctypes.c_float)), P(sz), P(i), P(i)]),
        }
        for name, (res, args) in sig.items():
            f = getattr(L, name)
            f.restype = res
            f.argtypes = args
        _LIB = L
        return L


class _Backend(ctypes.Structure):
    _fields_ = [("backend", ctypes.c_char_p), ("device", ctypes.c_int), ("threads", ctypes.c_int)]


def _check(L, status, what):
    if status != 0:
        msg = (L.audiocpp_last_error() or b"").decode("utf-8", "replace")
        name = (L.audiocpp_status_string(status) or b"").decode("utf-8", "replace")
        raise AudioError(f"audio.cpp {what} ล้มเหลว ({name}): {msg}")


def model_options(L, model, scope=SCOPE_REQUEST):
    """{ชื่อ option: (ค่าตั้งต้น, min, max, คำอธิบาย)} ที่โมเดลประกาศไว้."""
    out = {}
    n = L.audiocpp_model_option_count(model, scope)
    for k in range(n):
        name, vname, desc, dflt, lo, hi = (ctypes.c_char_p() for _ in range(6))
        req = ctypes.c_int()
        if L.audiocpp_model_option(model, scope, k, ctypes.byref(name), ctypes.byref(vname),
                                   ctypes.byref(desc), ctypes.byref(dflt), ctypes.byref(lo),
                                   ctypes.byref(hi), ctypes.byref(req)) == 0 and name.value:
            dec = lambda c: (c.value or b"").decode("utf-8", "replace")  # noqa: E731
            out[dec(name)] = (dec(dflt), dec(lo), dec(hi), dec(desc))
    return out


def pick_options(declared, wanted):
    """จับคู่ค่าที่อยากตั้ง ({duration, steps, seed, cfg, negative}) กับชื่อที่โมเดลประกาศจริง.
    ไม่รู้ว่าโมเดลประกาศอะไร (declared ว่าง) ใช้ชื่อแรกของแต่ละตัว."""
    out = {}
    for key, value in wanted.items():
        if value is None or value == "":
            continue
        names = OPTION_ALIASES.get(key, (key,))
        name = next((n for n in names if n in declared), None) if declared else names[0]
        if name:
            out[name] = str(value)
    return out


def generate_music(prompt, seconds, out_wav, seed=None, steps=None, cfg=None, negative="",
                   model_path=None, backend="vulkan", cancel_event=None):
    """เจนเพลงจากคำบรรยาย ยาว seconds วิ เขียน WAV (float32) คืน (out_wav, sample_rate, channels).

    เรียก DLL ตรง ๆ (ctypes ปล่อย GIL ระหว่างรัน) — ยกเลิกกลางคันไม่ได้ เช็คก่อน/หลังเท่านั้น."""
    prompt = (prompt or "").strip()
    if not prompt:
        raise ValueError("พิมพ์คำบรรยายเพลงก่อน (ภาษาอังกฤษ เช่น 'upbeat thai folk music, ranat')")
    secs = float(seconds)
    if not 0 < secs <= MAX_SECS:
        raise ValueError(f"ความยาวเพลงต้องอยู่ระหว่าง 0..{MAX_SECS} วินาที (ได้ {seconds})")
    path = model_path or music_model()
    if not path:
        raise FileNotFoundError(MUSIC_HINT)
    if cancel_event is not None and cancel_event.is_set():
        from generate import GenerationCancelled
        raise GenerationCancelled()
    _free_gpu()
    L = _lib()
    reg, model, sess, req, res = (ctypes.c_void_p() for _ in range(5))
    try:
        _check(L, L.audiocpp_registry_create(None, ctypes.byref(reg)), "สร้าง registry")
        _check(L, L.audiocpp_model_load(reg, os.fsencode(path), None, None, ctypes.byref(model)),
               "โหลดโมเดล")
        if not L.audiocpp_model_supports(model, b"gen", b"offline"):
            fam = (L.audiocpp_model_family(model) or b"?").decode()
            raise AudioError(f"โมเดล {fam} เจนเพลง (gen) ไม่ได้")
        be = _Backend(backend.encode(), 0, max(1, min(8, os.cpu_count() or 4)))  # threads ต้อง > 0
        _check(L, L.audiocpp_session_create(model, b"gen", b"offline", ctypes.byref(be), None,
                                            ctypes.byref(sess)), "สร้าง session")
        req = ctypes.c_void_p(L.audiocpp_request_create())
        _check(L, L.audiocpp_request_set_text(req, prompt.encode("utf-8"), None), "ใส่คำบรรยาย")
        declared = model_options(L, model)
        opts = pick_options(declared, {"duration": f"{secs:g}", "steps": steps, "seed": seed,
                                       "cfg": cfg, "negative": negative})
        for k, v in opts.items():
            _check(L, L.audiocpp_request_set_option(req, k.encode(), v.encode()), f"ตั้งค่า {k}")
        _check(L, L.audiocpp_session_run(sess, req, ctypes.byref(res)), "เจนเพลง")
        samples = ctypes.POINTER(ctypes.c_float)()
        frames, rate, ch = ctypes.c_size_t(), ctypes.c_int(), ctypes.c_int()
        _check(L, L.audiocpp_result_audio(res, ctypes.byref(samples), ctypes.byref(frames),
                                          ctypes.byref(rate), ctypes.byref(ch)), "อ่านเสียง")
        n = frames.value * ch.value
        if n <= 0:
            raise AudioError("audio.cpp ไม่ได้ส่งเสียงกลับมา")
        raw = ctypes.string_at(samples, n * 4)
        write_wav_float(out_wav, raw, rate.value, ch.value)
        return out_wav, rate.value, ch.value
    finally:
        if res:
            L.audiocpp_result_free(res)
        if req:
            L.audiocpp_request_free(req)
        if sess:
            L.audiocpp_session_free(sess)
        if model:
            L.audiocpp_model_free(model)
        if reg:
            L.audiocpp_registry_free(reg)


def write_wav_float(path, raw, rate, channels):
    """WAV แบบ IEEE float 32 bit (format 3) จากไบต์ PCM แบบ interleaved."""
    data_len = len(raw)
    hdr = (b"RIFF" + struct.pack("<I", 36 + 14 + data_len) + b"WAVE"
           + b"fmt " + struct.pack("<IHHIIHHH", 18, 3, channels, rate,
                                   rate * channels * 4, channels * 4, 32, 0)
           + b"fact" + struct.pack("<II", 4, data_len // (4 * channels))
           + b"data" + struct.pack("<I", data_len))
    # fmt chunk ขนาด 18 (มี cbSize) + fact chunk — แบบที่ WAV float มาตรฐานใช้
    with open(path, "wb") as f:
        f.write(hdr)
        f.write(raw)
    return path


def _free_gpu():
    """คืน VRAM ก่อนเจนเพลง — ปิด sd-server และตัวแปลไทยที่เปิดค้างอยู่."""
    import sys
    for mod, attr in (("sd_server", "SERVER"), ("local_llm", "LLM")):
        m = sys.modules.get(mod)
        if m is not None:
            getattr(m, attr).stop()


# ---------------------------------------------------------------- ffmpeg
_DUR = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")


def media_seconds(path, ffmpeg=None):
    """ความยาวคลิป (วินาที) จาก ffmpeg -i — อ่านไม่ได้ raise."""
    import generate
    ff = ffmpeg or generate.resolve_ffmpeg()
    p = subprocess.run([ff, "-hide_banner", "-i", path], capture_output=True, text=True,
                       errors="replace", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    m = _DUR.search(p.stderr or "")
    if not m:
        raise AudioError(f"อ่านความยาวคลิปไม่ได้: {path}")
    h, mi, s = m.groups()
    return int(h) * 3600 + int(mi) * 60 + float(s)


def mux_args(ffmpeg, video, audio, out, secs, volume=1.0):
    """argv ffmpeg ใส่เพลงเข้าคลิป: ภาพเดิม (copy) + เพลงเฟดเข้า/ออก ตัดยาวเท่าคลิป."""
    ext = os.path.splitext(out)[1].lower()
    acodec = ["-c:a", "libopus", "-b:a", "160k"] if ext == ".webm" else ["-c:a", "aac", "-b:a", "192k"]
    fade_out_start = max(0.0, secs - FADE_SECS)
    af = (f"volume={volume:g},afade=t=in:st=0:d=0.5,"
          f"afade=t=out:st={fade_out_start:.2f}:d={FADE_SECS:g}")
    return [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", video, "-i", audio,
            "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy"] + acodec + [
            "-af", af, "-t", f"{secs:.3f}", out]


def music_out_path(video):
    """ชื่อไฟล์ผลลัพธ์ — ชื่อเดิม_music นามสกุลเดิม ไม่ทับของเดิม (ชนเติม _2, _3)."""
    base, ext = os.path.splitext(video)
    cand = f"{base}_music{ext}"
    k = 2
    while os.path.exists(cand):
        cand = f"{base}_music_{k}{ext}"
        k += 1
    return cand


def add_music_to_clip(video, prompt, seed=None, steps=None, cfg=None, negative="",
                      volume=1.0, cancel_event=None, out=None):
    """เจนเพลงยาวเท่าคลิปแล้วรวมเป็นไฟล์ใหม่ (ชื่อเดิม_music) คืน (path ผลลัพธ์, วินาที)."""
    import generate
    if not video or not os.path.isfile(video):
        raise FileNotFoundError(f"ไม่พบคลิป: {video}")
    ff = generate.resolve_ffmpeg()
    secs = media_seconds(video, ff)
    gen_secs = min(MAX_SECS, max(1.0, secs + 0.5))  # เผื่อปลายนิดหน่อยก่อนเฟด
    out = out or music_out_path(video)
    with tempfile.TemporaryDirectory() as td:
        wav = os.path.join(td, "music.wav")
        generate_music(prompt, gen_secs, wav, seed=seed, steps=steps, cfg=cfg,
                       negative=negative, cancel_event=cancel_event)
        if cancel_event is not None and cancel_event.is_set():
            raise generate.GenerationCancelled()
        p = subprocess.run(mux_args(ff, video, wav, out, min(secs, gen_secs), volume),
                           capture_output=True, text=True, errors="replace",
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if p.returncode != 0 or not os.path.isfile(out):
            raise AudioError(f"ffmpeg รวมเพลงเข้าคลิปไม่สำเร็จ:\n{(p.stderr or '')[-600:]}")
    return out, secs
