"""เจนจ๊าบ GenJab — หน้าต่างโปรแกรมเจนรูปจากข้อความ (รันบนเครื่อง)."""
import os
import tempfile
import threading
import webbrowser
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image
from send2trash import send2trash

# บางชื่อ (OUT_DIR, default_settings, ...) import ไว้ให้ test_app.py / โค้ดเดิมที่เรียกผ่าน app
from appcore import (ACCENT, ACCENT_HOVER, BODY_FONT, DEFAULT_PROMPT, EXTEND_DURATIONS, FLOW_EXPORT_SUBDIR,
                     FLOW_URL, GALLERY_LIMIT, HEAD_FONT, KINOLOCAL_EXPORT_SUBDIR, KINOLOCAL_URL,
                     MODE_CONVERT, MODE_TXT, NO_UPSCALER,
                     MODEL_DEFAULTS, MODEL_DEFAULTS_FALLBACK, MODEL_IDS, MODEL_SIZES,
                     LOCAL_OUT_DIR, NAS_OUT_DIR, OUT_DIR, TITLE_FONT, copy_to_flow, copy_to_kinolocal,
                     ctk_image_size, default_settings,
                     engine_id, engine_label, fit_size, gen_params, load_gallery_thumbs, load_out_dir,
                     load_settings, next_path, next_paths, next_vid_path,
                     next_vid_paths, normalize_settings, params_to_settings,
                     read_params, save_out_dir, save_png, save_settings, unique_path)
from generate import (DEFAULT_ENGINE, I2V_MODELS, IP_ADAPTER_MODELS, NO_STYLE, RATIOS, face_engine, supports_ip_adapter,
                      CONTROL_TYPES, CONTROLNET_HINT, list_controlnets, supports_controlnet,
                      RESTYLE_FPS_CHOICES, STYLE_PRESETS, VIDEO_MODELS, GenerationCancelled,
                      apply_style, available_engines, comfy_i2v, comfy_img2img, comfy_txt2img, fit_video_size, img2img, img2vid, img2vid_extend,
                      restyle_video,
                      UPSCALE_HINT, list_loras, list_upscalers, lora_compatible, resolve_size, txt2img,
                      txt2img_batch, txt2vid, upscale)
