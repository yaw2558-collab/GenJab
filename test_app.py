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


def test_app_batch_wired():
    import generate
    import app
    assert app.txt2img_batch is generate.txt2img_batch
    assert app.txt2img is generate.txt2img


if __name__ == "__main__":
    test_next_path_empty_dir()
    test_next_path_skips_existing()
    test_next_paths_reserves_ahead()
    test_default_out_dir()
    test_out_dir_persists()
    test_out_dir_falls_back()
    test_sysmon_sample_shape()
    test_fit_size()
    test_load_gallery_thumbs()
    test_apply_out_dir()
    test_app_batch_wired()
    print("app logic OK")
