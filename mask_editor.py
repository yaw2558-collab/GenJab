"""หน้าต่างระบายมาสก์สำหรับ inpaint — ขาว = เจนใหม่, ดำ = คงเดิม.

ระบายบนรูปที่ย่อให้พอดีจอ แต่เขียนลงมาสก์ขนาดเต็มของรูปต้นฉบับ (sd-cli ต้องการขนาดตรงกัน)."""
import tkinter as tk

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageTk

from appcore import ACCENT, ACCENT_HOVER, BODY_FONT, HEAD_FONT

VIEW_MAX = (900, 640)
TINT = (230, 60, 60)


def view_scale(img_w, img_h, max_w=VIEW_MAX[0], max_h=VIEW_MAX[1]):
    """สเกลย่อรูปให้พอดีกล่อง (ไม่ขยายเกินขนาดจริง)."""
    return min(max_w / img_w, max_h / img_h, 1.0)


def paint_stroke(mask, p0, p1, radius, value=255):
    """ระบายเส้นจาก p0 ถึง p1 (พิกัดรูปเต็ม) หัวท้ายกลม — value 255 = ระบาย, 0 = ลบ."""
    r = max(1, int(round(radius)))
    d = ImageDraw.Draw(mask)
    d.line([p0, p1], fill=value, width=r * 2)
    for x, y in (p0, p1):
        d.ellipse([x - r, y - r, x + r, y + r], fill=value)


def mask_coverage(mask):
    """สัดส่วนพื้นที่ที่ระบาย 0..1."""
    hist = mask.convert("L").histogram()
    total = sum(hist)
    return sum(hist[128:]) / total if total else 0.0


def tinted(base, mask, alpha=0.5):
    """รูปพรีวิว: ทาสีแดงโปร่งทับส่วนที่ระบาย."""
    tint = Image.new("RGB", base.size, TINT)
    a = mask.convert("L").point(lambda v: int(v * alpha))
    return Image.composite(tint, base, a)


class MaskEditor(ctk.CTkToplevel):
    """เปิดรูปต้นฉบับให้ระบาย — กดบันทึกแล้วเรียก on_save(mask ขนาดเต็ม)."""

    def __init__(self, master, image_path, on_save, mask=None):
        super().__init__(master)
        self.title("ระบายจุดที่จะแก้ (คลิกซ้าย = ระบาย, คลิกขวา = ลบ)")
        self.on_save = on_save
        self.base = Image.open(image_path).convert("RGB")
        w, h = self.base.size
        if mask is not None:
            self.mask = mask.convert("L").resize((w, h))
        else:
            self.mask = Image.new("L", (w, h), 0)
        self.scale = view_scale(w, h)
        self.view_size = (max(1, int(w * self.scale)), max(1, int(h * self.scale)))
        self.view_base = self.base.resize(self.view_size, Image.LANCZOS)
        self._last = None
        self._photo = None

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=10, pady=(10, 4))
        ctk.CTkLabel(bar, text="ขนาดแปรง", font=HEAD_FONT).pack(side="left")
        self.brush = ctk.CTkSlider(bar, from_=4, to=200, number_of_steps=49, width=180,
                                   command=self._on_brush)
        self.brush.set(max(8, min(200, round(max(w, h) / 16))))
        self.brush.pack(side="left", padx=6)
        self.brush_val = ctk.CTkLabel(bar, text="", font=BODY_FONT, width=48)
        self.brush_val.pack(side="left")
        self._on_brush(self.brush.get())
        ctk.CTkButton(bar, text="ล้าง", width=60, command=self.on_clear).pack(side="left", padx=(12, 4))
        ctk.CTkButton(bar, text="กลับด้าน", width=70, command=self.on_invert).pack(side="left", padx=4)
        ctk.CTkButton(bar, text="ยกเลิก", width=70, fg_color="#555", hover_color="#666",
                      command=self.destroy).pack(side="right", padx=(4, 0))
        ctk.CTkButton(bar, text="ใช้มาสก์นี้", width=90, fg_color=ACCENT, hover_color=ACCENT_HOVER,
                      command=self.on_done).pack(side="right", padx=4)

        self.canvas = tk.Canvas(self, width=self.view_size[0], height=self.view_size[1],
                                highlightthickness=0, bg="#111", cursor="crosshair")
        self.canvas.pack(padx=10, pady=(4, 4))
        self.info = ctk.CTkLabel(self, text="", font=BODY_FONT)
        self.info.pack(pady=(0, 8))
        for btn, val in (("1", 255), ("3", 0)):
            self.canvas.bind(f"<ButtonPress-{btn}>", lambda e, v=val: self._start(e, v))
            self.canvas.bind(f"<B{btn}-Motion>", lambda e, v=val: self._drag(e, v))
            self.canvas.bind(f"<ButtonRelease-{btn}>", lambda e: self._end())
        self._redraw()
        self.transient(master)
        self.after(50, self.grab_set)

    def _on_brush(self, v):
        self.brush_val.configure(text=f"{int(float(v))}px")

    def _img_xy(self, e):
        return (e.x / self.scale, e.y / self.scale)

    def _start(self, e, value):
        self._last = self._img_xy(e)
        self._drag(e, value)

    def _drag(self, e, value):
        p = self._img_xy(e)
        p0 = self._last or p
        paint_stroke(self.mask, p0, p, self.brush.get() / 2, value)
        self._last = p
        # วาดเส้นชั่วคราวบน canvas ให้เห็นทันที — ภาพจริงอัปเดตตอนปล่อยเมาส์
        r = self.brush.get() / 2 * self.scale
        color = "#E63C3C" if value else "#111"
        self.canvas.create_line(p0[0] * self.scale, p0[1] * self.scale, e.x, e.y,
                                fill=color, width=r * 2, capstyle="round", tags="stroke")

    def _end(self):
        self._last = None
        self._redraw()

    def _redraw(self):
        view_mask = self.mask.resize(self.view_size)
        self._photo = ImageTk.PhotoImage(tinted(self.view_base, view_mask))
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self._photo)
        self.info.configure(text=f"ระบายแล้ว {mask_coverage(self.mask) * 100:.0f}% ของรูป "
                                 f"({self.base.size[0]}x{self.base.size[1]})")

    def on_clear(self):
        self.mask = Image.new("L", self.base.size, 0)
        self._redraw()

    def on_invert(self):
        self.mask = self.mask.point(lambda v: 255 - v)
        self._redraw()

    def on_done(self):
        mask = self.mask
        self.destroy()
        self.on_save(mask)
