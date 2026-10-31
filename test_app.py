"""เทส logic ที่เก็บรูปของ app.py (ไม่ต้องเปิด GUI) — รันด้วย `python test_app.py`."""
import os
import tempfile

from app import OUT_DIR, load_out_dir, next_path, save_out_dir


def test_next_path_empty_dir():
    with tempfile.TemporaryDirectory() as td:
        assert next_path(td) == os.path.join(td, "pic001.png")


def test_next_path_skips_existing():
    with tempfile.TemporaryDirectory() as td:
        for name in ("pic001.png", "pic002.png", "notes.txt"):
            open(os.path.join(td, name), "w").close()
        assert next_path(td) == os.path.join(td, "pic003.png")


def test_default_out_dir():
    assert OUT_DIR == "out"


def _in_tmp_cwd(td):
    cwd = os.getcwd()
    os.chdir(td)
    return cwd


def test_out_dir_persists():
    with tempfile.TemporaryDirectory() as td:
        target = os.path.join(td, "pics")
        os.makedirs(target)
        cwd = _in_tmp_cwd(td)
        try:
            assert load_out_dir() == OUT_DIR  # ยังไม่เคยเลือก
            save_out_dir(target)
            assert load_out_dir() == os.path.normpath(target)
        finally:
            os.chdir(cwd)


def test_out_dir_falls_back():
    with tempfile.TemporaryDirectory() as td:
        cwd = _in_tmp_cwd(td)
        try:
            save_out_dir(os.path.join(td, "deleted"))  # โฟลเดอร์ไม่อยู่แล้ว
            assert load_out_dir() == OUT_DIR
            with open("settings.json", "w", encoding="utf-8") as f:
                f.write("{broken")
            assert load_out_dir() == OUT_DIR  # ไฟล์พัง
        finally:
            os.chdir(cwd)


def test_sysmon_sample_shape():
    from sysmon import SysMon
    m = SysMon()
    try:
        for _ in range(2):
            s = m.sample()
            assert set(s) == {"cpu", "ram", "gpu", "ram_used_mb", "ram_total_mb",
                              "vram_used_mb", "vram_total_mb"}, set(s)
            for k in ("cpu", "ram", "gpu"):
                assert s[k] is None or 0 <= s[k] <= 100, (k, s[k])
            for k in ("ram_used_mb", "ram_total_mb", "vram_used_mb", "vram_total_mb"):
                assert s[k] is None or s[k] >= 0, (k, s[k])
            if s["vram_used_mb"] is not None and s["vram_total_mb"] is not None:
                assert s["vram_used_mb"] <= s["vram_total_mb"], s
    finally:
        m.close()
        m.close()  # ปิดซ้ำต้องไม่พัง


def test_fit_size():
    from app import fit_size
    assert fit_size(512, 512, 560, 560) == (560, 560)
    assert fit_size(384, 512, 700, 500) == (375, 500)
    assert fit_size(1024, 320, 700, 500) == (700, 218)
    assert fit_size(10, 10, 5, 500) == (5, 5)
    w, h = fit_size(100, 200, 1000, 1000)
    assert (w, h) == (500, 1000) and w >= 1 and h >= 1


def test_ctk_image_size():
    from app import ctk_image_size
    # สเกล 100% = เท่า fit เดิม
    assert ctk_image_size(512, 512, 560, 560) == (560, 560)
    assert ctk_image_size(512, 512, 560, 560, 1.0) == (560, 560)
    # จอ 150%: กล่อง physical 600 → logical 400 คูณสเกลกลับต้องไม่ล้นกล่อง
    w, h = ctk_image_size(512, 512, 600, 600, 1.5)
    assert (w, h) == (400, 400)
    assert w * 1.5 <= 600 and h * 1.5 <= 600
    # รูปแนวตั้งบนจอ 125% คูณสเกลกลับต้องไม่ล้นกล่อง
    w, h = ctk_image_size(384, 512, 700, 500, 1.25)
    assert (w, h) == (300, 400)
    assert w * 1.25 <= 700 and h * 1.25 <= 500
    # สเกลพัง → fallback 1.0 ไม่ error
    assert ctk_image_size(512, 512, 560, 560, 0) == (560, 560)
    assert ctk_image_size(512, 512, 560, 560, None) == (560, 560)


