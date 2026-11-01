"""เจนจ๊าบคลาวด์ GenJab Cloud — เจนรูปผ่าน API ออนไลน์ ไม่ต้องมีการ์ดจอ/โมเดลในเครื่อง."""
import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image

from cloud_core import (gallery_paths, load_settings, read_params, save_images, save_settings)
from cloud_providers import PROVIDERS, RATIOS, CloudError, generate, label_to_id

ACCENT = "#2B8FD9"
ACCENT_HOVER = "#3FA2E8"
TITLE_FONT = ("Segoe UI", 26, "bold")
HEAD_FONT = ("Segoe UI", 12, "bold")
BODY_FONT = ("Segoe UI", 12)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class CloudApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("เจนจ๊าบคลาวด์ GenJab Cloud")
        self.geometry("1040x720")
        self.minsize(900, 620)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.s = load_settings()
        self.current_path = None
        self.current_img = None
        self.thumb_refs = []
        self.busy = False
        self._resize_job = None
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # ---- ซ้าย: แผงควบคุม ----
        side = ctk.CTkScrollableFrame(self, width=300, corner_radius=0)
        side.grid(row=0, column=0, sticky="ns")
        ctk.CTkLabel(side, text="เจนจ๊าบคลาวด์", font=TITLE_FONT, text_color=ACCENT).pack(anchor="w", padx=16, pady=(14, 0))
        ctk.CTkLabel(side, text="เจนรูปผ่านเน็ต ไม่ต้องมีการ์ดจอ", font=BODY_FONT).pack(anchor="w", padx=16, pady=(0, 10))

        ctk.CTkLabel(side, text="ผู้ให้บริการ", font=HEAD_FONT).pack(anchor="w", padx=16)
        self.provider_menu = ctk.CTkOptionMenu(side, values=[p["label"] for p in PROVIDERS.values()],
                                               font=BODY_FONT, command=self.on_provider_change)
        self.provider_menu.set(PROVIDERS[self.s["provider"]]["label"])
        self.provider_menu.pack(fill="x", padx=16, pady=(0, 8))

        ctk.CTkLabel(side, text="คีย์ API", font=HEAD_FONT).pack(anchor="w", padx=16)
        key_row = ctk.CTkFrame(side, fg_color="transparent")
        key_row.pack(fill="x", padx=16, pady=(0, 2))
        self.key_entry = ctk.CTkEntry(key_row, show="•", font=BODY_FONT)
        self.key_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.show_key = ctk.CTkButton(key_row, text="ดู", width=44, command=self.on_toggle_key)
        self.show_key.pack(side="right")
        self.key_hint = ctk.CTkLabel(side, text="", font=("Segoe UI", 11), text_color="gray70",
                                     wraplength=270, justify="left", anchor="w")
        self.key_hint.pack(fill="x", padx=16, pady=(0, 8))

        ctk.CTkLabel(side, text="โมเดล (พิมพ์ชื่อเองได้)", font=HEAD_FONT).pack(anchor="w", padx=16)
        self.model_box = ctk.CTkComboBox(side, values=PROVIDERS[self.s["provider"]]["models"], font=BODY_FONT)
        self.model_box.set(self.s["model"])
        self.model_box.pack(fill="x", padx=16, pady=(0, 8))

        ctk.CTkLabel(side, text="คำบรรยายภาพ (อังกฤษได้ผลดีสุด)", font=HEAD_FONT).pack(anchor="w", padx=16)
        self.prompt = ctk.CTkTextbox(side, height=90, font=BODY_FONT)
        self.prompt.pack(fill="x", padx=16, pady=(0, 8))
        self.prompt.insert("1.0", self.s["prompt"])

        self.neg_label = ctk.CTkLabel(side, text="สิ่งที่ไม่อยากให้มี (negative)", font=HEAD_FONT)
        self.neg_label.pack(anchor="w", padx=16)
        self.negative = ctk.CTkTextbox(side, height=46, font=BODY_FONT)
        self.negative.pack(fill="x", padx=16, pady=(0, 8))
        self.negative.insert("1.0", self.s["negative"])

        ctk.CTkLabel(side, text="สัดส่วนรูป", font=HEAD_FONT).pack(anchor="w", padx=16)
        self.ratio_btn = ctk.CTkSegmentedButton(side, values=list(RATIOS), font=BODY_FONT)
        self.ratio_btn.set(self.s["ratio"])
        self.ratio_btn.pack(fill="x", padx=16, pady=(0, 8))

        row = ctk.CTkFrame(side, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(0, 8))
        ctk.CTkLabel(row, text="จำนวนรูป", font=HEAD_FONT).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(row, text="seed (-1 = สุ่ม)", font=HEAD_FONT).grid(row=0, column=1, sticky="w", padx=(10, 0))
        self.count_btn = ctk.CTkSegmentedButton(row, values=["1", "2", "3", "4"], font=BODY_FONT, width=120)
        self.count_btn.set(str(self.s["count"]))
        self.count_btn.grid(row=1, column=0, sticky="w")
        self.seed_entry = ctk.CTkEntry(row, width=120, font=BODY_FONT)
        self.seed_entry.insert(0, self.s["seed"])
        self.seed_entry.grid(row=1, column=1, sticky="w", padx=(10, 0))

        self.gen_btn = ctk.CTkButton(side, text="เจนรูป", height=44, font=("Segoe UI", 15, "bold"),
                                     fg_color=ACCENT, hover_color=ACCENT_HOVER, command=self.on_generate)
        self.gen_btn.pack(fill="x", padx=16, pady=(6, 6))
        self.status = ctk.CTkLabel(side, text="พร้อม", font=BODY_FONT, wraplength=270, justify="left", anchor="w")
        self.status.pack(fill="x", padx=16, pady=(0, 8))

        ctk.CTkLabel(side, text="ที่เก็บรูป", font=HEAD_FONT).pack(anchor="w", padx=16)
        out_row = ctk.CTkFrame(side, fg_color="transparent")
        out_row.pack(fill="x", padx=16, pady=(0, 14))
        self.out_entry = ctk.CTkEntry(out_row, font=BODY_FONT)
        self.out_entry.insert(0, self.s["out_dir"])
        self.out_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        ctk.CTkButton(out_row, text="เลือก...", width=60, command=self.on_pick_out).pack(side="right")

        # ---- ขวา: รูป + แกลเลอรี ----
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew", padx=12, pady=12)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)
        bar = ctk.CTkFrame(main, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        ctk.CTkButton(bar, text="ใช้ค่ารูปนี้", width=100, command=self.on_use_params).pack(side="left")
        ctk.CTkButton(bar, text="เปิดโฟลเดอร์", width=100, command=self.on_open_folder).pack(side="left", padx=6)
        self.info = ctk.CTkLabel(bar, text="", font=BODY_FONT, anchor="w")
        self.info.pack(side="left", fill="x", expand=True, padx=6)
        self.view = ctk.CTkLabel(main, text="กด \"เจนรูป\" เพื่อเริ่ม", font=("Segoe UI", 16),
                                 fg_color=("gray85", "gray14"), corner_radius=8)
        self.view.grid(row=1, column=0, sticky="nsew")
        self.view.bind("<Configure>", self._on_view_resize)
        self.gallery = ctk.CTkScrollableFrame(main, height=100, orientation="horizontal")
        self.gallery.grid(row=2, column=0, sticky="ew", pady=(8, 0))

        self._apply_provider(self.s["provider"], keep_model=True)
        self.refresh_gallery()

    # ---------- ผู้ให้บริการ / คีย์ ----------
    def _provider(self):
        return label_to_id(self.provider_menu.get())

    def _remember_key(self):
        pid = getattr(self, "_shown_provider", None)
        if pid:
            k = self.key_entry.get().strip()
            if k:
                self.s["keys"][pid] = k
            else:
                self.s["keys"].pop(pid, None)

    def _apply_provider(self, pid, keep_model=False):
        info = PROVIDERS[pid]
        self._shown_provider = pid
        self.key_entry.delete(0, "end")
        self.key_entry.insert(0, self.s["keys"].get(pid, ""))
        env_set = bool(os.environ.get(info["env"]))
        if info["key_required"]:
            hint = f"ต้องมีคีย์ — ขอได้ที่ {info['key_url']}"
        else:
            hint = "ไม่ใส่ก็ได้ (ใส่ token จะได้คิวเร็วขึ้น)"
        if env_set:
            hint += f"\nเจอคีย์ในตัวแปร {info['env']} แล้ว เว้นช่องว่างได้"
        self.key_hint.configure(text=hint)
        self.model_box.configure(values=info["models"])
        if not keep_model:
            self.model_box.set(info["models"][0])
        state = "normal" if info["negative"] else "disabled"
        self.negative.configure(state=state)
        self.neg_label.configure(text="สิ่งที่ไม่อยากให้มี (negative)" if info["negative"]
                                 else "negative (เจ้านี้ไม่รองรับ)")

    def on_provider_change(self, _label):
        self._remember_key()
        self._apply_provider(self._provider())

    def on_toggle_key(self):
        hidden = self.key_entry.cget("show") == "•"
        self.key_entry.configure(show="" if hidden else "•")
        self.show_key.configure(text="ซ่อน" if hidden else "ดู")

    # ---------- เจนรูป ----------
    def _collect(self):
        self._remember_key()
        self.s.update({
            "provider": self._provider(),
            "model": self.model_box.get().strip(),
            "prompt": self.prompt.get("1.0", "end").strip(),
            "negative": self.negative.get("1.0", "end").strip(),
            "ratio": self.ratio_btn.get(),
            "count": int(self.count_btn.get() or 1),
            "seed": self.seed_entry.get().strip() or "-1",
            "out_dir": self.out_entry.get().strip() or "cloud_out",
        })
        return dict(self.s)

    def on_generate(self):
        if self.busy:
            return
        s = self._collect()
        save_settings(self.s)
        self.busy = True
        self.gen_btn.configure(state="disabled", text="กำลังเจน...")
        self.status.configure(text=f"ส่งไป {PROVIDERS[s['provider']]['label']} ... (ประมาณ 5–60 วิ)")
        threading.Thread(target=self._worker, args=(s,), daemon=True).start()

    def _worker(self, s):
        try:
            blobs, seed = generate(s["provider"], s["prompt"], negative=s["negative"], ratio=s["ratio"],
                                   seed=s["seed"], model=s["model"], key=s["keys"].get(s["provider"], ""),
                                   count=s["count"])
            params = {k: s[k] for k in ("provider", "model", "prompt", "negative", "ratio")}
            params["seed"] = seed
            paths = save_images(blobs, s["out_dir"], params)
            self.after(0, self._done, paths, None)
        except CloudError as e:
            self.after(0, self._done, [], str(e))
        except Exception as e:  # noqa: BLE001
            self.after(0, self._done, [], f"ผิดพลาด: {e}")

    def _done(self, paths, err):
        self.busy = False
        self.gen_btn.configure(state="normal", text="เจนรูป")
        if err:
            self.status.configure(text="เจนไม่สำเร็จ")
            messagebox.showerror("เจนไม่สำเร็จ", err, parent=self)
            return
        self.status.configure(text=f"เสร็จแล้ว {len(paths)} รูป → {os.path.dirname(paths[0])}")
        self.show(paths[0])
        self.refresh_gallery()

    # ---------- แสดงรูป ----------
    def show(self, path):
        try:
            with Image.open(path) as im:
                self.current_img = im.convert("RGB")
        except Exception:  # noqa: BLE001
            return
        self.current_path = path
        p = read_params(path) or {}
        self.info.configure(text=f"{os.path.basename(path)}  ·  {p.get('provider', '?')}/{p.get('model', '?')}"
                                 f"  ·  seed {p.get('seed', '?')}")
        self._render()

    def _render(self):
        if self.current_img is None:
            return
        bw, bh = max(50, self.view.winfo_width() - 8), max(50, self.view.winfo_height() - 8)
        try:
            scale = ctk.ScalingTracker.get_widget_scaling(self.view) or 1.0
        except Exception:  # noqa: BLE001
            scale = 1.0
        w, h = self.current_img.size
        k = min(bw / scale / w, bh / scale / h)
        size = (max(1, int(w * k)), max(1, int(h * k)))
        self._main_ref = ctk.CTkImage(light_image=self.current_img, dark_image=self.current_img, size=size)
        self.view.configure(image=self._main_ref, text="")

    def _on_view_resize(self, _e):
        if self._resize_job:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(120, self._render)

    def refresh_gallery(self):
        for w in self.gallery.winfo_children():
            w.destroy()
        self.thumb_refs = []
        for path in gallery_paths(self.out_entry.get().strip() or "cloud_out"):
            try:
                with Image.open(path) as im:
                    t = im.convert("RGB")
                    t.thumbnail((84, 84))
            except Exception:  # noqa: BLE001
                continue
            ref = ctk.CTkImage(light_image=t, dark_image=t, size=t.size)
            self.thumb_refs.append(ref)
            ctk.CTkButton(self.gallery, image=ref, text="", width=88, height=88, fg_color="transparent",
                          command=lambda p=path: self.show(p)).pack(side="left", padx=2)

    # ---------- ปุ่มอื่น ----------
    def on_use_params(self):
        p = read_params(self.current_path) if self.current_path else None
        if not p:
            messagebox.showinfo("ใช้ค่ารูปนี้", "รูปนี้ไม่มีค่าที่ฝังไว้", parent=self)
            return
        if p.get("provider") in PROVIDERS:
            self._remember_key()
            self.provider_menu.set(PROVIDERS[p["provider"]]["label"])
            self._apply_provider(p["provider"])
        self.model_box.set(p.get("model", self.model_box.get()))
        for box, k in ((self.prompt, "prompt"), (self.negative, "negative")):
            st = box.cget("state")
            box.configure(state="normal")
            box.delete("1.0", "end")
            box.insert("1.0", p.get(k, ""))
            box.configure(state=st)
        if p.get("ratio") in RATIOS:
            self.ratio_btn.set(p["ratio"])
        self.seed_entry.delete(0, "end")
        self.seed_entry.insert(0, str(p.get("seed", -1)))
        self.status.configure(text="ดึงค่าจากรูปแล้ว กดเจนซ้ำได้เลย")

    def on_pick_out(self):
        d = filedialog.askdirectory(parent=self, initialdir=self.out_entry.get() or ".")
        if d:
            self.out_entry.delete(0, "end")
            self.out_entry.insert(0, d)
            self.refresh_gallery()

    def on_open_folder(self):
        d = os.path.abspath(self.out_entry.get().strip() or "cloud_out")
        os.makedirs(d, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(d)  # noqa: S606
        else:
            import subprocess
            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", d])

    def on_close(self):
        self._collect()
        save_settings(self.s)
        self.destroy()


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    try:
        CloudApp().mainloop()
    except tk.TclError as e:
        print(f"เปิดหน้าต่างไม่ได้: {e}")


if __name__ == "__main__":
    main()
