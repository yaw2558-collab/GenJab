"""เจนจ๊าบ GenJab — จุดเข้าแอปรวม backend คู่ (เครื่องนี้ + คลาวด์).

```
.venv\\Scripts\\python.exe genjab.py            # เลือก backend จากหน้าต่าง
.venv\\Scripts\\python.exe genjab.py --local    # ข้ามหน้าเลือก เปิดฝั่งเครื่องนี้
.venv\\Scripts\\python.exe genjab.py --cloud    # ข้ามหน้าเลือก เปิดฝั่งคลาวด์
```
กดปุ่มสลับ backend ในแอปแล้ว launcher จะเปิดอีกฝั่งต่อให้เลย
(ไม่ต้องปิดแล้วเปิดใหม่เอง) — จำฝั่งล่าสุดไว้ใน dual_settings.json.
"""
import os
import sys

import dual_backend as db


def choose_backend(initial):
    """หน้าต่างเลือก backend คืน "local"/"cloud" หรือ None ถ้าปิดหน้าต่างทิ้ง."""
    import customtkinter as ctk

    picked = {"backend": None}
    win = ctk.CTk()
    win.title("เจนจ๊าบ GenJab — เลือก backend")
    win.geometry("360x320")
    win.resizable(False, False)

    ctk.CTkLabel(win, text="เจนจ๊าบ", font=("Segoe UI", 26, "bold"),
                 text_color="#2B8FD9").pack(pady=(20, 0))
    ctk.CTkLabel(win, text="เลือก backend ที่จะเจนรูป",
                 font=("Segoe UI", 13)).pack(pady=(0, 16))

    def pick(which):
        picked["backend"] = which
        db.save_backend(which)
        win.destroy()

    def mark(which):
        return " (ใช้ล่าสุด)" if which == initial else ""

    ctk.CTkButton(win, text=f"เครื่องนี้ (Local){mark(db.LOCAL)}",
                  font=("Segoe UI", 15, "bold"), height=48,
                  command=lambda: pick(db.LOCAL)).pack(fill="x", padx=28, pady=(0, 10))
    ctk.CTkButton(win, text=f"คลาวด์ (Cloud){mark(db.CLOUD)}",
                  font=("Segoe UI", 15, "bold"), height=48,
                  command=lambda: pick(db.CLOUD)).pack(fill="x", padx=28)
    ctk.CTkLabel(win, text="สลับฝั่งได้ตลอดด้วยปุ่มในแอป",
                 font=("Segoe UI", 11), text_color="gray60").pack(pady=14)
    win.protocol("WM_DELETE_WINDOW", win.destroy)
    win.mainloop()
    return picked["backend"]


def run_backend(backend):
    """เปิดแอปฝั่งที่เลือก คืน True ถ้าผู้ใช้กดสลับไปอีกฝั่ง (ยังไม่ออกโปรแกรม)."""
    if backend == db.CLOUD:
        from cloud_app import CloudApp
        app = CloudApp()
    else:
        from app import App
        app = App()
    app.mainloop()
    return bool(getattr(app, "switch_requested", False))


def main(argv=None):
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    argv = sys.argv[1:] if argv is None else argv
    forced = db.parse_argv(argv)
    backend = forced or db.load_backend()
    if forced is None:
        backend = choose_backend(backend)
        if backend is None:
            return 0
    db.save_backend(backend)
    while run_backend(backend):
        backend = db.other(backend)
        db.save_backend(backend)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
