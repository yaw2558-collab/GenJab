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
                 "steps": 8, "cfg": 1.5, "seed": "123", "out_dir": ""}


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
           "steps": -5, "cfg": 0.0, "seed": 0, "out_dir": 5}
    got = normalize_settings(bad)
    assert got["prompt"] == "123" and got["negative"] == "None"
    assert got["model"] == "sd-turbo" and got["size"] == "512"
    assert got["ratio"] == "1:1" and got["count"] == "1"
    assert got["lora"] == "7"
    assert got["lora_strength"] == 2.0 and got["steps"] == 1
    assert got["cfg"] == 1.0 and got["seed"] == "0"
    assert got["out_dir"] == "5"
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
        seed=Get(" 123 "), out_dir="mydir")
    assert App.collect_settings(self) == {
        "prompt": "a cat", "negative": "blurry", "model": "anima-turbo",
        "size": "1024", "ratio": "9:16", "count": "4", "lora": "some-lora",
        "lora_strength": 0.8, "steps": 8, "cfg": 1.0, "seed": "123",
        "out_dir": "mydir"}


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
        def configure(self, **kw):
            self.cfg.update(kw)
            if "values" in kw:
                self.values = kw["values"]

    def make_ns():
        return types.SimpleNamespace(
            prompt=W(), negative=W(), model=W(), size=W(), ratio=W(),
            count=W(), lora=W(), lora_strength=W(1.0), lora_val=W(),
            steps=W(4), steps_val=W(), cfg=W(1.0), cfg_val=W(), seed=W(),
            _lora_names=["(ไม่ใช้)", "my-lora"])

    with tempfile.TemporaryDirectory() as td:
        cwd = _in_tmp_cwd(td)
        try:
            save_settings({"prompt": "p1", "negative": "n1",
                           "model": "anima-turbo", "size": "1024",
                           "ratio": "9:16", "count": "4", "lora": "my-lora",
                           "lora_strength": 0.8, "steps": 8, "cfg": 1.5,
                           "seed": "7", "out_dir": ""})
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
            assert ns.steps_val.cfg["text"] == "8"
            assert ns.cfg_val.cfg["text"] == "1.5"
            # LoRA ที่ถูกลบไปแล้ว → กลับเป็น (ไม่ใช้), โมเดลพัง → sd-turbo
            save_settings({"model": "nope", "lora": "gone-lora"})
            ns = make_ns()
            App._restore_settings(ns)
            assert ns.model.v == "SD-Turbo (เร็ว ~4 วิ)"
            assert ns.lora.v == "(ไม่ใช้)"
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
        status, btn, cancel_btn, progress = Stub(), Stub(), Stub(), Stub()
        self = types.SimpleNamespace(
            out_dir=".", cancel_event=None,
            after=lambda ms, fn, *a: calls.append(fn.__name__),
            status=status, btn=btn, cancel_btn=cancel_btn, progress=progress)
        self.show_cancelled = types.MethodType(App.show_cancelled, self)
        self._gen_done = types.MethodType(App._gen_done, self)
        App.work(self, "p", 4, None, 512, 1.0, "", "sd-turbo")
        assert "show_cancelled" in calls, calls
        self.show_cancelled = types.MethodType(App.show_cancelled, self)
        App.show_cancelled(self)
        assert any("ยกเลิกแล้ว" in d.get("text", "") for d in status.kw), status.kw
        assert {"state": "normal"} in btn.kw, btn.kw
        assert {"state": "disabled"} in cancel_btn.kw, cancel_btn.kw
        assert self.cancel_event is None
    finally:
        app.txt2img = real


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
    print("app logic OK")