def test_next_paths_reserves_ahead():
    import tempfile
    from app import next_path, next_paths
    with tempfile.TemporaryDirectory() as td:
        assert next_paths(td, 4) == [os.path.join(td, f"pic{i:03d}.png") for i in (1, 2, 3, 4)]
        open(os.path.join(td, "pic001.png"), "w").close()
        open(os.path.join(td, "pic003.png"), "w").close()
        assert next_paths(td, 3) == [os.path.join(td, f"pic{i:03d}.png") for i in (2, 4, 5)]
        assert next_path(td) == os.path.join(td, "pic002.png")


def test_load_gallery_thumbs():
    from PIL import Image
    from app import GALLERY_LIMIT, load_gallery_thumbs
    assert GALLERY_LIMIT == 40
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        p1 = os.path.join(td, "a.png")
        p2 = os.path.join(td, "b.png")
        Image.new("RGB", (200, 100)).save(p1)
        Image.new("RGB", (100, 300)).save(p2)
        with open(os.path.join(td, "broken.png"), "w") as f:
            f.write("not an image")
        out = load_gallery_thumbs([p1, p2, os.path.join(td, "broken.png"),
                                   os.path.join(td, "missing.png")])
        assert [p for p, _ in out] == [p1, p2]
        for _, t in out:
            assert t.mode == "RGB" and max(t.size) <= 84, t.size
        assert out[0][1].size == (84, 42)
        assert out[1][1].size == (28, 84)
        assert load_gallery_thumbs([]) == []


def test_next_vid_paths():
    import tempfile
    from app import next_vid_path, next_vid_paths
    with tempfile.TemporaryDirectory() as td:
        assert next_vid_paths(td, 2) == [os.path.join(td, f"vid{i:03d}.webm") for i in (1, 2)]
        open(os.path.join(td, "vid001.webm"), "w").close()
        open(os.path.join(td, "pic001.png"), "w").close()  # ชื่อรูปไม่ชนชื่อวิดีโอ
        assert next_vid_path(td) == os.path.join(td, "vid002.webm")


def test_app_video_wired():
    import generate
    import app
    assert app.txt2vid is generate.txt2vid
    assert set(generate.VIDEO_MODELS) <= set(app.MODEL_IDS.values())
    for mid in generate.VIDEO_MODELS:
        assert app.MODEL_SIZES[mid][0] in ("256", "480")


def test_apply_out_dir():
    import tempfile
    import types
    from app import App
    calls = []

    class Stub:
        def __init__(self, text=""):
            self.text = text
        def configure(self, text=""):
            self.text = text
        def get(self):
            return self.text
        def delete(self, a, b=None):
            self.text = ""

    with tempfile.TemporaryDirectory() as td:
        target = os.path.join(td, "pics")
        os.makedirs(target)
        cwd = _in_tmp_cwd(td)
        try:
            self = types.SimpleNamespace(
                out_dir=".", out_label=Stub(), status=Stub(),
                out_entry=Stub(target),
                refresh_gallery=lambda: calls.append("refresh"))
            self.apply_out_dir = types.MethodType(App.apply_out_dir, self)
            from app import load_out_dir
            assert App.apply_out_dir(self, target) is True
            assert self.out_dir == os.path.normpath(target)
            assert load_out_dir() == os.path.normpath(target)
            assert calls == ["refresh"]
            App.on_use_typed_dir(self)
            assert self.out_entry.text == ""
            assert App.apply_out_dir(self, os.path.join(td, "nope")) is False
            assert self.out_dir == os.path.normpath(target)  # ค่าเดิมไม่เปลี่ยน
            self.out_entry.text = ""
            App.on_use_typed_dir(self)
            assert "วาง path" in self.status.text
        finally:
            os.chdir(cwd)


def test_model_menu_consistent():
    from app import MODEL_IDS, MODEL_SIZES
    assert set(MODEL_IDS.values()) == set(MODEL_SIZES), (MODEL_IDS, MODEL_SIZES)
    assert "qwen21" in MODEL_IDS.values()
    assert MODEL_SIZES["qwen21"] == ["512", "768", "1024"]


def test_app_batch_wired():
    import generate
    import app
    assert app.txt2img_batch is generate.txt2img_batch
    assert app.txt2img is generate.txt2img


