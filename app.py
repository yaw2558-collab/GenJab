"""เจนจ๊าบ GenJab — หน้าต่างโปรแกรมเจนรูปจากข้อความ (รันบนเครื่อง)."""
import json
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image
from send2trash import send2trash

from generate import (RATIOS, VIDEO_MODELS, GenerationCancelled, list_loras,
                      resolve_size, txt2img, txt2img_batch, txt2vid)
from sysmon import SysMon

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

OUT_DIR = "out"
SETTINGS_FILE = "settings.json"
ACCENT = "#D97A2B"
ACCENT_HOVER = "#E8933F"
TITLE_FONT = ("Segoe UI", 26, "bold")
HEAD_FONT = ("Segoe UI", 12, "bold")
BODY_FONT = ("Segoe UI", 12)
MODEL_IDS = {"SD-Turbo (เร็ว ~4 วิ)": "sd-turbo", "SDXL-Turbo (1024px เร็ว)": "sdxl-turbo",
             "SDXL Base (1024px ละเอียด)": "sdxl-base",
             "Anima Turbo (สวย ~45 วิ)": "anima-turbo",
             "Anima Base (คมชัด)": "anima-base", "Anima Aesthetic (เน้นสวย)": "anima-aesthetic",
             "Qwen 2.1 (1024px ช้า ~9 นาที)": "qwen21",
             "Iris 3B (ภาพใหญ่ ช้า)": "iris-3b",
             "Wan2.2 5B (วิดีโอ)": "wan22-5b",
             "MiniMax-H3 (วิดีโอ ช้ามาก)": "minimax-h3"}
MODEL_SIZES = {"sd-turbo": ["256", "512", "768", "1024"],
               "anima-turbo": ["256", "512", "768", "1024", "1344"],
               "sdxl-turbo": ["512", "768", "1024"],
               "sdxl-base": ["512", "768", "1024"],
               "anima-base": ["256", "512", "768", "1024"],
               "anima-aesthetic": ["256", "512", "768", "1024"],
               "qwen21": ["512", "768", "1024"],
               "iris-3b": ["512", "768", "1024", "1344"],
               "wan22-5b": ["256", "480", "704", "1280"],
               "minimax-h3": ["256", "480", "864"]}


def next_path(out_dir):
    """คืน path ไฟล์รูปถัดไป (picNNN.png) ในโฟลเดอร์ที่เลือก — ไม่ชนชื่อเดิม."""

    return next_paths(out_dir, 1)[0]


def next_paths(out_dir, n, prefix="pic", ext=".png"):
    """จองชื่อไฟล์ทีเดียว n ชื่อ (picNNN.. / vidNNN..) — กันนับซ้ำตอนโฟลเดอร์เน็ตเวิร์กเห็นไฟล์ช้า."""
    try:
        taken = {f for f in os.listdir(out_dir) if f.endswith(ext)}
    except OSError:
        taken = set()
    paths, i = [], 1
    while len(paths) < n:
        name = f"{prefix}{i:03d}{ext}"
        if name not in taken:
            paths.append(os.path.join(out_dir, name))
            taken.add(name)
        i += 1
    return paths


DEFAULT_PROMPT = "a cute robot holding a red umbrella, digital art"


def default_settings():
    """ค่าเริ่มต้นทั้งหมด — ใช้ตอนยังไม่เคยจำ + เป็นฐานเวลาอ่านไฟล์."""
    return {"prompt": DEFAULT_PROMPT, "negative": "", "model": "sd-turbo",
            "size": "512", "ratio": "1:1", "count": "1", "lora": "(ไม่ใช้)",
            "lora_strength": 1.0, "steps": 4, "cfg": 1.0, "seed": "",
            "out_dir": ""}


def load_settings():
    """อ่าน settings ที่จำไว้ทั้งชุด — คีย์ไหนหาย/ไฟล์พังใช้ default ข้อนั้น."""
    d = default_settings()
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            saved = json.load(f)
    except (OSError, ValueError):
        return d
    if isinstance(saved, dict):
        for k in d:
            if k in saved:
                d[k] = saved[k]
    return d


def save_settings(d):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def _num(v, default, lo, hi):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    if f != f:  # NaN
        return default
    return min(hi, max(lo, f))


