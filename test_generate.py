"""Smoke test: backend (sd-cli + SD-Turbo) ต้องเจนรูปได้จริง — รันด้วย `python test_generate.py`."""
from generate import RATIOS, _batch_seeds, model_files, resolve_size, txt2img, txt2img_batch


def test_resolve_size_square():
    assert resolve_size(512) == (512, 512)
    assert resolve_size(512, "1:1") == (512, 512)


def test_resolve_size_portrait():
    assert resolve_size(512, "3:4") == (384, 512)
    assert resolve_size(512, "9:16") == (320, 512)
    assert resolve_size(1024, "3:4") == (768, 1024)
    assert resolve_size(1024, "9:16") == (576, 1024)
    assert set(RATIOS) == {"1:1", "3:4", "9:16", "16:9"}
    for size, ratio in ((256, "3:4"), (768, "3:4"), (256, "9:16"),
                        (768, "9:16"), (1024, "9:16")):
        w, h = resolve_size(size, ratio)
        assert h == size and w < h, (w, h)
        assert w % 64 == 0 and h % 64 == 0, (w, h)


def test_resolve_size_landscape():
    assert resolve_size(512, "16:9") == (512, 320)
    assert resolve_size(1024, "16:9") == (1024, 576)
    for size in (256, 512, 768, 1024):
        w, h = resolve_size(size, "16:9")
        assert w == size and h < w, (w, h)
        assert w % 64 == 0 and h % 64 == 0, (w, h)


def test_resolve_size_explicit_and_invalid():
    assert resolve_size(width=512, height=768) == (512, 768)
    assert resolve_size("512x768") == (512, 768)
    for bad in (lambda: resolve_size(512, "2:1"),
                lambda: resolve_size(width=512),
                lambda: resolve_size(size=0),
                lambda: resolve_size(width=-1, height=5)):
        try:
            bad()
        except ValueError:
            pass
        else:
            raise AssertionError("ควร raise ValueError")


def test_txt2img_returns_image():
    img, seed = txt2img("a red apple on a wooden table", steps=1, size=256, seed=7)
    assert seed == 7, seed
    assert img.size == (256, 256), img.size
    assert img.mode == "RGB", img.mode
    px = img.resize((16, 16)).tobytes()
    colors = {px[i:i + 3] for i in range(0, len(px), 3)}
    assert len(colors) > 10, "รูปที่ได้เป็นสีเดียว (เจนล้มเหลวแบบเงียบ?)"


def test_txt2img_negative_and_size():
    img, _ = txt2img("a blue bird on a branch", steps=1, size=512, seed=7,
                     negative="blurry, watermark", guidance=2.0)
    assert img.size == (512, 512), img.size
    px = img.tobytes()
    colors = {px[i:i + 3] for i in range(0, len(px), 3)}
    assert len(colors) > 10


def test_txt2img_anima():
    img, _ = txt2img("a red apple on a wooden table", steps=2, size=256, seed=7,
                     model="anima-turbo")
    assert img.size == (256, 256), img.size
    px = img.tobytes()
    colors = {px[i:i + 3] for i in range(0, len(px), 3)}
    assert len(colors) > 10


def test_txt2img_anima_base():
    img, _ = txt2img("a red apple on a wooden table", steps=2, size=256, seed=7,
                     model="anima-base")
    assert img.size == (256, 256), img.size
    px = img.tobytes()
    colors = {px[i:i + 3] for i in range(0, len(px), 3)}
    assert len(colors) > 10


def test_txt2img_anima_aesthetic():
    img, _ = txt2img("a red apple on a wooden table", steps=2, size=256, seed=7,
                     model="anima-aesthetic")
    assert img.size == (256, 256), img.size
    px = img.tobytes()
    colors = {px[i:i + 3] for i in range(0, len(px), 3)}
    assert len(colors) > 10


def test_txt2img_batch():
    results = txt2img_batch("a red apple on a wooden table", n=2, steps=1, size=256, seed=7)
    assert len(results) == 2
    assert [s for _, s in results] == [7, 8]
    imgs = [img for img, _ in results]
    assert all(img.size == (256, 256) for img in imgs)
    assert imgs[0].tobytes() != imgs[1].tobytes()
    colors = {imgs[0].tobytes()[i:i + 3] for i in range(0, len(imgs[0].tobytes()), 3)}
    assert len(colors) > 10


def test_txt2img_batch_invalid_count():
    try:
        txt2img_batch("x", n=0)
    except ValueError:
        return
    raise AssertionError("n=0 ควร raise ValueError")


def test_model_files_sdxl_turbo_env_override():
    import os
    import tempfile
    import generate
    with tempfile.TemporaryDirectory() as td:
        fake = os.path.join(td, "sd_xl_turbo_1.0_fp16.safetensors")
        open(fake, "w").close()
        old = generate.SDXL_TURBO
        generate.SDXL_TURBO = fake
        try:
            assert model_files("sdxl-turbo") == {"m": fake}
        finally:
            generate.SDXL_TURBO = old


def test_model_files_unknown_model():
    try:
        model_files("nope")
    except ValueError:
        return
    raise AssertionError("โมเดลไม่รู้จักควร raise ValueError")


def test_batch_seeds_sequential():
    assert _batch_seeds(7, 3) == [7, 8, 9]


def test_batch_seeds_never_repeat_or_overflow():
    assert _batch_seeds(2**31 + 5, 2) == [5, 6]
    assert _batch_seeds(2**31 - 1, 2) == [2**31 - 2, 2**31 - 1]
    assert _batch_seeds(-3, 2) == [2**31 - 3, 2**31 - 2]
    assert _batch_seeds(-1, 2) == [2**31 - 2, 2**31 - 1]
    auto = _batch_seeds(None, 4)
    assert len(set(auto)) == 4 and all(0 <= s <= 2**31 - 1 for s in auto)


def test_random_seed_differs():
    _, s1 = txt2img("a red apple on a wooden table", steps=1, size=256)
    _, s2 = txt2img("a red apple on a wooden table", steps=1, size=256)
    assert s1 != s2, "ไม่ส่ง seed แล้วได้ seed ซ้ำ (รูปจะเหมือนเดิม)"
    assert 0 <= s1 <= 2**31 - 1 and 0 <= s2 <= 2**31 - 1


if __name__ == "__main__":
    test_resolve_size_square()
    test_resolve_size_portrait()
    test_resolve_size_landscape()
    test_resolve_size_explicit_and_invalid()
    test_txt2img_returns_image()
    test_txt2img_negative_and_size()
    test_txt2img_anima()
    test_txt2img_anima_base()
    test_txt2img_anima_aesthetic()
    test_txt2img_batch()
    test_txt2img_batch_invalid_count()
    test_model_files_sdxl_turbo_env_override()
    test_model_files_unknown_model()
    test_batch_seeds_sequential()
    test_batch_seeds_never_repeat_or_overflow()
    test_random_seed_differs()
    print("smoke OK")