FULL_SETTINGS = {"prompt": "a cat astronaut", "negative": "blurry",
                 "model": "anima-turbo", "size": "1024", "ratio": "9:16",
                 "count": "4", "lora": "some-lora", "lora_strength": 0.8,
                 "steps": 8, "cfg": 1.5, "seed": "123", "out_dir": "",
                 "mode": "แปลงรูป", "init_img": "C:/tmp/in.png",
                 "style": "สงกรานต์", "strength": 0.6,
                 "keep_face": True, "face_strength": 0.7, "upscaler": "RealESRGAN_x4plus"}


def test_settings_roundtrip():
    from app import load_settings, save_settings
    with tempfile.TemporaryDirectory() as td:
        cwd = _in_tmp_cwd(td)
        try:
            save_settings(dict(FULL_SETTINGS))
            assert load_settings() == FULL_SETTINGS
        finally:
            os.chdir(cwd)


def test_normalize_settings_falls_back():
    from app import default_settings, normalize_settings
    d = default_settings()
    assert normalize_settings(None) == d  # ไฟล์พัง/ไม่ใช่ dict
    assert normalize_settings("oops") == d
    bad = {"prompt": 123, "negative": None, "model": "nope", "size": "9999",
           "ratio": "2:3", "count": "9", "lora": 7, "lora_strength": 99,
           "steps": -5, "cfg": 0.0, "seed": 0, "out_dir": 5,
           "mode": "ลบรูป", "init_img": 5, "style": "ไม่มี", "strength": 99,
           "keep_face": "yes", "face_strength": 5}
    got = normalize_settings(bad)
    assert got["prompt"] == "123" and got["negative"] == "None"
    assert got["model"] == "sd-turbo" and got["size"] == "512"
    assert got["ratio"] == "1:1" and got["count"] == "1"
    assert got["lora"] == "7"
    assert got["lora_strength"] == 2.0 and got["steps"] == 1
    assert got["cfg"] == 1.0 and got["seed"] == "0"
    assert got["out_dir"] == "5"
    assert got["mode"] == "เจนรูป" and got["init_img"] == "5"
    assert got["style"] == "(ไม่ใช้สไตล์)" and got["strength"] == 0.95
    assert got["keep_face"] is False and got["face_strength"] == 1.0
    # size ต้องอยู่ในรายการของโมเดลนั้น
    assert normalize_settings({"model": "sdxl-turbo", "size": "256"})["size"] == "512"
    assert normalize_settings({"model": "sdxl-turbo", "size": "768"})["size"] == "768"


def test_save_out_dir_merges():
    from app import load_settings, save_out_dir, save_settings
    with tempfile.TemporaryDirectory() as td:
        target = os.path.join(td, "pics")
        os.makedirs(target)
        cwd = _in_tmp_cwd(td)
        try:
            save_settings(dict(FULL_SETTINGS))
            save_out_dir(target)
            got = load_settings()
            assert got["out_dir"] == target
            assert got["prompt"] == FULL_SETTINGS["prompt"]  # ค่าอื่นต้องไม่หาย
            assert got["steps"] == FULL_SETTINGS["steps"]
        finally:
            os.chdir(cwd)


def test_collect_settings_maps_widgets():
    import types
    from app import App

    class Get:
        def __init__(self, v):
            self.v = v
        def get(self, *a):
            return self.v

    self = types.SimpleNamespace(
        prompt=Get("a cat "), negative=Get(" blurry "),
        model=Get("Anima Turbo (สวย ~45 วิ)"), size=Get("1024"),
        ratio=Get("9:16"), count=Get("4"), lora=Get("some-lora"),
        lora_strength=Get(0.8), steps=Get(8.0), cfg=Get(1.0),
        seed=Get(" 123 "), out_dir="mydir", mode_btn=Get("แปลงรูป"),
        style=Get("สงกรานต์"), strength=Get(0.6), init_img_path="C:/tmp/in.png",
        keep_face=Get(1), face_strength=Get(0.7),
        upscaler_menu=Get("RealESRGAN_x4plus"))
    assert App.collect_settings(self) == {
        "prompt": "a cat", "negative": "blurry", "model": "anima-turbo",
        "size": "1024", "ratio": "9:16", "count": "4", "lora": "some-lora",
        "lora_strength": 0.8, "steps": 8, "cfg": 1.0, "seed": "123",
        "out_dir": "mydir", "mode": "แปลงรูป", "init_img": "C:/tmp/in.png",
        "style": "สงกรานต์", "strength": 0.6,
        "keep_face": True, "face_strength": 0.7, "upscaler": "RealESRGAN_x4plus"}