def normalize_settings(d):
    """ตรวจชนิด/ช่วงรายข้อ — ค่าพังกลับไปใช้ default ข้อนั้น (ไม่ทิ้งทั้งชุด)."""
    base = default_settings()
    if not isinstance(d, dict):
        return base
    s = dict(base)
    if "prompt" in d:
        s["prompt"] = str(d["prompt"])
    if "negative" in d:
        s["negative"] = str(d["negative"])
    mid = d.get("model", "")
    s["model"] = mid if mid in MODEL_IDS.values() else "sd-turbo"
    sizes = MODEL_SIZES[s["model"]]
    s["size"] = str(d.get("size", "")) if str(d.get("size", "")) in sizes else "512"
    s["ratio"] = d.get("ratio", "") if d.get("ratio", "") in RATIOS else "1:1"
    s["count"] = d.get("count", "") if d.get("count", "") in ("1", "2", "4") else "1"
    if "lora" in d:
        s["lora"] = str(d["lora"])
    s["lora_strength"] = _num(d.get("lora_strength"), 1.0, 0.1, 2.0)
    s["steps"] = int(_num(d.get("steps"), 4, 1, 30))
    s["cfg"] = _num(d.get("cfg"), 1.0, 1.0, 7.0)
    if "seed" in d:
        s["seed"] = str(d["seed"])
    if "out_dir" in d:
        s["out_dir"] = str(d["out_dir"])
    return s


def next_vid_path(out_dir):
    """คืน path ไฟล์วิดีโอถัดไป (vidNNN.webm) ในโฟลเดอร์ที่เลือก — ไม่ชนชื่อเดิม."""
    return next_vid_paths(out_dir, 1)[0]


def next_vid_paths(out_dir, n):
    """จองชื่อไฟล์วิดีโอทีเดียว n ชื่อ (vidNNN.webm)."""
    return next_paths(out_dir, n, "vid", ".webm")


def load_out_dir():
    """อ่านที่เก็บรูปที่จำไว้ — ไฟล์หาย/พัง หรือโฟลเดอร์ไม่อยู่แล้ว กลับไปใช้ out."""
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            d = json.load(f).get("out_dir", "")
        if d and os.path.isdir(d):
            return os.path.normpath(d)
    except (OSError, ValueError):
        pass
    return OUT_DIR