from mask_editor import MaskEditor, mask_coverage
from sysmon import SysMon
import comfy_client
import audio_gen
import local_llm
from cloud_translate import has_thai
import sd_server

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


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
        self.current_video = None  # คลิปล่าสุดที่เจน/ใส่เพลง — ปุ่ม "ใส่เพลง" ใช้ตัวนี้
        self.mask_img = None
        self.mask_path = os.path.join(tempfile.gettempdir(), "genjab_mask.png")
        self.out_dir = load_out_dir()
        self.switch_requested = False  # launcher (genjab.py) อ่านหลังปิดหน้าต่าง
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # ---- ซ้าย: แผงควบคุม ----
        side = ctk.CTkScrollableFrame(self, width=300, corner_radius=0)
        side.grid(row=0, column=0, sticky="ns")


        ctk.CTkLabel(side, text="เจนจ๊าบ", font=TITLE_FONT, text_color=ACCENT).pack(anchor="w", padx=16, pady=(14, 0))
        ctk.CTkLabel(side, text="GenJab — เจนรูปฟรีบนเครื่อง", font=BODY_FONT).pack(anchor="w", padx=16, pady=(0, 6))
        ctk.CTkButton(side, text="สลับไปคลาวด์ (Cloud)", font=BODY_FONT, height=30,
                      fg_color="transparent", border_width=1,
                      command=self.on_switch_backend).pack(fill="x", padx=16, pady=(0, 10))

        self.mode_btn = ctk.CTkSegmentedButton(side, values=[MODE_TXT, MODE_CONVERT],
                                                   font=BODY_FONT, command=self.on_mode_change)
        self.mode_btn.set(MODE_TXT)
        self.mode_btn.pack(fill="x", padx=16, pady=(0, 8))

        ctk.CTkLabel(side, text="คำบรรยายภาพ (ไทย/English)", font=HEAD_FONT).pack(anchor="w", padx=16)
        self.prompt = ctk.CTkTextbox(side, height=70, font=BODY_FONT)
        self.prompt.pack(fill="x", padx=16, pady=(0, 4))
        self.translate_local = ctk.CTkCheckBox(
            side, text="แปลไทยเป็นอังกฤษในเครื่องก่อนเจน (Qwen3 ไม่ใช้เน็ต)", font=BODY_FONT)
        self.translate_local.select()
        self.translate_local.pack(anchor="w", padx=16, pady=(0, 8))
        self.prompt.insert("1.0", DEFAULT_PROMPT)

        # แผง ControlNet (โหมดเจนรูป) — คุมโครงรูปจากรูปอ้างอิง, _apply_mode โชว์/ซ่อน
        self.control_frame = ctk.CTkFrame(side, fg_color="transparent")
        ctk.CTkLabel(self.control_frame, text="คุมโครงด้วยรูป (ControlNet · SDXL)", font=HEAD_FONT).pack(anchor="w")
        ctl_row = ctk.CTkFrame(self.control_frame, fg_color="transparent")
        ctl_row.pack(fill="x", pady=(0, 4))
        self.control_label = ctk.CTkLabel(ctl_row, text="ไม่ใช้", font=BODY_FONT, anchor="w",
                                          wraplength=150, justify="left")
        self.control_label.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(ctl_row, text="ล้าง", width=50, command=self.on_clear_control).pack(side="right")
        ctk.CTkButton(ctl_row, text="เลือก...", width=70,
                      command=self.on_pick_control).pack(side="right", padx=(0, 6))
        self.control_path = ""
        ctl_row2 = ctk.CTkFrame(self.control_frame, fg_color="transparent")
        ctl_row2.pack(fill="x", pady=(0, 4))
        self.control_type = ctk.CTkOptionMenu(ctl_row2, values=list(CONTROL_TYPES), font=BODY_FONT, width=110)
        self.control_type.set("canny")
        self.control_type.pack(side="left")
        self.control_strength_val = ctk.CTkLabel(ctl_row2, text="0.9", font=BODY_FONT, width=30)
        self.control_strength_val.pack(side="right")
        self.control_strength = ctk.CTkSlider(ctl_row2, from_=0.1, to=1.5, number_of_steps=14, width=110,
                                              command=self.on_control_strength)
        self.control_strength.set(0.9)
        self.control_strength.pack(side="right", padx=(6, 4))

        # แผงโหมดแปลงรูป — สร้างไว้ก่อน ยังไม่ pack (ให้ _apply_mode โชว์/ซ่อน)
        self.convert_frame = ctk.CTkFrame(side, fg_color="transparent")
        ctk.CTkLabel(self.convert_frame, text="รูปต้นฉบับ", font=HEAD_FONT).pack(anchor="w")
        init_row = ctk.CTkFrame(self.convert_frame, fg_color="transparent")
        init_row.pack(fill="x", pady=(0, 4))
        self.init_label = ctk.CTkLabel(init_row, text="ยังไม่เลือกรูป", font=BODY_FONT, anchor="w",
                                       wraplength=180, justify="left")
        self.init_label.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(init_row, text="เลือก...", width=70, command=self.on_pick_init).pack(side="right")
        self.init_img_path = ""
        ctk.CTkLabel(self.convert_frame, text="สไตล์เทศกาล", font=HEAD_FONT).pack(anchor="w")
        self.style = ctk.CTkOptionMenu(self.convert_frame, values=[NO_STYLE] + list(STYLE_PRESETS),
                                       font=BODY_FONT, width=268)
        self.style.set(NO_STYLE)
        self.style.pack(pady=(0, 4))
        str_row = ctk.CTkFrame(self.convert_frame, fg_color="transparent")
        str_row.pack(fill="x")
        ctk.CTkLabel(str_row, text="ความแรงแปลงรูป (น้อย = คงเดิม)", font=HEAD_FONT).pack(side="left")
        self.strength_val = ctk.CTkLabel(str_row, text="0.6", font=BODY_FONT, width=30)
        self.strength_val.pack(side="right")
        self.strength = ctk.CTkSlider(self.convert_frame, from_=0.1, to=0.9, number_of_steps=8,
                                      command=self.on_strength)
        self.strength.set(0.6)
        self.strength.pack(fill="x", pady=(0, 6))
        self.keep_face = ctk.CTkCheckBox(self.convert_frame, text="คงหน้าเดิม (เฉพาะโมเดล SDXL)",
                                         font=BODY_FONT)
        self.keep_face.pack(anchor="w", pady=(0, 4))
        face_row = ctk.CTkFrame(self.convert_frame, fg_color="transparent")
        face_row.pack(fill="x")
        ctk.CTkLabel(face_row, text="แรงคงหน้า", font=HEAD_FONT).pack(side="left")
        self.face_strength_val = ctk.CTkLabel(face_row, text="0.6", font=BODY_FONT, width=30)
        self.face_strength_val.pack(side="right")
        self.face_strength = ctk.CTkSlider(self.convert_frame, from_=0.2, to=1.0, number_of_steps=8,
                                           command=self.on_face_strength)
        self.face_strength.set(0.6)
        self.face_strength.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(self.convert_frame, text="แก้เฉพาะจุด (inpaint)", font=HEAD_FONT).pack(anchor="w")
        mask_row = ctk.CTkFrame(self.convert_frame, fg_color="transparent")
        mask_row.pack(fill="x", pady=(0, 6))
        self.mask_label = ctk.CTkLabel(mask_row, text="ไม่ใช้ (แปลงทั้งรูป)", font=BODY_FONT, anchor="w")
        self.mask_label.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(mask_row, text="ล้าง", width=50, command=self.on_clear_mask).pack(side="right")
        ctk.CTkButton(mask_row, text="ระบาย...", width=70,
                      command=self.on_paint_mask).pack(side="right", padx=(0, 6))
        ctk.CTkLabel(self.convert_frame, text="ความยาวคลิป (วินาที)", font=HEAD_FONT).pack(anchor="w")
        self.extend_secs = ctk.CTkSegmentedButton(self.convert_frame, values=list(EXTEND_DURATIONS),
                                                  font=BODY_FONT)
        self.extend_secs.set("1")
        self.extend_secs.pack(fill="x", pady=(0, 6))
        self.animate_btn = ctk.CTkButton(self.convert_frame, text="ทำภาพขยับได้ (~2 นาที/คลิป)",
                                         font=("Segoe UI", 13, "bold"), height=36,
                                         fg_color=ACCENT, hover_color=ACCENT_HOVER,
                                         command=self.on_animate)
        self.animate_btn.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(self.convert_frame, text="FPS restyle (ยิ่งน้อยยิ่งเร็ว)", font=HEAD_FONT).pack(anchor="w")
        self.restyle_fps = ctk.CTkSegmentedButton(self.convert_frame,
                                                 values=[str(f) for f in RESTYLE_FPS_CHOICES],
                                                 font=BODY_FONT)
        self.restyle_fps.set("8")
        self.restyle_fps.pack(fill="x", pady=(0, 6))
        self.restyle_btn = ctk.CTkButton(self.convert_frame, text="วิดีโอจริง → 3D การ์ตูน (restyle ทั้งคลิป)",
                                         font=("Segoe UI", 13, "bold"), height=36,
                                         fg_color=ACCENT, hover_color=ACCENT_HOVER,
                                         command=self.on_restyle)
        self.restyle_btn.pack(fill="x", pady=(0, 6))

        ctk.CTkLabel(side, text="Negative (ดัน CFG > 1 ถึงมีผล)", font=HEAD_FONT).pack(anchor="w", padx=16)
        self.negative = ctk.CTkTextbox(side, height=44, font=BODY_FONT)
        self.negative.pack(fill="x", padx=16, pady=(0, 8))

        ctk.CTkLabel(side, text="โมเดล", font=HEAD_FONT).pack(anchor="w", padx=16)
        self.model = ctk.CTkOptionMenu(side, values=list(MODEL_IDS), command=self.on_model_change,
                                       font=BODY_FONT, width=268)
        self.model.pack(padx=16, pady=(0, 8))

        ctk.CTkLabel(side, text="Engine (sd-cli)", font=HEAD_FONT).pack(anchor="w", padx=16)
        self._engine_labels = [engine_label(e) for e in available_engines()]
        self.engine = ctk.CTkOptionMenu(side, values=self._engine_labels,
                                        font=BODY_FONT, width=268)
        self.engine.set(engine_label(DEFAULT_ENGINE))
        self.engine.pack(padx=16, pady=(0, 8))
        self.keep_model = ctk.CTkCheckBox(
            side, text="โหลดโมเดลค้างไว้ (รูปถัดไปเร็วขึ้น · ไม่มีภาพระหว่างเจน)", font=BODY_FONT)
        self.keep_model.select()
        self.keep_model.pack(anchor="w", padx=16, pady=(0, 8))

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
        ctk.CTkButton(topbar, text="ส่งไป Flow", font=BODY_FONT, width=90,
                      command=self.on_export_flow).pack(side="right", padx=(0, 8))
        self.music_btn = ctk.CTkButton(topbar, text="ใส่เพลง", font=BODY_FONT, width=80,
                                       command=self.on_add_music)
        self.music_btn.pack(side="right", padx=(0, 8))
        ctk.CTkButton(topbar, text="ส่งไป KinoLocal", font=BODY_FONT, width=120,
                      command=self.on_export_kinolocal).pack(side="right", padx=(0, 8))
        self.upscale_btn = ctk.CTkButton(topbar, text="ขยายรูป", font=BODY_FONT, width=80,
                                         command=self.on_upscale)
        self.upscale_btn.pack(side="right", padx=(0, 4))
        self.upscaler_menu = ctk.CTkOptionMenu(topbar, values=self._upscaler_names(),
                                               font=BODY_FONT, width=210)
        self.upscaler_menu.pack(side="right", padx=(0, 4))
        ctk.CTkButton(topbar, text="ใช้ค่ารูปนี้", font=BODY_FONT, width=90,
                      command=self.on_reuse_params).pack(side="right", padx=(0, 8))
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
        saved_up = load_settings().get("upscaler", "")
        if saved_up in self._upscaler_names():
            self.upscaler_menu.set(saved_up)

    @staticmethod
    def _upscaler_names():
        return list(list_upscalers()) or [NO_UPSCALER]

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
            "mode": self.mode_btn.get(),
            "init_img": self.init_img_path,
            "style": self.style.get(),
            "strength": round(float(self.strength.get()), 2),
            "keep_face": bool(self.keep_face.get()),
            "face_strength": round(float(self.face_strength.get()), 2),
            "upscaler": self.upscaler_menu.get(),
            "extend_secs": self.extend_secs.get(),
            "engine": engine_id(self.engine.get()),
            "keep_model": bool(self.keep_model.get()),
            "translate_local": bool(self.translate_local.get()),
        }

    def save_current_settings(self):
        save_settings(self.collect_settings())

    def _restore_settings(self, s=None):
        """ใส่ค่าลงวิดเจ็ต — ไม่ส่ง s = ค่าที่จำไว้ล่าสุด (ตอนเปิดโปรแกรม), ส่ง s = ค่าจากรูป."""
        s = normalize_settings(load_settings() if s is None else s)
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
        self.mode_btn.set(s["mode"])
        self.init_img_path = s["init_img"] if s["init_img"] and os.path.isfile(s["init_img"]) else ""
        self.init_label.configure(
            text=os.path.basename(self.init_img_path) if self.init_img_path else "ยังไม่เลือกรูป")
        self.style.set(s["style"])
        self.strength.set(s["strength"])
        self.strength_val.configure(text=f"{s['strength']:.1f}")
        if s["keep_face"]:
            self.keep_face.select()
        else:
            self.keep_face.deselect()
        self.face_strength.set(s["face_strength"])
        self.face_strength_val.configure(text=f"{s['face_strength']:.1f}")
        self.extend_secs.set(s["extend_secs"] if s["extend_secs"] in EXTEND_DURATIONS else "1")
        eng = engine_label(s["engine"])
        self.engine.set(eng if eng in self._engine_labels else engine_label(DEFAULT_ENGINE))
        if s.get("keep_model", True):
            self.keep_model.select()
        else:
            self.keep_model.deselect()
        if s.get("translate_local", True):
            self.translate_local.select()
        else:
            self.translate_local.deselect()
        self._apply_mode()

    def on_close(self):
        try:
            self.save_current_settings()
        finally:
            sd_server.SERVER.stop()  # ปิด sd-server ที่โหลดโมเดลค้างไว้ คืน VRAM
            self.destroy()

    def on_switch_backend(self):
        """ปุ่มสลับ backend — บอก launcher (genjab.py) ให้เปิดฝั่งคลาวด์ต่อ."""
        self.switch_requested = True
        self.on_close()

    def on_steps(self, v):
        self.steps_val.configure(text=str(int(round(float(v)))))

    def on_cfg(self, v):
        self.cfg_val.configure(text=f"{float(v):.1f}")

    def on_model_change(self, choice):
        mid = MODEL_IDS.get(choice, "sd-turbo")
        self.size.configure(values=MODEL_SIZES[mid])
        d = MODEL_DEFAULTS.get(mid, MODEL_DEFAULTS_FALLBACK)
        self.steps.set(d["steps"])
        self.steps_val.configure(text=str(d["steps"]))
        self.size.set(d["size"])
        if "cfg" in d:
            self.cfg.set(d["cfg"])
            self.cfg_val.configure(text=f"{d['cfg']:.1f}")
        for key in ("ratio", "frames", "fps"):
            if key in d:
                getattr(self, key).set(d[key])
        lora = self.lora.get()
        if lora != "(ไม่ใช้)" and not lora_compatible(lora, mid):
            self.lora.set("(ไม่ใช้)")
            self.status.configure(text=f"เอา LoRA {lora} ออกให้แล้ว — ไม่ตรงรุ่นกับโมเดลนี้ (รูปจะเพี้ยน)")
        if mid.startswith("comfy-") and self.lora.get() != "(ไม่ใช้)" \
                and not comfy_client.resolve_comfy_lora(self.lora.get()):
            bad = self.lora.get()
            self.lora.set("(ไม่ใช้)")
            self.status.configure(text=f"เอา LoRA {bad} ออกให้แล้ว — ฝั่ง ComfyUI ใช้ได้เฉพาะ LoRA SDXL ที่มีไฟล์คู่บน server")
        # ชื่อปุ่มเจนตั้งใน _apply_mode()
        if mid in VIDEO_MODELS:
            self.size_label.configure(text="ขนาดวิดีโอ (ด้านยาว)")
        else:
            self.size_label.configure(text="ขนาดรูป (ด้านยาว)")
        self._apply_mode()

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

    def on_mode_change(self, choice):
        self._apply_mode()

    def _apply_mode(self):
        """โชว์/ซ่อนแผงแปลงรูป + เปลี่ยนชื่อปุ่มตามโหมด — ปุ่มโหมดกับ restore ใช้ร่วมกัน."""
        convert = self.mode_btn.get() == MODE_CONVERT
        if convert:
            self.control_frame.pack_forget()
            self.convert_frame.pack(fill="x", padx=16, pady=(0, 8), before=self.size_label)
        else:
            self.convert_frame.pack_forget()
            self.control_frame.pack(fill="x", padx=16, pady=(0, 8), before=self.size_label)
        mid = MODEL_IDS.get(self.model.get(), "sd-turbo")
        if mid in VIDEO_MODELS:
            self.btn.configure(text="เจนวิดีโอ")
        else:
            self.btn.configure(text=MODE_CONVERT if convert else MODE_TXT)

    def on_strength(self, v):
        self.strength_val.configure(text=f"{float(v):.1f}")

    def on_face_strength(self, v):
        self.face_strength_val.configure(text=f"{float(v):.1f}")

    def on_control_strength(self, v):
        self.control_strength_val.configure(text=f"{float(v):.1f}")

    def on_pick_control(self):
        """เลือกรูปคุมโครง (ControlNet) — canny ใช้รูปถ่ายได้เลย, scribble ใช้ภาพวาดเส้น."""
        if not list_controlnets():
            messagebox.showinfo("ControlNet", f"ยังไม่มีไฟล์ ControlNet — {CONTROLNET_HINT}")
            return
        p = filedialog.askopenfilename(
            parent=self, title="เลือกรูปคุมโครง (ControlNet)",
            filetypes=[("รูปภาพ", "*.png *.jpg *.jpeg *.webp *.bmp"), ("ทั้งหมด", "*.*")])
        if p:
            self.control_path = p
            self.control_label.configure(text=os.path.basename(p))

    def on_clear_control(self):
        self.control_path = ""
        self.control_label.configure(text="ไม่ใช้")

    def on_pick_init(self):
        p = filedialog.askopenfilename(
            parent=self, title="เลือกรูปต้นฉบับ",
            filetypes=[("รูปภาพ", "*.png *.jpg *.jpeg *.webp *.bmp"), ("ทั้งหมด", "*.*")])
        if not p:
            return
        try:
            img = Image.open(p).convert("RGB")
        except Exception as e:  # noqa: BLE001
            self.status.configure(text=f"เปิดรูปไม่ได้: {e}")
            return
        self.init_img_path = p
        self.init_label.configure(text=os.path.basename(p))
        self.on_clear_mask()  # มาสก์เก่าระบายไว้กับรูปอื่น
        self.current_path = None  # กันปุ่มลบไปลบรูปต้นฉบับของ user
        self.display(img, os.path.basename(p))

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
        negative_raw = self.negative.get("1.0", "end").strip()
        if (self.translate_local.get() and (has_thai(prompt) or has_thai(negative_raw))
                and self.btn.cget("state") != "disabled"):
            # แปลในเธรดแยก แล้วใส่คำแปลกลับช่องเดิม จากนั้นเรียกเจนซ้ำ (รอบนั้นไม่มีอักษรไทยแล้ว)
            if not local_llm.available():
                messagebox.showwarning("เตือน", f"{local_llm.MISSING_HINT} — หรือเอาติ๊กแปลไทยออกแล้วพิมพ์อังกฤษเอง")
                return
            self.btn.configure(state="disabled")
            self.status.configure(text="กำลังแปลไทย→อังกฤษในเครื่อง...")
            self.progress.start()
            threading.Thread(target=self.work_translate, args=(prompt, negative_raw), daemon=True).start()
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
        engine = engine_id(self.engine.get())
        face_note = ""
        ratio = self.ratio.get()
        if ratio not in RATIOS:
            ratio = "1:1"
        lora = self.lora.get()
        if lora == "(ไม่ใช้)":
            lora = None
        lora_strength = round(float(self.lora_strength.get()), 2)
        if lora and not lora_compatible(lora, model):
            messagebox.showwarning("เตือน", f"LoRA {lora} ไม่ตรงรุ่นกับโมเดลนี้ — ใส่ไปรูปจะเพี้ยน "
                                            "เลือก (ไม่ใช้) หรือ LoRA ของรุ่นนี้ก่อน")
            return
        convert = self.mode_btn.get() == MODE_CONVERT
        init_path = self.init_img_path.strip() if convert else ""
        keep_face = bool(self.keep_face.get()) if convert else False
        if convert:
            if model in VIDEO_MODELS:
                messagebox.showwarning("เตือน", "โหมดแปลงรูปใช้กับโมเดลรูปเท่านั้น — เปลี่ยนโมเดลก่อน")
                return
            if keep_face and not supports_ip_adapter(model):
                messagebox.showwarning("เตือน", "คงหน้าเดิมใช้ได้กับโมเดล SDXL เท่านั้น — เปลี่ยนเป็น SDXL-Turbo/Base หรือเอาติ๊กออก")
                return
            if keep_face and not model.startswith("comfy-"):
                # Amuse 4.0 ถอด --ip-adapter ออก → สลับไป engine ที่ยังมี (เช่น 1106) ให้เอง
                try:
                    face_eng, _ = face_engine(engine, model)
                except (FileNotFoundError, RuntimeError) as e:
                    messagebox.showwarning("เตือน", str(e))
                    return
                if face_eng != engine:
                    face_note = f" (คงหน้าเดิมใช้ {engine_label(face_eng)})"
                    engine = face_eng
            if not init_path or not os.path.isfile(init_path):
                messagebox.showwarning("เตือน", "เลือกรูปต้นฉบับก่อน (ปุ่ม เลือก...)")
                return
        try:
            count = int(self.count.get())
        except ValueError:
            count = 1
        control = None
        use_control = (not convert and getattr(self, "control_path", "")
                       and model not in VIDEO_MODELS and not model.startswith("comfy-"))
        if use_control:
            if not supports_controlnet(model):
                messagebox.showwarning("เตือน", "ControlNet ใช้ได้กับโมเดล SDXL เท่านั้น — "
                                                "เปลี่ยนเป็น SDXL-Turbo/Base หรือกด ล้าง")
                return
            control = {"image": self.control_path, "type": self.control_type.get(),
                       "strength": round(float(self.control_strength.get()), 2)}
        meta = self.collect_settings()
        save_settings(meta)  # จำ engine ที่ผู้ใช้เลือก ไม่ใช่ตัวที่สลับให้ตอนคงหน้าเดิม
        meta["engine"] = engine  # PNG ฝัง engine ที่เจนจริง
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
                             kwargs={"engine": engine},
                             daemon=True).start()
            return
        if model.startswith("comfy-"):
            if lora and not comfy_client.resolve_comfy_lora(lora):
                messagebox.showwarning("เตือน", f"LoRA {lora} ยังใช้กับ ComfyUI ไม่ได้ — เลือก LoRA SDXL ที่มีไฟล์คู่บน server หรือ (ไม่ใช้)")
                return
            self.btn.configure(state="disabled")
            if convert:
                styled_prompt, styled_negative = apply_style(prompt, negative, self.style.get())
                strength = round(float(self.strength.get()), 2)
                mask = self.mask_path if self.mask_img is not None else None
                if mask:
                    self.mask_img.save(mask)
                    meta["inpaint"] = True
                self.status.configure(text="กำลังแปลงรูปผ่าน ComfyUI..." if count <= 1 else f"กำลังแปลง {count} รูปผ่าน ComfyUI...")
                self.progress.start()
                threading.Thread(target=self.work_comfy_img2img,
                                 args=(init_path, styled_prompt, strength, steps, seed, size,
                                       cfg, styled_negative, model, count,
                                       lora, lora_strength, mask, self.cancel_event),
                                 kwargs={"meta": meta}, daemon=True).start()
                return
            self.status.configure(text="กำลังเจนผ่าน ComfyUI..." if count <= 1 else f"กำลังเจน {count} รูปผ่าน ComfyUI...")
            self.progress.start()
            threading.Thread(target=self.work_comfy,
                             args=(prompt, steps, seed, size, cfg, negative, model, count, ratio,
                                   lora, lora_strength, self.cancel_event),
                             kwargs={"meta": meta}, daemon=True).start()
            return
        self.btn.configure(state="disabled")
        if convert:
            strength = round(float(self.strength.get()), 2)
            styled_prompt, styled_negative = apply_style(prompt, negative, self.style.get())
            face_ref = init_path if keep_face else None
            face_strength = round(float(self.face_strength.get()), 2)
            mask = self.mask_path if self.mask_img is not None else None
            if mask:
                self.mask_img.save(mask)
                meta["inpaint"] = True
            verb = "แก้เฉพาะจุด" if mask else "แปลง"
            self.status.configure(text=(f"กำลัง{verb}รูป..." if count <= 1 else f"กำลัง{verb} {count} รูป...")
                                  + face_note)
            self.progress.start()
            threading.Thread(target=self.work_img2img,
                             args=(init_path, styled_prompt, steps, seed, size, strength, cfg,
                                   styled_negative, model, count, lora, lora_strength,
                                   face_ref, face_strength,
                                   self.cancel_event),
                             kwargs={"mask": mask, "meta": meta, "engine": engine},
                             daemon=True).start()
            return
        self.status.configure(text="กำลังเจน..." if count <= 1 else f"กำลังเจน {count} รูป...")
        self.progress.start()
        if control:
            meta["controlnet"] = f"{control['type']} {control['strength']:g}"
        threading.Thread(target=self.work, args=(prompt, steps, seed, size, cfg, negative, model, count, ratio,
                                                 lora, lora_strength, self.cancel_event),
                         kwargs={"meta": meta, "engine": engine, "control": control}, daemon=True).start()

    def on_animate(self):
        prompt = self.prompt.get("1.0", "end").strip()
        if not prompt:
            messagebox.showwarning("เตือน", "พิมพ์คำบรรยายก่อน (บอกด้วยว่าอยากให้อะไรขยับ)")
            return
        model = MODEL_IDS.get(self.model.get(), "sd-turbo")
        if model not in I2V_MODELS:
            messagebox.showwarning("เตือน", "ทำภาพขยับได้เฉพาะโมเดลวิดีโอ (Wan2.2 5B / Wan2.2 14B ComfyUI) — เปลี่ยนโมเดลก่อน")
            return
        init_path = self.init_img_path.strip()
        if not init_path or not os.path.isfile(init_path):
            messagebox.showwarning("เตือน", "เลือกรูปต้นฉบับก่อน (ปุ่ม เลือก...)")
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
        try:
            frames = int(self.frames.get())
        except ValueError:
            frames = 17
        try:
            fps = int(self.fps.get())
        except ValueError:
            fps = 16
        try:
            target_secs = int(self.extend_secs.get())
        except ValueError:
            target_secs = 1
        styled_prompt, styled_negative = apply_style(prompt, negative, self.style.get())
        engine = engine_id(self.engine.get())
        self.save_current_settings()
        self.cancel_event = threading.Event()
        self.cancel_btn.configure(state="normal")
        self.btn.configure(state="disabled")
        self.animate_btn.configure(state="disabled")
        self.restyle_btn.configure(state="disabled")
        if target_secs > 1:
            self.status.configure(text=f"กำลังทำภาพขยับยาว ~{target_secs} วิ (หลายท่อน นานหลายนาที)...")
        else:
            self.status.configure(text="กำลังทำภาพขยับ...")
        self.progress.start()
        threading.Thread(target=self.work_animate,
                         args=(init_path, styled_prompt, steps, seed, size, frames, fps,
                               cfg, styled_negative, model, target_secs, self.cancel_event),
                         kwargs={"engine": engine},
                         daemon=True).start()

    def _seg_progress(self, i, n):
        self.status.configure(text=f"กำลังเจนท่อน {i}/{n}...")

    def work_animate(self, init_path, prompt, steps, seed, size, frames, fps, cfg,
                     negative, model, target_secs=1, cancel_event=None, engine=None):
        path = None
        try:
            out_dir = self.out_dir
            os.makedirs(out_dir, exist_ok=True)
            with Image.open(init_path) as im:
                w, h = fit_video_size(im.size[0], im.size[1], size)
            path = next_vid_path(out_dir)
            if target_secs > 1:
                out, seeds = img2vid_extend(
                    init_path, prompt, model=model, size=size, frames=frames, fps=fps,
                    steps=steps, guidance=cfg, seed=seed, negative=negative,
                    target_secs=target_secs, output=path,
                    on_segment=lambda i, n: self.after(0, self._seg_progress, i, n),
                    cancel_event=cancel_event, engine=engine)
                self.after(0, self.show_video_result, [(out, seeds[-1])], w, h, frames,
                           f"ยาว ~{target_secs} วิ {len(seeds)} ท่อน (seed {seeds[0]}–{seeds[-1]})")
                return
            if model == "wan22-14b-comfy":
                path = os.path.splitext(path)[0] + ".mp4"
                out, used_seed = comfy_i2v(
                    init_path, prompt, model=model, size=size,
                    frames=frames, fps=fps, steps=steps, guidance=cfg,
                    seed=seed, negative=negative, output=path,
                    cancel_event=cancel_event)
            else:
                out, used_seed = img2vid(init_path, prompt, model=model, size=size,
                                         frames=frames, fps=fps, steps=steps, guidance=cfg,
                                         seed=seed, negative=negative, output=path,
                                         cancel_event=cancel_event, engine=engine)
            self.after(0, self.show_video_result, [(out, used_seed)], w, h, frames)
        except GenerationCancelled:
            if path:
                try:
                    if os.path.isfile(path):
                        os.remove(path)
                except OSError:
                    pass
            self.after(0, self.show_cancelled)
        except Exception as e:  # noqa: BLE001
            self.after(0, self.show_error, str(e))

    def on_restyle(self):
        prompt = self.prompt.get("1.0", "end").strip()
        model = MODEL_IDS.get(self.model.get(), "sd-turbo")
        if model in VIDEO_MODELS or model.startswith("comfy-"):
            messagebox.showwarning("เตือน", "restyle ใช้โมเดลรูปเท่านั้น — เปลี่ยนเป็น SD-Turbo/SDXL/Anima ก่อน")
            return
        src = filedialog.askopenfilename(
            title="เลือกวิดีโอต้นฉบับ",
            filetypes=[("วิดีโอ", "*.mp4 *.avi *.webm *.mov *.mkv"), ("ทั้งหมด", "*.*")])
        if not src:
            return
        steps = int(round(self.steps.get()))
        try:
            size = int(self.size.get())
        except ValueError:
            size = 512
        try:
            fps = int(self.restyle_fps.get())
        except ValueError:
            fps = 8
        cfg = round(float(self.cfg.get()), 1)
        seed_txt = self.seed.get().strip()
        seed = int(seed_txt) if seed_txt.lstrip("-").isdigit() else None
        negative = self.negative.get("1.0", "end").strip()
        strength = round(float(self.strength.get()), 2)
        styled_prompt, styled_negative = apply_style(prompt, negative, self.style.get())
        est = max(1, round(120 * fps))
        if not messagebox.askokcancel(
                "ยืนยัน restyle",
                f"คลิป 2 นาทีที่ {fps}fps ≈ {est} เฟรม (หลายชั่วโมง)\n"
                "แนะนำลองคลิปสั้น 5 วิก่อน — กด OK เพื่อเริ่ม"):
            return
        self.save_current_settings()
        self.cancel_event = threading.Event()
        self.cancel_btn.configure(state="normal")
        self.btn.configure(state="disabled")
        self.animate_btn.configure(state="disabled")
        self.restyle_btn.configure(state="disabled")
        self.status.configure(text="กำลังแตกเฟรมวิดีโอ...")
        self.progress.start()
        threading.Thread(target=self.work_restyle,
                         args=(src, styled_prompt, steps, seed, size, fps, strength,
                               cfg, styled_negative, model, self.cancel_event),
                         daemon=True).start()

    def _restyle_progress(self, i, n):
        self.status.configure(text=f"กำลัง restyle เฟรม {i}/{n}...")

    def work_restyle(self, src, prompt, steps, seed, size, fps, strength, cfg,
                     negative, model, cancel_event=None):
        path = None
        try:
            out_dir = self.out_dir
            os.makedirs(out_dir, exist_ok=True)
            path = next_vid_path(out_dir)
            out, used_seed, n = restyle_video(
                src, prompt, model=model, size=size, fps=fps, strength=strength,
                steps=steps, guidance=cfg, seed=seed, negative=negative,
                output=path,
                on_frame=lambda i, total: self.after(0, self._restyle_progress, i, total),
                cancel_event=cancel_event)
            self.after(0, self.show_restyle_result, out, used_seed, n)
        except GenerationCancelled:
            if path:
                try:
                    if os.path.isfile(path):
                        os.remove(path)
                except OSError:
                    pass
            self.after(0, self.show_cancelled)
        except Exception as e:  # noqa: BLE001
            self.after(0, self.show_error, str(e))

    def show_restyle_result(self, path, used_seed, nframes):
        name = os.path.basename(path)
        self.current_img = None
        self.main_img = None
        self.canvas.configure(image=None, text=f"วิดีโอ restyle เสร็จแล้ว\n{name}\nเปิดด้วย player ดูได้เลย")
        self.img_name.configure(text=name)
        self.status.configure(text=f"เสร็จ! {name} {nframes} เฟรม (seed {used_seed})")
        self.seed.delete(0, tk.END)
        self._gen_done()
        self.progress.stop()

    def on_cancel(self):
        """User pressed cancel - tell the worker to kill sd-cli and end as cancelled."""
        if self.cancel_event is None:
            return
        self.cancel_event.set()
        self.status.configure(text="กำลังยกเลิก...")


    def work_translate(self, prompt, negative):
        """แปลไทย→อังกฤษ (เธรดแยก) แล้วส่งผลกลับเธรด Tk."""
        try:
            en_p = local_llm.translate(prompt)
            en_n = local_llm.translate(negative) if negative else ""
            self.after(0, self._translated, prompt, en_p, en_n)
        except Exception as e:  # noqa: BLE001
            self.after(0, self._translate_failed, str(e))

    def _translated(self, th_prompt, en_prompt, en_negative):
        """ใส่คำแปลแทนข้อความไทยในช่อง แล้วเจนต่อทันที — ต้นฉบับไทยโชว์ใน status."""
        self.progress.stop()
        self.btn.configure(state="normal")
        self.prompt.delete("1.0", "end")
        self.prompt.insert("1.0", en_prompt)
        if en_negative:
            self.negative.delete("1.0", "end")
            self.negative.insert("1.0", en_negative)
        self.on_generate()
        st = self.status.cget("text")
        self.status.configure(text=f"แปลแล้ว: {th_prompt[:40]} → {en_prompt[:60]} · {st}")

    def _translate_failed(self, msg):
        self.progress.stop()
        self.btn.configure(state="normal")
        self.status.configure(text="แปลไม่สำเร็จ")
        messagebox.showerror("แปลไม่สำเร็จ", msg)

    def on_add_music(self):
        """ใส่เพลงประกอบให้คลิป — ใช้คลิปล่าสุด ไม่มีให้เลือกไฟล์, ถามคำบรรยายเพลง แล้วเจนในเธรดแยก."""
        if self.btn.cget("state") == "disabled":
            self.status.configure(text="รองานที่ทำอยู่เสร็จก่อน")
            return
        if not audio_gen.available():
            hint = audio_gen.MUSIC_HINT if audio_gen.audiocpp_dir() else audio_gen.RUNTIME_HINT
            messagebox.showinfo("ใส่เพลง", hint)
            return
        video = self.current_video if self.current_video and os.path.isfile(self.current_video) else ""
        if not video:
            video = filedialog.askopenfilename(
                parent=self, title="เลือกคลิปที่จะใส่เพลง",
                filetypes=[("วิดีโอ", "*.webm *.mp4"), ("ทั้งหมด", "*.*")])
            if not video:
                return
        dlg = ctk.CTkInputDialog(
            title="ใส่เพลงประกอบคลิป",
            text=f"คลิป: {os.path.basename(video)}\nบรรยายเพลง (ไทยหรืออังกฤษ)\n"
                 "เช่น เพลงไทยเดิม ระนาด สนุกสนาน / calm lofi piano")
        desc = (dlg.get_input() or "").strip()
        if not desc:
            return
        if has_thai(desc) and not self.translate_local.get():
            messagebox.showwarning("เตือน", "คำบรรยายเพลงเป็นภาษาไทย — ติ๊ก \"แปลไทยเป็นอังกฤษในเครื่อง\" "
                                            "หรือพิมพ์เป็นภาษาอังกฤษ")
            return
        self.btn.configure(state="disabled")
        self.music_btn.configure(state="disabled")
        self.cancel_event = threading.Event()
        self.cancel_btn.configure(state="normal")
        self.status.configure(text=f"กำลังเจนเพลงให้ {os.path.basename(video)}... (ยกเลิกได้หลังเพลงเสร็จ)")
        self.progress.start()
        threading.Thread(target=self.work_music, args=(video, desc, self.cancel_event),
                         daemon=True).start()

    def work_music(self, video, desc, cancel_event=None):
        try:
            prompt = local_llm.translate(desc) if has_thai(desc) else desc
            out, secs = audio_gen.add_music_to_clip(video, prompt, cancel_event=cancel_event)
            self.after(0, self.show_music_result, out, secs, prompt)
        except GenerationCancelled:
            self.after(0, self.show_cancelled)
        except Exception as e:  # noqa: BLE001
            self.after(0, self.show_error, str(e))

    def show_music_result(self, out, secs, prompt):
        name = os.path.basename(out)
        self.current_video = out
        self.current_img = None
        self.main_img = None
        self.canvas.configure(image=None, text=f"ใส่เพลงแล้ว\n{name}\nเปิดด้วย player ฟังได้เลย")
        self.img_name.configure(text=name)
        self.status.configure(text=f"เสร็จ! {name} ({secs:.1f} วิ) เพลง: {prompt[:70]}")
        self._gen_done()
        self.progress.stop()

    def _preview_cb(self, job_event):
        """callback ดูรูประหว่างเจน (เรียกจากเธรดเจน) — ส่งต่อให้เธรด Tk วาด เฉพาะงานที่ยังรันอยู่."""
        def cb(img):
            self.after(0, self._show_preview, img, job_event)
        return cb

    def _show_preview(self, img, job_event):
        """วาดรูประหว่างเจนบนจอใหญ่ — งานจบ/ยกเลิกแล้ว (cancel_event เปลี่ยน) ไม่วาดทับรูปผลลัพธ์;
        ไม่แตะ current_img/current_path (ปุ่มลบ/ส่งต่อยังชี้รูปเดิม)."""
        if job_event is None or self.cancel_event is not job_event:
            return
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        if cw < 50 or ch < 50:
            cw, ch = 560, 560
        try:
            scaling = ctk.ScalingTracker.get_widget_scaling(self.canvas)
        except Exception:  # noqa: BLE001
            scaling = 1.0
        self.preview_img = ctk.CTkImage(light_image=img, dark_image=img,
                                        size=ctk_image_size(img.size[0], img.size[1], cw, ch, scaling))
        self.canvas.configure(image=self.preview_img, text="")
        self.img_name.configure(text="กำลังเจน... (ภาพตัวอย่างระหว่างทาง)")

    def _gen_done(self):
        """Restore buttons after finish/fail/cancel - gen back on, cancel off."""
        self.btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")
        self.animate_btn.configure(state="normal")
        self.restyle_btn.configure(state="normal")
        self.upscale_btn.configure(state="normal")
        if hasattr(self, "music_btn"):
            self.music_btn.configure(state="normal")
        self.cancel_event = None
        self.progress.stop()


    def show_cancelled(self):
        """Job was cancelled - show status instead of error popup."""
        self.status.configure(text="ยกเลิกแล้ว")
        self._gen_done()


    def work_video(self, prompt, steps, seed, width, height, frames, fps, cfg, negative, model,
                   count=1, cancel_event=None, engine=None):
        try:
            out_dir = self.out_dir
            os.makedirs(out_dir, exist_ok=True)
            paths = next_vid_paths(out_dir, count)
            saved = []
            for i, path in enumerate(paths):
                s = (seed + i) % 2**31 if seed is not None else None
                out, used_seed = txt2vid(prompt, model=model, seed=s, width=width, height=height,
                                         frames=frames, fps=fps, steps=steps, guidance=cfg,
                                         negative=negative, output=path, cancel_event=cancel_event,
                                         engine=engine)
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

    def show_video_result(self, saved, width, height, frames, extra=""):
        path, used_seed = saved[0]
        self.current_video = saved[-1][0]
        name = os.path.basename(path)
        self.current_img = None
        self.main_img = None
        self.canvas.configure(image=None, text=f"วิดีโอเซฟแล้ว\n{name}\nเปิดด้วย player ดูได้เลย")
        self.img_name.configure(text=name)
        if len(saved) > 1:
            self.status.configure(
                text=f"เสร็จ! {len(saved)} คลิป {width}x{height} {frames}f (seed {saved[0][1]}–{saved[-1][1]})")
        else:
            self.status.configure(text=f"เสร็จ! {name} {width}x{height} {frames}f (seed {used_seed})" + (f" {extra}" if extra else ""))
        # ล้างช่อง seed ทุกครั้งหลังเจน — กดครั้งต่อไปสุ่มใหม่เสมอ (ดู seed ที่ใช้ใน status เอา)
        self.seed.delete(0, tk.END)
        self._gen_done()
        self.progress.stop()

    def work_img2img(self, init_path, prompt, steps, seed, size, strength, cfg, negative, model,
                     count=1, lora=None, lora_strength=1.0, face_ref=None,
                     face_strength=0.6, cancel_event=None, mask=None, meta=None, engine=None):
        try:
            out_dir = self.out_dir
            os.makedirs(out_dir, exist_ok=True)
            paths = next_paths(out_dir, count)
            saved = []
            for i, path in enumerate(paths):
                s = (seed + i) % 2**31 if seed is not None else None
                img, used_seed = img2img(init_path, prompt, strength=strength, steps=steps, seed=s,
                                         size=size, guidance=cfg, negative=negative, model=model,
                                         lora=lora, lora_strength=lora_strength,
                                         face_ref=face_ref, face_strength=face_strength,
                                         mask=mask, cancel_event=cancel_event, engine=engine,
                                         on_preview=App._preview_cb(self, cancel_event),
                                         server=bool(meta and meta.get("keep_model")))
                save_png(img, path, gen_params(meta, used_seed) if meta else None)
                saved.append((img, path, used_seed))
            if len(saved) > 1:
                self.after(0, self.show_batch_result, saved)
            else:
                img, path, used_seed = saved[0]
                self.after(0, self.show_result, img, path, used_seed)
        except GenerationCancelled:
            self.after(0, self.show_cancelled)
        except Exception as e:  # noqa: BLE001
            self.after(0, self.show_error, str(e))

    def work_comfy_img2img(self, init_path, prompt, strength, steps, seed, size, cfg,
                           negative, model, count=1, lora=None, lora_strength=1.0,
                           mask=None, cancel_event=None, meta=None):
        """แปลงรูปผ่าน ComfyUI server — ปลายทางโชว์ผลเดียวกับ work_img2img()."""
        try:
            out_dir = self.out_dir
            os.makedirs(out_dir, exist_ok=True)
            paths = next_paths(out_dir, count)
            saved = []
            for i, path in enumerate(paths):
                s = (seed + i) % 2**31 if seed is not None else None
                img, used_seed = comfy_img2img(init_path, prompt, strength=strength, steps=steps,
                                              seed=s, size=size, guidance=cfg, negative=negative,
                                              ckpt=model, lora=lora, lora_strength=lora_strength,
                                              mask=mask, cancel_event=cancel_event)
                save_png(img, path, gen_params(meta, used_seed) if meta else None)
                saved.append((img, path, used_seed))
            if len(saved) > 1:
                self.after(0, self.show_batch_result, saved)
            else:
                img, path, used_seed = saved[0]
                self.after(0, self.show_result, img, path, used_seed)
        except GenerationCancelled:
            self.after(0, self.show_cancelled)
        except Exception as e:  # noqa: BLE001
            self.after(0, self.show_error, str(e))

    def work_comfy(self, prompt, steps, seed, size, cfg, negative, model, count=1,
                   ratio="1:1", lora=None, lora_strength=1.0, cancel_event=None, meta=None):
        """เจนผ่าน ComfyUI server ทีละรูป (server คิวเร็ว) — ปลายทางโชว์ผลเดียวกับ work()."""
        try:
            out_dir = self.out_dir
            os.makedirs(out_dir, exist_ok=True)
            paths = next_paths(out_dir, count)
            saved = []
            for i, path in enumerate(paths):
                s = (seed + i) % 2**31 if seed is not None else None
                img, used_seed = comfy_txt2img(prompt, steps=steps, seed=s, size=size,
                                              guidance=cfg, negative=negative,
                                              ckpt=model, ratio=ratio, lora=lora,
                                              lora_strength=lora_strength,
                                              cancel_event=cancel_event)
                save_png(img, path, gen_params(meta, used_seed) if meta else None)
                saved.append((img, path, used_seed))
            if len(saved) > 1:
                self.after(0, self.show_batch_result, saved)
            else:
                img, path, used_seed = saved[0]
                self.after(0, self.show_result, img, path, used_seed)
        except GenerationCancelled:
            self.after(0, self.show_cancelled)
        except Exception as e:  # noqa: BLE001
            self.after(0, self.show_error, str(e))

    def work(self, prompt, steps, seed, size, cfg, negative, model, count=1, ratio="1:1",
             lora=None, lora_strength=1.0, cancel_event=None, meta=None, engine=None, control=None):
        try:
            out_dir = self.out_dir
            os.makedirs(out_dir, exist_ok=True)
            if count > 1:
                results = txt2img_batch(prompt, n=count, steps=steps, seed=seed, size=size, ratio=ratio,
                                        lora=lora, lora_strength=lora_strength,
                                        guidance=cfg, negative=negative, model=model,
                                        cancel_event=cancel_event, engine=engine,
                                        server=bool(meta and meta.get("keep_model")), control=control)
                paths = next_paths(out_dir, len(results))
                saved = []
                for (img, used_seed), path in zip(results, paths):
                    save_png(img, path, gen_params(meta, used_seed) if meta else None)
                    saved.append((img, path, used_seed))
                self.after(0, self.show_batch_result, saved)
                return
            img, used_seed = txt2img(prompt, steps=steps, seed=seed, size=size, ratio=ratio, guidance=cfg,
                                     lora=lora, lora_strength=lora_strength,
                                     negative=negative, model=model, cancel_event=cancel_event,
                                     engine=engine, on_preview=App._preview_cb(self, cancel_event),
                                     server=bool(meta and meta.get("keep_model")), control=control)
            path = next_path(out_dir)
            save_png(img, path, gen_params(meta, used_seed) if meta else None)
            self.after(0, self.show_result, img, path, used_seed)
        except GenerationCancelled:
            self.after(0, self.show_cancelled)
        except Exception as e:  # noqa: BLE001
            self.after(0, self.show_error, str(e))

    def show_result(self, img, path, used_seed):
        self.current_path = path
        self.display(img, os.path.basename(path))
        self.status.configure(text=f"เสร็จ! {os.path.basename(path)} {img.size[0]}x{img.size[1]} (seed {used_seed})")
        # ล้างช่อง seed ทุกครั้งหลังเจน — กดครั้งต่อไปสุ่มใหม่เสมอ (ดู seed ที่ใช้ใน status เอา)
        self.seed.delete(0, tk.END)
        self._gen_done()
        self.progress.stop()
        self.refresh_gallery()

    def show_batch_result(self, saved):
        img, path, used_seed = saved[0]
        self.current_path = path
        self.display(img, os.path.basename(path))
        last_seed = saved[-1][2]
        self.status.configure(text=f"เสร็จ! {len(saved)} รูป {img.size[0]}x{img.size[1]} (seed {used_seed}–{last_seed})")
        # ล้างช่อง seed ทุกครั้งหลังเจน — กดครั้งต่อไปสุ่มใหม่เสมอ (ดู seed ที่ใช้ใน status เอา)
        self.seed.delete(0, tk.END)
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

    def on_export_flow(self):
        if not self.current_path or not os.path.isfile(self.current_path):
            self.status.configure(text="ไม่มีรูปให้ส่ง")
            return
        try:
            dest = copy_to_flow(self.current_path, self.out_dir)
        except OSError as e:  # noqa: BLE001
            self.status.configure(text=f"ส่งไป Flow ไม่ได้: {e}")
            return
        webbrowser.open(FLOW_URL)
        self.status.configure(text=f"ก๊อป {os.path.basename(dest)} ไปโฟลเดอร์ flow แล้ว — ลากเข้า Flow ได้เลย")

    def on_export_kinolocal(self):
        if not self.current_path or not os.path.isfile(self.current_path):
            self.status.configure(text="ไม่มีรูปให้ส่ง")
            return
        try:
            dest = copy_to_kinolocal(self.current_path, self.out_dir)
        except OSError as e:  # noqa: BLE001
            self.status.configure(text=f"ส่งไป KinoLocal ไม่ได้: {e}")
            return
        webbrowser.open(KINOLOCAL_URL)
        self.status.configure(text=f"ก๊อป {os.path.basename(dest)} ไปโฟลเดอร์ kinolocal แล้ว — ลากเข้า KinoLocal ได้เลย")

    def on_reuse_params(self):
        """ดึงพรอม/โมเดล/seed ที่ฝังไว้ในรูปที่โชว์อยู่กลับมาใส่แผงซ้าย."""
        if not self.current_path or not os.path.isfile(self.current_path):
            self.status.configure(text="ไม่มีรูปให้ดึงค่า")
            return
        params = read_params(self.current_path)
        if params is None:
            self.status.configure(text="รูปนี้ไม่มีค่าที่บันทึกไว้ (เจนก่อนมีฟีเจอร์นี้ หรือมาจากที่อื่น)")
            return
        self._restore_settings(params_to_settings(params, self.collect_settings()))
        if params.get("inpaint"):
            self.status.configure(text=f"ดึงค่าจาก {os.path.basename(self.current_path)} แล้ว "
                                       "— รูปนี้แก้เฉพาะจุด ต้องระบายมาสก์ใหม่")
        else:
            self.status.configure(text=f"ดึงค่าจาก {os.path.basename(self.current_path)} แล้ว "
                                       f"(seed {params.get('seed', '?')}) — กดเจนซ้ำได้เลย")

    def on_upscale(self):
        if not self.current_path or not os.path.isfile(self.current_path):
            self.status.configure(text="ไม่มีรูปให้ขยาย")
            return
        found = list_upscalers()
        if not found:
            messagebox.showwarning("ยังไม่มีโมเดลขยายรูป", "ไม่พบโมเดลขยายรูป — " + UPSCALE_HINT)
            return
        name = self.upscaler_menu.get()
        if name not in found:  # ไฟล์ถูกลบ/เพิ่มระหว่างเปิดโปรแกรม — อัปเดตเมนูแล้วใช้ตัวแรก
            self.upscaler_menu.configure(values=list(found))
            name = next(iter(found))
            self.upscaler_menu.set(name)
        engine = engine_id(self.engine.get())
        self.save_current_settings()
        self.cancel_event = threading.Event()
        self.cancel_btn.configure(state="normal")
        self.btn.configure(state="disabled")
        self.upscale_btn.configure(state="disabled")
        self.status.configure(text=f"กำลังขยาย {os.path.basename(self.current_path)} ด้วย {name}...")
        self.progress.start()
        threading.Thread(target=self.work_upscale, args=(self.current_path, self.cancel_event, name),
                         kwargs={"engine": engine},
                         daemon=True).start()

    def work_upscale(self, src, cancel_event=None, upscaler=None, engine=None):
        try:
            img = upscale(src, upscaler=upscaler, cancel_event=cancel_event, engine=engine)
            base = os.path.splitext(os.path.basename(src))[0]
            path = unique_path(self.out_dir, f"{base}_up.png")
            params = read_params(src)
            if params is not None:
                params["upscaled_from"] = os.path.basename(src)
            save_png(img, path, params)
            self.after(0, self.show_upscale_result, img, path)
        except GenerationCancelled:
            self.after(0, self.show_cancelled)
        except Exception as e:  # noqa: BLE001
            self.after(0, self.show_error, str(e))

    def show_upscale_result(self, img, path):
        self.current_path = path
        self.display(img, os.path.basename(path))
        self.status.configure(text=f"ขยายเสร็จ! {os.path.basename(path)} {img.size[0]}x{img.size[1]}")
        self._gen_done()
        self.refresh_gallery()

    def on_paint_mask(self):
        init = self.init_img_path.strip()
        if not init or not os.path.isfile(init):
            messagebox.showwarning("เตือน", "เลือกรูปต้นฉบับก่อน (ปุ่ม เลือก...) แล้วค่อยระบาย")
            return
        try:
            MaskEditor(self, init, self._set_mask, mask=self.mask_img)
        except Exception as e:  # noqa: BLE001
            self.status.configure(text=f"เปิดหน้าระบายไม่ได้: {e}")

    def _set_mask(self, mask):
        if mask_coverage(mask) <= 0:
            self.on_clear_mask()
            return
        self.mask_img = mask
        self.mask_label.configure(text=f"ระบายแล้ว {mask_coverage(mask) * 100:.0f}% — แก้เฉพาะจุดนั้น")
        self.status.configure(text="ตั้งมาสก์แล้ว — กดแปลงรูปเพื่อเจนใหม่เฉพาะส่วนที่ระบาย "
                                   "(ความแรงสูง ~0.8 เปลี่ยนชัดกว่า)")

    def on_clear_mask(self):
        self.mask_img = None
        self.mask_label.configure(text="ไม่ใช้ (แปลงทั้งรูป)")

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