def test_restore_settings_applies():
    import types
    from app import MODEL_SIZES, App, save_settings

    class W:
        def __init__(self, v=""):
            self.v = v
            self.cfg = {}
        def get(self, *a):
            return self.v
        def set(self, v):
            self.v = v
        def delete(self, *a):
            self.v = ""
        def insert(self, *a):
            self.v = a[-1] if a else ""
        def pack(self, **kw):
            self.cfg["packed"] = kw
        def pack_forget(self):
            self.cfg["packed"] = None
        def select(self):
            self.cfg["selected"] = True
        def deselect(self):
            self.cfg["selected"] = False
        def configure(self, **kw):
            self.cfg.update(kw)
            if "values" in kw:
                self.values = kw["values"]

    def make_ns():
        ns = types.SimpleNamespace(
            prompt=W(), negative=W(), model=W(), size=W(), ratio=W(),
            count=W(), lora=W(), lora_strength=W(1.0), lora_val=W(),
            steps=W(4), steps_val=W(), cfg=W(1.0), cfg_val=W(), seed=W(),
            mode_btn=W(), convert_frame=W(), init_label=W(), style=W(),
            strength=W(0.6), strength_val=W(), btn=W(), size_label=W(),
            keep_face=W(), face_strength=W(0.6), face_strength_val=W(),
            _lora_names=["(ไม่ใช้)", "my-lora"])
        ns._apply_mode = types.MethodType(App._apply_mode, ns)
        return ns

    with tempfile.TemporaryDirectory() as td:
        cwd = _in_tmp_cwd(td)
        try:
            init = os.path.join(td, "in.png")
            open(init, "w").close()
            save_settings({"prompt": "p1", "negative": "n1",
                           "model": "anima-turbo", "size": "1024",
                           "ratio": "9:16", "count": "4", "lora": "my-lora",
                           "lora_strength": 0.8, "steps": 8, "cfg": 1.5,
                           "seed": "7", "out_dir": "", "mode": "แปลงรูป",
                           "init_img": init, "style": "สงกรานต์", "strength": 0.7,
                           "keep_face": True, "face_strength": 0.8})
            ns = make_ns()
            App._restore_settings(ns)
            assert ns.prompt.v == "p1" and ns.negative.v == "n1"
            assert ns.model.v == "Anima Turbo (สวย ~45 วิ)"
            assert ns.size.values == MODEL_SIZES["anima-turbo"]
            assert ns.size.v == "1024"
            assert ns.ratio.v == "9:16" and ns.count.v == "4"
            assert ns.lora.v == "my-lora"
            assert ns.lora_strength.v == 0.8 and ns.steps.v == 8
            assert ns.cfg.v == 1.5 and ns.seed.v == "7"
            assert ns.mode_btn.v == "แปลงรูป" and ns.style.v == "สงกรานต์"
            assert ns.strength.v == 0.7
            assert ns.strength_val.cfg["text"] == "0.7"
            assert ns.init_label.cfg["text"] == "in.png"
            assert ns.keep_face.cfg["selected"] is True
            assert ns.face_strength.v == 0.8
            assert ns.face_strength_val.cfg["text"] == "0.8"
            assert ns.convert_frame.cfg.get("packed") is not None
            assert ns.btn.cfg["text"] == "แปลงรูป"
            assert ns.steps_val.cfg["text"] == "8"
            assert ns.cfg_val.cfg["text"] == "1.5"
            # LoRA ที่ถูกลบไปแล้ว → กลับเป็น (ไม่ใช้), โมเดลพัง → sd-turbo
            save_settings({"model": "nope", "lora": "gone-lora"})
            ns = make_ns()
            App._restore_settings(ns)
            assert ns.model.v == "SD-Turbo (เร็ว ~4 วิ)"
            assert ns.lora.v == "(ไม่ใช้)"
            assert ns.mode_btn.v == "เจนรูป" and ns.style.v == "(ไม่ใช้สไตล์)"
            assert ns.convert_frame.cfg.get("packed") is None
            assert ns.btn.cfg["text"] == "เจนรูป"
            assert ns.init_label.cfg["text"] == "ยังไม่เลือกรูป"
            assert ns.keep_face.cfg["selected"] is False
            assert ns.face_strength.v == 0.6
        finally:
            os.chdir(cwd)