def save_out_dir(out_dir):
    d = load_settings()
    d["out_dir"] = out_dir
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:


            json.dump(d, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


GALLERY_LIMIT = 40


def load_gallery_thumbs(paths, size=84):
    """เปิด+ย่อรูปทีละไฟล์ คืน [(path, PIL.Image)] — ไม่แตะ Tk รันใน worker thread ได้."""
    thumbs = []
    for path in paths:
        try:
            with Image.open(path) as im:
                thumb = im.convert("RGB")
                thumb.thumbnail((size, size))
                thumbs.append((path, thumb))
        except Exception:  # noqa: BLE001, PERF203
            continue
    return thumbs


def fit_size(img_w, img_h, box_w, box_h):
    """ขนาดย่อรูปลงกล่องโดยคงสัดส่วน — คืน (w, h) อย่างน้อย 1px."""
    scale = min(box_w / img_w, box_h / img_h)
    return (max(1, int(img_w * scale)), max(1, int(img_h * scale)))


def ctk_image_size(img_w, img_h, box_w, box_h, scaling=1.0):
    """ขนาด CTkImage (logical) จากกล่อง physical — หาร scaling ก่อน fit กันรูปใหญ่เกินจอที่สเกล >100%."""
    if not scaling or scaling <= 0:
        scaling = 1.0
    return fit_size(img_w, img_h, box_w / scaling, box_h / scaling)


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("เจนจ๊าบ GenJab")
        self.geometry("1040x720")
        self.minsize(900, 640)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.main_img = None
        self.current_img = None
        self._resize_job = None
        self.thumb_refs = []
        self.current_path = None
        self.out_dir = load_out_dir()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # ---- ซ้าย: แผงควบคุม ----
        side = ctk.CTkScrollableFrame(self, width=300, corner_radius=0)
        side.grid(row=0, column=0, sticky="ns")


        ctk.CTkLabel(side, text="เจนจ๊าบ", font=TITLE_FONT, text_color=ACCENT).pack(anchor="w", padx=16, pady=(14, 0))
        ctk.CTkLabel(side, text="GenJab — เจนรูปฟรีบนเครื่อง", font=BODY_FONT).pack(anchor="w", padx=16, pady=(0, 10))

        ctk.CTkLabel(side, text="คำบรรยายภาพ (English)", font=HEAD_FONT).pack(anchor="w", padx=16)
        self.prompt = ctk.CTkTextbox(side, height=70, font=BODY_FONT)
        self.prompt.pack(fill="x", padx=16, pady=(0, 8))
        self.prompt.insert("1.0", DEFAULT_PROMPT)

        ctk.CTkLabel(side, text="Negative (ดัน CFG > 1 ถึงมีผล)", font=HEAD_FONT).pack(anchor="w", padx=16)
        self.negative = ctk.CTkTextbox(side, height=44, font=BODY_FONT)
        self.negative.pack(fill="x", padx=16, pady=(0, 8))

        ctk.CTkLabel(side, text="โมเดล", font=HEAD_FONT).pack(anchor="w", padx=16)
        self.model = ctk.CTkOptionMenu(side, values=list(MODEL_IDS), command=self.on_model_change,
                                       font=BODY_FONT, width=268)
        self.model.pack(padx=16, pady=(0, 8))

        self.size_label = ctk.CTkLabel(side, text="ขนาดรูป (ด้านยาว)", font=HEAD_FONT)
        self.size_label.pack(anchor="w", padx=16)
        self.size = ctk.CTkSegmentedButton(side, values=["256", "512", "768", "1024"], font=BODY_FONT)
        self.size.set("512")
        self.size.pack(fill="x", padx=16, pady=(0, 8))
        ctk.CTkLabel(side, text="สัดส่วน (3:4/9:16 แนวตั้ง · 16:9 แนวนอน)", font=HEAD_FONT).pack(anchor="w", padx=16)
        self.ratio = ctk.CTkSegmentedButton(side, values=sorted(RATIOS), font=BODY_FONT)
        self.ratio.set("1:1")
        self.ratio.pack(fill="x", padx=16, pady=(0, 8))

        ctk.CTkLabel(side, text="เฟรมวิดีโอ (เฉพาะโมเดลวิดีโอ)", font=HEAD_FONT).pack(anchor="w", padx=16)
        self.frames = ctk.CTkSegmentedButton(side, values=["9", "17", "33", "56", "81", "121"],
                                             font=BODY_FONT)
        self.frames.set("17")
        self.frames.pack(fill="x", padx=16, pady=(0, 8))
        ctk.CTkLabel(side, text="FPS วิดีโอ", font=HEAD_FONT).pack(anchor="w", padx=16)
        self.fps = ctk.CTkSegmentedButton(side, values=["16", "24"], font=BODY_FONT)
        self.fps.set("24")
        self.fps.pack(fill="x", padx=16, pady=(0, 8))

        ctk.CTkLabel(side, text="จำนวนรูป", font=HEAD_FONT).pack(anchor="w", padx=16)
        self.count = ctk.CTkSegmentedButton(side, values=["1", "2", "4"], font=BODY_FONT)
        self.count.set("1")
        self.count.pack(fill="x", padx=16, pady=(0, 8))

        ctk.CTkLabel(side, text="LoRA (ต้องตรงรุ่นโมเดล)", font=HEAD_FONT).pack(anchor="w", padx=16)
        try:
            lora_names = sorted(list_loras())
        except OSError:
            lora_names = []
        self.lora = ctk.CTkOptionMenu(side, values=["(ไม่ใช้)"] + lora_names,
                                     font=BODY_FONT, width=268)
        self.lora.pack(padx=16, pady=(0, 8))
        self._lora_names = ["(ไม่ใช้)"] + lora_names
        lora_row = ctk.CTkFrame(side, fg_color="transparent")
        lora_row.pack(fill="x", padx=16)
        ctk.CTkLabel(lora_row, text="แรง LoRA", font=HEAD_FONT).pack(side="left")
        self.lora_val = ctk.CTkLabel(lora_row, text="1.0", font=BODY_FONT, width=30)
        self.lora_val.pack(side="right")
        self.lora_strength = ctk.CTkSlider(side, from_=0.1, to=2.0, number_of_steps=19,
                                          command=self.on_lora)
        self.lora_strength.set(1.0)
        self.lora_strength.pack(fill="x", padx=16, pady=(0, 6))

        steps_row = ctk.CTkFrame(side, fg_color="transparent")
        steps_row.pack(fill="x", padx=16)
        ctk.CTkLabel(steps_row, text="Steps", font=HEAD_FONT).pack(side="left")
        self.steps_val = ctk.CTkLabel(steps_row, text="4", font=BODY_FONT, width=30)
        self.steps_val.pack(side="right")
        self.steps = ctk.CTkSlider(side, from_=1, to=30, number_of_steps=29, command=self.on_steps)
        self.steps.set(4)
        self.steps.pack(fill="x", padx=16, pady=(0, 6))

        cfg_row = ctk.CTkFrame(side, fg_color="transparent")
        cfg_row.pack(fill="x", padx=16)
        ctk.CTkLabel(cfg_row, text="CFG", font=HEAD_FONT).pack(side="left")
        self.cfg_val = ctk.CTkLabel(cfg_row, text="1.0", font=BODY_FONT, width=30)
        self.cfg_val.pack(side="right")
        self.cfg = ctk.CTkSlider(side, from_=1.0, to=7.0, number_of_steps=60, command=self.on_cfg)
        self.cfg.set(1.0)
        self.cfg.pack(fill="x", padx=16, pady=(0, 6))

        ctk.CTkLabel(side, text="Seed (ว่าง = สุ่มใหม่ทุกรูป)", font=HEAD_FONT).pack(anchor="w", padx=16)
        seed_row = ctk.CTkFrame(side, fg_color="transparent")
        seed_row.pack(fill="x", padx=16, pady=(0, 10))
        self.seed = ctk.CTkEntry(seed_row, font=BODY_FONT, placeholder_text="ว่าง = สุ่ม")
        self.seed.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(seed_row, text="สุ่ม", width=60, command=lambda: self.seed.delete(0, tk.END)).pack(side="right")

        ctk.CTkLabel(side, text="ที่เก็บรูป", font=HEAD_FONT).pack(anchor="w", padx=16)
        save_row = ctk.CTkFrame(side, fg_color="transparent")
        save_row.pack(fill="x", padx=16, pady=(0, 10))
        self.out_label = ctk.CTkLabel(save_row, text=self.out_dir, font=BODY_FONT, anchor="w",
                                      wraplength=180, justify="left")
        self.out_label.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(save_row, text="เลือก...", width=70, command=self.on_pick_dir).pack(side="right")

        type_row = ctk.CTkFrame(side, fg_color="transparent")
        type_row.pack(fill="x", padx=16, pady=(0, 10))
        self.out_entry = ctk.CTkEntry(type_row, font=BODY_FONT,
                                      placeholder_text="วาง path โฟลเดอร์ตรง ๆ ได้")
        self.out_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(type_row, text="ใช้", width=70, command=self.on_use_typed_dir).pack(side="right")

        self.btn = ctk.CTkButton(side, text="เจนรูป", font=("Segoe UI", 15, "bold"), height=42,
                                 fg_color=ACCENT, hover_color=ACCENT_HOVER, command=self.on_generate)
        self.btn.pack(fill="x", padx=16, pady=(0, 8))

        self.cancel_btn = ctk.CTkButton(side, text="ยกเลิก",
                                        font=("Segoe UI", 13, "bold"), height=36,
                                        fg_color="#8A2E2E", hover_color="#A63A3A",
                                        command=self.on_cancel, state="disabled")
        self.cancel_btn.pack(fill="x", padx=16, pady=(0, 8))
        self.cancel_event = None

        self.progress = ctk.CTkProgressBar(side, mode="indeterminate")
        self.progress.pack(fill="x", padx=16, pady=(0, 6))
        self.progress.stop()
        self.status = ctk.CTkLabel(side, text="พร้อม — เลือกโมเดลแล้วกดเจนรูป", font=BODY_FONT,
                                   wraplength=268, justify="left")
        self.status.pack(anchor="w", padx=16, pady=(0, 10))

        ctk.CTkLabel(side, text="การใช้งานเครื่อง", font=HEAD_FONT).pack(anchor="w", padx=16)
        self.mon = SysMon()
        self.meters = {}
        for key, label in (("cpu", "CPU"), ("gpu", "GPU"), ("ram", "RAM")):
            row = ctk.CTkFrame(side, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=(0, 2))
            ctk.CTkLabel(row, text=label, font=BODY_FONT, width=34).pack(side="left")
            bar = ctk.CTkProgressBar(row, height=8)
            bar.set(0)
            bar.pack(side="left", fill="x", expand=True, padx=(4, 4))
            val = ctk.CTkLabel(row, text="—", font=BODY_FONT, width=104, anchor="e")
            val.pack(side="right")
            self.meters[key] = (bar, val)

        self.after(2000, self.tick_mon)

        # ---- ขวา: รูป + แกลเลอรี ----
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew", padx=12, pady=12)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)

        topbar = ctk.CTkFrame(main, fg_color="transparent")
        topbar.grid(row=0, column=0, sticky="ew")
        self.img_name = ctk.CTkLabel(topbar, text="—", font=HEAD_FONT)
        self.img_name.pack(side="left")
        ctk.CTkButton(topbar, text="ลบรูปนี้", font=BODY_FONT, width=90,
                      fg_color="#8A2E2E", hover_color="#A63A3A", command=self.on_delete).pack(side="right")
        self.canvas = ctk.CTkLabel(main, text="กด \"เจนรูป\" เพื่อเริ่มต้น", font=("Segoe UI", 14))
        self.canvas.grid(row=1, column=0, sticky="nsew")
        self.canvas.bind("<Configure>", self.on_canvas_resize)

        ctk.CTkLabel(main, text="รูปที่เคยเจน", font=HEAD_FONT).grid(row=2, column=0, sticky="w", pady=(8, 4))
        self.gallery = ctk.CTkScrollableFrame(main, orientation="horizontal", height=110)
        self.gallery.grid(row=3, column=0, sticky="ew")
        self._gallery_pending = None
        self.after(100, self._gallery_poll)
        self.refresh_gallery()

        self._restore_settings()

    def collect_settings(self):
        """อ่านค่าปัจจุบันจากวิดเจ็ตเป็น dict — ตรงกับค่าที่ใช้เจนจริง."""
        return {
            "prompt": self.prompt.get("1.0", "end").strip(),
            "negative": self.negative.get("1.0", "end").strip(),
            "model": MODEL_IDS.get(self.model.get(), "sd-turbo"),
            "size": self.size.get(),
            "ratio": self.ratio.get(),
            "count": self.count.get(),
            "lora": self.lora.get(),
            "lora_strength": round(float(self.lora_strength.get()), 2),
            "steps": int(round(self.steps.get())),
            "cfg": round(float(self.cfg.get()), 1),
            "seed": self.seed.get().strip(),
            "out_dir": self.out_dir,
        }

    def save_current_settings(self):
        save_settings(self.collect_settings())

    def _restore_settings(self):
        """คืนพรอม+การตั้งค่าล่าสุดลงวิดเจ็ต — เรียกครั้งเดียวตอนเปิดโปรแกรม."""
        s = normalize_settings(load_settings())
        self.prompt.delete("1.0", "end")
        self.prompt.insert("1.0", s["prompt"])
        self.negative.delete("1.0", "end")
        self.negative.insert("1.0", s["negative"])
        label = next((k for k, v in MODEL_IDS.items() if v == s["model"]),
                     list(MODEL_IDS)[0])
        self.model.set(label)
        self.size.configure(values=MODEL_SIZES[s["model"]])
        self.size.set(s["size"])
        self.ratio.set(s["ratio"])
        self.count.set(s["count"])
        self.lora.set(s["lora"] if s["lora"] in self._lora_names else "(ไม่ใช้)")
        self.lora_strength.set(s["lora_strength"])
        self.lora_val.configure(text=f"{s['lora_strength']:.1f}")
        self.steps.set(s["steps"])
        self.steps_val.configure(text=str(s["steps"]))
        self.cfg.set(s["cfg"])
        self.cfg_val.configure(text=f"{s['cfg']:.1f}")
        self.seed.delete(0, tk.END)
        self.seed.insert(0, s["seed"])

    def on_close(self):
        try:
            self.save_current_settings()
        finally:
            self.destroy()

    def on_steps(self, v):
        self.steps_val.configure(text=str(int(round(float(v)))))

    def on_cfg(self, v):
        self.cfg_val.configure(text=f"{float(v):.1f}")

    def on_model_change(self, choice):
        mid = MODEL_IDS.get(choice, "sd-turbo")
        self.size.configure(values=MODEL_SIZES[mid])
        if mid in ("anima-base", "anima-aesthetic"):
            self.steps.set(20)
            self.steps_val.configure(text="20")
            self.size.set("1024")
            self.cfg.set(6.0)
            self.cfg_val.configure(text="6.0")
        elif mid == "sdxl-turbo":
            self.steps.set(4)
            self.steps_val.configure(text="4")
            self.size.set("1024")
            self.cfg.set(1.0)
            self.cfg_val.configure(text="1.0")
        elif mid == "sdxl-base":
            self.steps.set(25)
            self.steps_val.configure(text="25")
            self.size.set("1024")
            self.cfg.set(6.0)
            self.cfg_val.configure(text="6.0")
        elif mid == "qwen21":
            self.steps.set(30)
            self.steps_val.configure(text="30")
            self.size.set("1024")
            self.cfg.set(4.0)
            self.cfg_val.configure(text="4.0")
        elif mid == "iris-3b":
            self.steps.set(30)
            self.steps_val.configure(text="30")
            self.size.set("1024")
            self.cfg.set(4.0)
            self.cfg_val.configure(text="4.0")
        elif mid == "wan22-5b":
            self.steps.set(30)
            self.steps_val.configure(text="30")
            self.size.set("704")
            self.cfg.set(5.0)
            self.cfg_val.configure(text="5.0")
            self.ratio.set("16:9")
            self.frames.set("17")
            self.fps.set("24")
        elif mid == "minimax-h3":
            self.steps.set(20)
            self.steps_val.configure(text="20")
            self.size.set("480")
            self.cfg.set(1.0)
            self.cfg_val.configure(text="1.0")
            self.ratio.set("16:9")
            self.frames.set("17")
            self.fps.set("24")
        elif mid == "anima-turbo":
            self.steps.set(8)
            self.steps_val.configure(text="8")
            self.size.set("1024")
            self.cfg.set(1.0)
            self.cfg_val.configure(text="1.0")
        else:
            self.steps.set(4)
            self.steps_val.configure(text="4")
            self.size.set("512")
        if mid in VIDEO_MODELS:
            self.btn.configure(text="เจนวิดีโอ")
            self.size_label.configure(text="ขนาดวิดีโอ (ด้านยาว)")
        else:
            self.btn.configure(text="เจนรูป")
            self.size_label.configure(text="ขนาดรูป (ด้านยาว)")

    def set_meter(self, key, pct, text):
        bar, val = self.meters[key]
        bar.set(max(0.0, min(1.0, (pct or 0) / 100)))
        val.configure(text=text)

    def tick_mon(self):
        try:
            s = self.mon.sample()
        except Exception:  # noqa: BLE001
            s = {}
        cpu, gpu, ram = s.get("cpu"), s.get("gpu"), s.get("ram")
        self.set_meter("cpu", cpu, "—" if cpu is None else f"{cpu:.0f}%")
        if gpu is None:
            self.set_meter("gpu", None, "—")
        elif s.get("vram_total_mb"):
            used = (s.get("vram_used_mb") or 0) / 1024
            self.set_meter("gpu", gpu, f"{gpu:.0f}% {used:.1f}/{s['vram_total_mb'] / 1024:.0f}G")
        else:
            self.set_meter("gpu", gpu, f"{gpu:.0f}%")
        if ram is None:
            self.set_meter("ram", None, "—")
        else:
            used = (s.get("ram_used_mb") or 0) / 1024
            self.set_meter("ram", ram, f"{ram:.0f}% {used:.1f}/{s['ram_total_mb'] / 1024:.0f}G")
        self.after(2000, self.tick_mon)

    def on_canvas_resize(self, event):
        if self.current_img is None:
            return
        if self._resize_job is not None:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(200, self._refit)

    def _refit(self):
        self._resize_job = None
        if self.current_img is not None:
            self.display(self.current_img, self.img_name.cget("text"))

    def on_lora(self, v):
        self.lora_val.configure(text=f"{float(v):.1f}")

    def apply_out_dir(self, d):
        """ตรวจแล้วใช้โฟลเดอร์เก็บรูป คืน True ถ้าสำเร็จ — ปุ่มเลือก/พิมพ์เองใช้ร่วมกัน."""
        d = os.path.normpath(d)
        if not os.path.isdir(d):
            self.status.configure(text="โฟลเดอร์นี้ไม่มี — ตรวจ path อีกครั้ง")
            return False
        self.out_dir = d
        save_out_dir(self.out_dir)
        self.out_label.configure(text=self.out_dir)
        self.status.configure(text=f"ที่เก็บรูป: {self.out_dir}")
        self.refresh_gallery()
        return True

    def on_pick_dir(self):
        start = self.out_dir if os.path.isdir(self.out_dir) else None
        d = filedialog.askdirectory(parent=self, initialdir=start,
                                    title="เลือกที่เก็บรูป", mustexist=True)
        if not d:
            return
        self.apply_out_dir(d)

    def on_use_typed_dir(self):
        d = self.out_entry.get().strip().strip('"')
        if not d:
            self.status.configure(text="วาง path โฟลเดอร์ก่อนแล้วกด ใช้")
            return
        if self.apply_out_dir(d):
            self.out_entry.delete(0, tk.END)

    def on_generate(self):
        prompt = self.prompt.get("1.0", "end").strip()
        if not prompt:
            messagebox.showwarning("เตือน", "พิมพ์คำบรรยายก่อน")
            return
        steps = int(round(self.steps.get()))
        try:
            size = int(self.size.get())
        except ValueError:
            size = 512
        cfg = round(float(self.cfg.get()), 1)
        seed_txt = self.seed.get().strip()
        seed = int(seed_txt) if seed_txt.lstrip("-").isdigit() else None
        negative = self.negative.get("1.0", "end").strip()
        model = MODEL_IDS.get(self.model.get(), "sd-turbo")
        ratio = self.ratio.get()
        if ratio not in RATIOS:
            ratio = "1:1"
        lora = self.lora.get()
        if lora == "(ไม่ใช้)":
            lora = None
        lora_strength = round(float(self.lora_strength.get()), 2)
        try:
            count = int(self.count.get())
        except ValueError:
            count = 1
        self.save_current_settings()
        self.cancel_event = threading.Event()
        self.cancel_btn.configure(state="normal")
        try:
            frames = int(self.frames.get())
        except ValueError:
            frames = 17
        try:
            fps = int(self.fps.get())
        except ValueError:
            fps = 24
        if model in VIDEO_MODELS:
            if lora:
                messagebox.showwarning("เตือน", "โมเดลวิดีโอไม่รองรับ LoRA — เลือก (ไม่ใช้) ก่อน")
                return
            w, h = resolve_size(size, ratio)
            self.btn.configure(state="disabled")
            self.status.configure(text="กำลังเจนวิดีโอ..." if count <= 1 else f"กำลังเจน {count} คลิป...")
            self.progress.start()
            threading.Thread(target=self.work_video,
                             args=(prompt, steps, seed, w, h, frames, fps, cfg, negative, model, count,
                                             self.cancel_event),
                             daemon=True).start()
            return
        self.btn.configure(state="disabled")
        self.status.configure(text="กำลังเจน..." if count <= 1 else f"กำลังเจน {count} รูป...")
        self.progress.start()
        threading.Thread(target=self.work, args=(prompt, steps, seed, size, cfg, negative, model, count, ratio,
                                                 lora, lora_strength, self.cancel_event),
                         daemon=True).start()

    def on_cancel(self):
        """User pressed cancel - tell the worker to kill sd-cli and end as cancelled."""
        if self.cancel_event is None:
            return
        self.cancel_event.set()
        self.status.configure(text="กำลังยกเลิก...")


    def _gen_done(self):
        """Restore buttons after finish/fail/cancel - gen back on, cancel off."""
        self.btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")
        self.cancel_event = None
        self.progress.stop()


    def show_cancelled(self):
        """Job was cancelled - show status instead of error popup."""
        self.status.configure(text="ยกเลิกแล้ว")
        self._gen_done()


    def work_video(self, prompt, steps, seed, width, height, frames, fps, cfg, negative, model,
                   count=1, cancel_event=None):
        try:
            out_dir = self.out_dir
            os.makedirs(out_dir, exist_ok=True)
            paths = next_vid_paths(out_dir, count)
            saved = []
            for i, path in enumerate(paths):
                s = (seed + i) % 2**31 if seed is not None else None
                out, used_seed = txt2vid(prompt, model=model, seed=s, width=width, height=height,
                                         frames=frames, fps=fps, steps=steps, guidance=cfg,
                                         negative=negative, output=path, cancel_event=cancel_event)
                saved.append((out, used_seed))
            self.after(0, self.show_video_result, saved, width, height, frames)
        except GenerationCancelled:
            for p in paths:
                try:
                    if os.path.isfile(p):
                        os.remove(p)
                except OSError:
                    pass
            self.after(0, self.show_cancelled)
        except Exception as e:  # noqa: BLE001
            self.after(0, self.show_error, str(e))

    def show_video_result(self, saved, width, height, frames):
        path, used_seed = saved[0]
        name = os.path.basename(path)
        self.current_img = None
        self.main_img = None
        self.canvas.configure(image=None, text=f"วิดีโอเซฟแล้ว\n{name}\nเปิดด้วย player ดูได้เลย")
        self.img_name.configure(text=name)
        if len(saved) > 1:
            self.status.configure(
                text=f"เสร็จ! {len(saved)} คลิป {width}x{height} {frames}f (seed {saved[0][1]}–{saved[-1][1]})")
        else:
            self.status.configure(text=f"เสร็จ! {name} {width}x{height} {frames}f (seed {used_seed})")
        self.seed.delete(0, tk.END)
        self.seed.insert(0, str(used_seed))
        self._gen_done()
        self.progress.stop()

    def work(self, prompt, steps, seed, size, cfg, negative, model, count=1, ratio="1:1",
             lora=None, lora_strength=1.0, cancel_event=None):
        try:
            out_dir = self.out_dir
            os.makedirs(out_dir, exist_ok=True)
            if count > 1:
                results = txt2img_batch(prompt, n=count, steps=steps, seed=seed, size=size, ratio=ratio,
                                        lora=lora, lora_strength=lora_strength,
                                        guidance=cfg, negative=negative, model=model,
                                        cancel_event=cancel_event)
                paths = next_paths(out_dir, len(results))
                saved = []
                for (img, used_seed), path in zip(results, paths):

                    img.save(path)
                    saved.append((img, path, used_seed))
                self.after(0, self.show_batch_result, saved)
                return
            img, used_seed = txt2img(prompt, steps=steps, seed=seed, size=size, ratio=ratio, guidance=cfg,
                                     lora=lora, lora_strength=lora_strength,
                                     negative=negative, model=model, cancel_event=cancel_event)
            path = next_path(out_dir)
            img.save(path)
            self.after(0, self.show_result, img, path, used_seed)
        except GenerationCancelled:
            self.after(0, self.show_cancelled)
        except Exception as e:  # noqa: BLE001
            self.after(0, self.show_error, str(e))

    def show_result(self, img, path, used_seed):
        self.current_path = path
        self.display(img, os.path.basename(path))
        self.status.configure(text=f"เสร็จ! {os.path.basename(path)} {img.size[0]}x{img.size[1]} (seed {used_seed})")
        self.seed.delete(0, tk.END)
        self.seed.insert(0, str(used_seed))
        self._gen_done()
        self.progress.stop()
        self.refresh_gallery()

    def show_batch_result(self, saved):
        img, path, used_seed = saved[0]
        self.current_path = path
        self.display(img, os.path.basename(path))
        last_seed = saved[-1][2]
        self.status.configure(text=f"เสร็จ! {len(saved)} รูป {img.size[0]}x{img.size[1]} (seed {used_seed}–{last_seed})")
        self.seed.delete(0, tk.END)
        self.seed.insert(0, str(used_seed))
        self._gen_done()
        self.progress.stop()
        self.refresh_gallery()

    def show_error(self, msg):
        self.status.configure(text="เกิดข้อผิดพลาด")
        self._gen_done()
        self.progress.stop()
        messagebox.showerror("ผิดพลาด", msg[:500])

    def display(self, img, name):
        self.current_img = img
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        if cw < 50 or ch < 50:  # ยังจัด layout ไม่เสร็จ ใช้ค่าเดิม
            cw, ch = 560, 560
        try:
            scaling = ctk.ScalingTracker.get_widget_scaling(self.canvas)
        except Exception:  # noqa: BLE001
            scaling = 1.0
        self.main_img = ctk.CTkImage(light_image=img, dark_image=img,
                                     size=ctk_image_size(img.size[0], img.size[1], cw, ch, scaling))
        self.canvas.configure(image=self.main_img, text="")
        self.img_name.configure(text=name)

    def view_image(self, path):
        try:
            self.display(Image.open(path).convert("RGB"), os.path.basename(path))
            self.current_path = path
        except Exception as e:  # noqa: BLE001
            self.status.configure(text=f"เปิดรูปไม่ได้: {e}")

    def on_delete(self):
        if not self.current_path or not os.path.isfile(self.current_path):
            self.status.configure(text="ไม่มีรูปให้ลบ")
            return
        name = os.path.basename(self.current_path)
        if not messagebox.askyesno("ยืนยัน", f"ลบ {name} ไปถังขยะ?"):
            return
        try:
            send2trash(self.current_path)
        except Exception as e:  # noqa: BLE001
            self.status.configure(text=f"ลบไม่ได้: {e}")
            return
        self.current_path = None
        self.status.configure(text=f"ลบ {name} แล้ว (กู้ได้จากถังขยะ)")
        self.refresh_gallery()
        files = self.recent_files()
        if files:
            self.view_image(files[0])
        else:
            self.canvas.configure(image=None, text="กด \"เจนรูป\" เพื่อเริ่มต้น")
            self.img_name.configure(text="—")
            self.current_img = None

    def recent_files(self):
        try:
            return sorted((os.path.join(self.out_dir, f) for f in os.listdir(self.out_dir) if f.endswith(".png")),
                           key=os.path.getmtime, reverse=True)
        except FileNotFoundError:
            return []

    def refresh_gallery(self):
        self._gallery_token = getattr(self, "_gallery_token", 0) + 1
        threading.Thread(target=self._gallery_work,
                         args=(self.out_dir, self._gallery_token), daemon=True).start()

    def _gallery_work(self, out_dir, token):
        try:
            files = sorted((os.path.join(out_dir, f) for f in os.listdir(out_dir)
                            if f.endswith(".png")),
                           key=os.path.getmtime, reverse=True)[:GALLERY_LIMIT]
        except OSError:
            files = []
        thumbs = load_gallery_thumbs(files)
        self._gallery_pending = (thumbs, token)

    def _gallery_poll(self):
        pending = self._gallery_pending
        if pending is not None:
            self._gallery_pending = None
            self._gallery_done(*pending)
        self.after(100, self._gallery_poll)

    def _gallery_done(self, thumbs, token):
        if token != getattr(self, "_gallery_token", 0):
            return  # ผลจากรอบเก่า ทิ้งไป
        for w in self.gallery.winfo_children():
            w.destroy()
        self.thumb_refs = []
        if not thumbs:
            ctk.CTkLabel(self.gallery, text="ยังไม่มีรูป — กดเจนรูปเลย", font=BODY_FONT).pack(padx=8, pady=30)
            return
        for path, thumb in thumbs:
            cimg = ctk.CTkImage(light_image=thumb, dark_image=thumb,
                                size=fit_size(thumb.size[0], thumb.size[1], 84, 84))
            self.thumb_refs.append(cimg)
            ctk.CTkButton(self.gallery, image=cimg, text="", width=88, height=88,
                          fg_color="transparent", command=lambda p=path: self.view_image(p)).pack(
                              side="left", padx=4, pady=4)


def log_startup_error():
    """เขียน traceback ตอนเปิดโปรแกรมพังลง error.log — ใช้ตอนรันแบบไม่มีคอนโซล."""
    import traceback
    try:
        with open("error.log", "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
    except OSError:
        pass


if __name__ == "__main__":
    try:
        App().mainloop()
    except Exception:
        log_startup_error()
        raise
