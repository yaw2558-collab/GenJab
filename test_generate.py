"""Smoke test: backend (sd-cli + SD-Turbo) ต้องเจนรูปได้จริง — รันด้วย `python test_generate.py`."""
from generate import txt2img


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


def test_random_seed_differs():
    _, s1 = txt2img("a red apple on a wooden table", steps=1, size=256)
    _, s2 = txt2img("a red apple on a wooden table", steps=1, size=256)
    assert s1 != s2, "ไม่ส่ง seed แล้วได้ seed ซ้ำ (รูปจะเหมือนเดิม)"
    assert 0 <= s1 <= 2**31 - 1 and 0 <= s2 <= 2**31 - 1


if __name__ == "__main__":
    test_txt2img_returns_image()
    test_txt2img_negative_and_size()
    test_txt2img_anima()
    test_random_seed_differs()
    print("smoke OK")