def test_log_startup_error():
    from app import log_startup_error
    with tempfile.TemporaryDirectory() as td:
        cwd = _in_tmp_cwd(td)
        try:
            try:
                raise RuntimeError("boom-test")
            except RuntimeError:
                log_startup_error()
            with open("error.log", encoding="utf-8") as f:
                assert "boom-test" in f.read()
        finally:
            os.chdir(cwd)




def test_on_cancel_sets_event():
    import threading
    import types
    from app import App

    class Stub:
        def __init__(self):
            self.text = ""
        def configure(self, text=""):
            self.text = text

    self = types.SimpleNamespace(cancel_event=threading.Event(), status=Stub())
    App.on_cancel(self)
    assert self.cancel_event.is_set()
    assert "ยกเลิก" in self.status.text


def test_work_cancelled_shows_cancelled():
    import types
    import app
    from app import App, GenerationCancelled
    calls = []

    class Stub:
        def __init__(self):
            self.kw = []
        def configure(self, **kw):
            self.kw.append(kw)
        def stop(self):
            calls.append("stop")

    def boom(*a, **k):
        raise GenerationCancelled()

    real = app.txt2img
    app.txt2img = boom
    try:
        status, btn, cancel_btn, progress, animate_btn = Stub(), Stub(), Stub(), Stub(), Stub()
        upscale_btn = Stub()
        self = types.SimpleNamespace(
            out_dir=".", cancel_event=None,
            after=lambda ms, fn, *a: calls.append(fn.__name__),
            status=status, btn=btn, cancel_btn=cancel_btn, progress=progress,
            animate_btn=animate_btn, upscale_btn=upscale_btn)
        self.show_cancelled = types.MethodType(App.show_cancelled, self)
        self._gen_done = types.MethodType(App._gen_done, self)
        App.work(self, "p", 4, None, 512, 1.0, "", "sd-turbo")
        assert "show_cancelled" in calls, calls
        self.show_cancelled = types.MethodType(App.show_cancelled, self)
        App.show_cancelled(self)
        assert any("ยกเลิกแล้ว" in d.get("text", "") for d in status.kw), status.kw
        assert {"state": "normal"} in btn.kw, btn.kw
        assert {"state": "disabled"} in cancel_btn.kw, cancel_btn.kw
        assert {"state": "normal"} in animate_btn.kw, animate_btn.kw
        assert self.cancel_event is None
    finally:
        app.txt2img = real


def test_app_img2img_wired():
    import generate
    import app
    assert app.img2img is generate.img2img
    assert app.apply_style is generate.apply_style
    assert app.NO_STYLE == generate.NO_STYLE
    assert set(generate.STYLE_PRESETS) == {"สงกรานต์", "ลอยกระทง", "งานวัด",
                                           "Diwali", "Holi", "คาร์นิวัล"}
    assert (app.MODE_TXT, app.MODE_CONVERT) == ("เจนรูป", "แปลงรูป")
    assert app.IP_ADAPTER_MODELS == ("sdxl-turbo", "sdxl-base")


def test_app_img2vid_wired():
    import generate
    import app
    assert app.img2vid is generate.img2vid
    assert app.fit_video_size is generate.fit_video_size
    assert app.I2V_MODELS == ("wan22-5b",)


def test_flow_url():
    from app import FLOW_URL
    assert FLOW_URL == "https://flow.google.com"


def test_copy_to_flow():
    import tempfile
    from app import FLOW_EXPORT_SUBDIR, copy_to_flow
    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, "pic001.png")
        with open(src, "wb") as f:
            f.write(b"fake-png-bytes")
        dest = copy_to_flow(src, td)
        assert dest == os.path.join(td, FLOW_EXPORT_SUBDIR, "pic001.png")
        with open(dest, "rb") as f:
            assert f.read() == b"fake-png-bytes"
        # ชื่อชน → เติม _2 ไม่เขียนทับของเดิม
        dest2 = copy_to_flow(src, td)
        assert dest2 == os.path.join(td, FLOW_EXPORT_SUBDIR, "pic001_2.png")
        with open(dest, "rb") as f:
            assert f.read() == b"fake-png-bytes"


