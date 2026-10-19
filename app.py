"""เจนจ๊าบ GenJab — หน้าต่างโปรแกรมเจนรูปจากข้อความ (รันบนเครื่อง)."""
import json
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image
from send2trash import send2trash

from generate import RATIOS, txt2img, txt2img_batch

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
             "Anima Turbo (สวย ~45 วิ)": "anima-turbo",
             "Anima Base (คมชัด)": "anima-base", "Anima Aesthetic (เน้นสวย)": "anima-aesthetic"}
MODEL_SIZES = {"sd-turbo": ["256", "512", "768", "1024"],
               "anima-turbo": ["256", "512", "768", "1024", "1344"],
               "sdxl-turbo": ["512", "768", "1024"],
               "anima-base": ["256", "512", "768", "1024"],
               "anima-aesthetic": ["256", "512", "768", "1024"]}


def next_path(out_dir):
    """คืน path ไฟล์รูปถัดไป (picNNN.png) ในโฟลเดอร์ที่เลือก — ไม่ชนชื่อเดิม."""
    n = len([f for f in os.listdir(out_dir) if f.endswith(".png")]) + 1
    return os.path.join(out_dir, f"pic{n:03d}.png")


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
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump({"out_dir": out_dir}, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("เจนจ๊าบ GenJab")
        self.geometry("1040x720")
        self.minsize(900, 640)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.main_img = None
        self.thumb_refs = []
        self.current_path = None
        self.out_dir = load_out_dir()

        # ---- ซ้าย: แผงควบคุม ----
        side = ctk.CTkFrame(self, width=300, corner_radius=0)
        side.grid(row=0, column=0, sticky="ns")
        side.grid_propagate(False)

        ctk.CTkLabel(side, text="เจนจ๊าบ", font=TITLE_FONT, text_color=ACCENT).pack(anchor="w", padx=16, pady=(14, 0))
        ctk.CTkLabel(side, text="GenJab — เจนรูปฟรีบนเครื่อง", font=BODY_FONT).pack(anchor="w", padx=16, pady=(0, 10))

        ctk.CTkLabel(side, text="คำบรรยายภาพ (English)", font=HEAD_FONT).pack(anchor="w", padx=16)
        self.prompt = ctk.CTkTextbox(side, height=70, font=BODY_FONT)
        self.prompt.pack(fill="x", padx=16, pady=(0, 8))
        self.prompt.insert("1.0", "a cute robot holding a red umbrella, digital art")

        ctk.CTkLabel(side, text="Negative (ดัน CFG > 1 ถึงมีผล)", font=HEAD_FONT).pack(anchor="w", padx=16)
        self.negative = ctk.CTkTextbox(side, height=44, font=BODY_FONT)
        self.negative.pack(fill="x", padx=16, pady=(0, 8))

        ctk.CTkLabel(side, text="โมเดล", font=HEAD_FONT).pack(anchor="w", padx=16)
        self.model = ctk.CTkOptionMenu(side, values=list(MODEL_IDS), command=self.on_model_change,
                                       font=BODY_FONT, width=268)
        self.model.pack(padx=16, pady=(0, 8))

        ctk.CTkLabel(side, text="ขนาดรูป (ด้านยาว)", font=HEAD_FONT).pack(anchor="w", padx=16)
        self.size = ctk.CTkSegmentedButton(side, values=["256", "512", "768", "1024"], font=BODY_FONT)
        self.size.set("512")
        self.size.pack(fill="x", padx=16, pady=(0, 8))
        ctk.CTkLabel(side, text="สัดส่วน (3:4/9:16 แนวตั้ง · 16:9 แนวนอน)", font=HEAD_FONT).pack(anchor="w", padx=16)
        self.ratio = ctk.CTkSegmentedButton(side, values=sorted(RATIOS), font=BODY_FONT)
        self.ratio.set("1:1")
        self.ratio.pack(fill="x", padx=16, pady=(0, 8))

        ctk.CTkLabel(side, text="จำนวนรูป", font=HEAD_FONT).pack(anchor="w", padx=16)
        self.count = ctk.CTkSegmentedButton(side, values=["1", "2", "4"], font=BODY_FONT)
        self.count.set("1")
        self.count.pack(fill="x", padx=16, pady=(0, 8))

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

        self.btn = ctk.CTkButton(side, text="เจนรูป", font=("Segoe UI", 15, "bold"), height=42,
                                 fg_color=ACCENT, hover_color=ACCENT_HOVER, command=self.on_generate)
        self.btn.pack(fill="x", padx=16, pady=(0, 8))

        self.progress = ctk.CTkProgressBar(side, mode="indeterminate")
        self.progress.pack(fill="x", padx=16, pady=(0, 6))
        self.progress.stop()
        self.status = ctk.CTkLabel(side, text="พร้อม — เลือกโมเดลแล้วกดเจนรูป", font=BODY_FONT,
                                   wraplength=268, justify="left")
        self.status.pack(anchor="w", padx=16, pady=(0, 10))

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

        ctk.CTkLabel(main, text="รูปที่เคยเจน", font=HEAD_FONT).grid(row=2, column=0, sticky="w", pady=(8, 4))
        self.gallery = ctk.CTkScrollableFrame(main, orientation="horizontal", height=110)
        self.gallery.grid(row=3, column=0, sticky="ew")
        self.refresh_gallery()

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

    def on_pick_dir(self):
        d = filedialog.askdirectory(initialdir=self.out_dir, title="เลือกที่เก็บรูป")
        if not d:
            return
        self.out_dir = os.path.normpath(d)
        save_out_dir(self.out_dir)
        self.out_label.configure(text=self.out_dir)
        self.status.configure(text=f"ที่เก็บรูป: {self.out_dir}")
        self.refresh_gallery()

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
        try:
            count = int(self.count.get())
        except ValueError:
            count = 1
        self.btn.configure(state="disabled")
        self.status.configure(text="กำลังเจน..." if count <= 1 else f"กำลังเจน {count} รูป...")
        self.progress.start()
        threading.Thread(target=self.work, args=(prompt, steps, seed, size, cfg, negative, model, count, ratio),
                         daemon=True).start()

    def work(self, prompt, steps, seed, size, cfg, negative, model, count=1, ratio="1:1"):
        try:
            out_dir = self.out_dir
            os.makedirs(out_dir, exist_ok=True)
            if count > 1:
                results = txt2img_batch(prompt, n=count, steps=steps, seed=seed, size=size, ratio=ratio,
                                        guidance=cfg, negative=negative, model=model)
                saved = []
                for img, used_seed in results:
                    path = next_path(out_dir)
                    img.save(path)
                    saved.append((img, path, used_seed))
                self.after(0, self.show_batch_result, saved)
                return
            img, used_seed = txt2img(prompt, steps=steps, seed=seed, size=size, ratio=ratio, guidance=cfg,
                                     negative=negative, model=model)
            path = next_path(out_dir)
            img.save(path)
            self.after(0, self.show_result, img, path, used_seed)
        except Exception as e:  # noqa: BLE001
            self.after(0, self.show_error, str(e))

    def show_result(self, img, path, used_seed):
        self.current_path = path
        self.display(img, os.path.basename(path))
        self.status.configure(text=f"เสร็จ! {os.path.basename(path)} {img.size[0]}x{img.size[1]} (seed {used_seed})")
        self.seed.delete(0, tk.END)
        self.seed.insert(0, str(used_seed))
        self.btn.configure(state="normal")
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
        self.btn.configure(state="normal")
        self.progress.stop()
        self.refresh_gallery()

    def show_error(self, msg):
        self.status.configure(text="เกิดข้อผิดพลาด")
        self.btn.configure(state="normal")
        self.progress.stop()
        messagebox.showerror("ผิดพลาด", msg[:500])

    def display(self, img, name):
        scale = min(560 / img.size[0], 560 / img.size[1])
        self.main_img = ctk.CTkImage(light_image=img, dark_image=img,
                                     size=(max(1, int(img.size[0] * scale)),
                                           max(1, int(img.size[1] * scale))))
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

    def recent_files(self):
        try:
            return sorted((os.path.join(self.out_dir, f) for f in os.listdir(self.out_dir) if f.endswith(".png")),
                           key=os.path.getmtime, reverse=True)
        except FileNotFoundError:
            return []

    def refresh_gallery(self):
        for w in self.gallery.winfo_children():
            w.destroy()
        self.thumb_refs = []
        files = self.recent_files()[:40]
        if not files:
            ctk.CTkLabel(self.gallery, text="ยังไม่มีรูป — กดเจนรูปเลย", font=BODY_FONT).pack(padx=8, pady=30)
            return
        for path in files:
            try:
                thumb = Image.open(path).convert("RGB")
                thumb.thumbnail((84, 84))
                cimg = ctk.CTkImage(light_image=thumb, dark_image=thumb, size=(84, 84))
            except Exception:  # noqa: BLE001, PERF203
                continue
            self.thumb_refs.append(cimg)
            ctk.CTkButton(self.gallery, image=cimg, text="", width=88, height=88,
                          fg_color="transparent", command=lambda p=path: self.view_image(p)).pack(
                              side="left", padx=4, pady=4)


if __name__ == "__main__":
    App().mainloop()