def test_copy_to_flow_missing_src():
    import tempfile
    from app import copy_to_flow
    with tempfile.TemporaryDirectory() as td:
        for bad in (os.path.join(td, "nope.png"), None, ""):
            try:
                copy_to_flow(bad, td)
            except FileNotFoundError:
                pass
            else:
                raise AssertionError(f"ต้อง raise FileNotFoundError: {bad!r}")


def test_on_export_flow():
    import tempfile
    import types
    import app
    from app import FLOW_URL, App

    class Stub:
        def __init__(self):
            self.text = ""
        def configure(self, text=""):
            self.text = text

    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, "pic001.png")
        with open(src, "wb") as f:
            f.write(b"fake-png-bytes")
        opened = []
        real_open = app.webbrowser.open
        app.webbrowser.open = lambda url: opened.append(url)
        try:
            self = types.SimpleNamespace(current_path=src, out_dir=td, status=Stub())
            App.on_export_flow(self)
            assert opened == [FLOW_URL], opened
            assert os.path.isfile(os.path.join(td, "flow", "pic001.png"))
            assert "flow" in self.status.text
            # ไม่มีรูป → ไม่เปิดเบราว์เซอร์
            opened.clear()
            self.current_path = None
            App.on_export_flow(self)
            assert opened == []
            assert "ไม่มีรูป" in self.status.text
        finally:
            app.webbrowser.open = real_open


def test_png_params_roundtrip():
    import tempfile
    from PIL import Image
    from app import gen_params, read_params, save_png
    settings = {"prompt": "ช้างน้อย cute", "negative": "blurry", "model": "sdxl-turbo",
                "steps": 4, "cfg": 1.0, "seed": "", "out_dir": "D:/secret", "count": "4"}
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "pic001.png")
        save_png(Image.new("RGB", (16, 8)), path, gen_params(settings, 123))
        p = read_params(path)
        assert p["prompt"] == "ช้างน้อย cute" and p["seed"] == "123", p
        assert "out_dir" not in p and "count" not in p, p  # ไม่ฝังที่เก็บรูปของเครื่อง
        with Image.open(path) as im:
            assert "Seed: 123" in im.text["parameters"] and "Size: 16x8" in im.text["parameters"]
        plain = os.path.join(td, "plain.png")
        save_png(Image.new("RGB", (4, 4)), plain)
        assert read_params(plain) is None
        assert read_params(os.path.join(td, "nope.png")) is None
        bad = os.path.join(td, "bad.png")
        open(bad, "wb").write(b"not a png")
        assert read_params(bad) is None


def test_params_to_settings_merges_and_validates():
    from app import default_settings, params_to_settings
    cur = dict(default_settings(), out_dir="mine", count="2", prompt="old")
    s = params_to_settings({"prompt": "new", "model": "anima-turbo", "size": "1344",
                            "steps": 999, "seed": "42", "out_dir": "theirs", "count": "4",
                            "junk": 1}, cur)
    assert s["prompt"] == "new" and s["model"] == "anima-turbo" and s["size"] == "1344"
    assert s["steps"] == 30  # ค่าเกินช่วงถูกบีบ
    assert s["seed"] == "42"
    assert s["out_dir"] == "mine" and s["count"] == "2"  # คงค่าของเครื่องนี้
    assert "junk" not in s


def test_unique_path():
    import tempfile
    from app import unique_path
    with tempfile.TemporaryDirectory() as td:
        assert unique_path(td, "a_up.png") == os.path.join(td, "a_up.png")
        open(os.path.join(td, "a_up.png"), "w").close()
        open(os.path.join(td, "a_up_2.png"), "w").close()
        assert unique_path(td, "a_up.png") == os.path.join(td, "a_up_3.png")


def test_model_defaults_consistent():
    from app import MODEL_DEFAULTS, MODEL_IDS, MODEL_SIZES
    assert set(MODEL_DEFAULTS) <= set(MODEL_IDS.values())
    for mid, d in MODEL_DEFAULTS.items():
        assert d["size"] in MODEL_SIZES[mid], (mid, d)
        assert 1 <= d["steps"] <= 30


def test_on_model_change_uses_table():
    import types
    from app import App

    class W:
        def __init__(self, v=None):
            self.v = v
            self.cfg = {}
        def set(self, v):
            self.v = v
        def get(self):
            return self.v
        def configure(self, **kw):
            self.cfg.update(kw)

    ns = types.SimpleNamespace(size=W(), steps=W(), steps_val=W(), cfg=W(3.3), cfg_val=W(),
                               ratio=W("1:1"), frames=W("9"), fps=W("16"), size_label=W(),
                               _apply_mode=lambda: None)
    App.on_model_change(ns, "Wan2.2 5B (วิดีโอ)")
    assert (ns.steps.v, ns.size.v, ns.cfg.v) == (30, "704", 5.0)
    assert (ns.ratio.v, ns.frames.v, ns.fps.v) == ("16:9", "17", "24")
    assert "วิดีโอ" in ns.size_label.cfg["text"]
    ns.cfg.v = 3.3
    App.on_model_change(ns, "SD-Turbo (เร็ว ~4 วิ)")
    assert (ns.steps.v, ns.size.v) == (4, "512")
    assert ns.cfg.v == 3.3  # โมเดลที่ไม่มีในตารางไม่แตะ CFG (เหมือนเดิม)


def test_on_reuse_params():
    import tempfile
    import types
    from PIL import Image
    from app import App, default_settings, gen_params, save_png

    class Stub:
        def __init__(self):
            self.text = ""
        def configure(self, text=""):
            self.text = text

    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "pic001.png")
        save_png(Image.new("RGB", (8, 8)), path,
                 gen_params(dict(default_settings(), prompt="from image"), 77))
        got = []
        ns = types.SimpleNamespace(current_path=path, status=Stub(),
                                   collect_settings=lambda: dict(default_settings(), out_dir="x"),
                                   _restore_settings=lambda s: got.append(s))
        App.on_reuse_params(ns)
        assert got and got[0]["prompt"] == "from image" and got[0]["seed"] == "77"
        assert got[0]["out_dir"] == "x"
        assert "77" in ns.status.text
        plain = os.path.join(td, "plain.png")
        Image.new("RGB", (8, 8)).save(plain)
        ns.current_path, got[:] = plain, []
        App.on_reuse_params(ns)
        assert got == [] and "ไม่มีค่า" in ns.status.text


def test_mask_helpers():
    from PIL import Image
    from mask_editor import mask_coverage, paint_stroke, tinted, view_scale
    assert view_scale(1800, 1280) == 0.5
    assert view_scale(100, 100) == 1.0  # ไม่ขยายรูปเล็ก
    m = Image.new("L", (100, 100), 0)
    assert mask_coverage(m) == 0
    paint_stroke(m, (0, 50), (100, 50), 10)
    assert m.getpixel((50, 50)) == 255 and m.getpixel((50, 5)) == 0
    assert 0.15 < mask_coverage(m) < 0.3
    paint_stroke(m, (0, 50), (100, 50), 10, value=0)
    assert mask_coverage(m) == 0
    m.paste(255, (0, 0, 50, 100))
    out = tinted(Image.new("RGB", (100, 100), (0, 0, 0)), m)
    assert out.getpixel((10, 10))[0] > 0 and out.getpixel((90, 10)) == (0, 0, 0)


if __name__ == "__main__":
    test_next_path_empty_dir()
    test_next_path_skips_existing()
    test_next_paths_reserves_ahead()
    test_default_out_dir()
    test_out_dir_persists()
    test_out_dir_falls_back()
    test_sysmon_sample_shape()
    test_fit_size()
    test_ctk_image_size()
    test_load_gallery_thumbs()
    test_apply_out_dir()
    test_app_batch_wired()
    test_settings_roundtrip()
    test_normalize_settings_falls_back()
    test_save_out_dir_merges()
    test_collect_settings_maps_widgets()
    test_restore_settings_applies()
    test_log_startup_error()
    test_app_video_wired()
    test_next_vid_paths()
    test_model_menu_consistent()
    test_on_cancel_sets_event()
    test_work_cancelled_shows_cancelled()
    test_app_img2img_wired()
    test_app_img2vid_wired()
    test_flow_url()
    test_copy_to_flow()
    test_copy_to_flow_missing_src()
    test_on_export_flow()
    test_png_params_roundtrip()
    test_params_to_settings_merges_and_validates()
    test_unique_path()
    test_model_defaults_consistent()
    test_on_model_change_uses_table()
    test_on_reuse_params()
    test_mask_helpers()
    print("app logic OK")
