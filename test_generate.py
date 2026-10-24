"""Smoke test: backend (sd-cli + SD-Turbo) ต้องเจนรูปได้จริง — รันด้วย `python test_generate.py` (`--fast` ข้ามเทสเจนรูปจริงสำหรับ CI)."""
from generate import RATIOS, _batch_seeds, _extra_args, list_loras, lora_prompt, model_files, resolve_lora, resolve_size, txt2img, txt2img_batch


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


def test_lora_prompt_and_resolve():
    import os
    import tempfile
    import generate
    assert lora_prompt("a cat", None) == ("a cat", [])
    assert lora_prompt("a cat", "") == ("a cat", [])
    with tempfile.TemporaryDirectory() as td:
        fake = os.path.join(td, "my-style.safetensors")
        open(fake, "w").close()
        old = generate.LORA_ENV_DIRS
        generate.LORA_ENV_DIRS = [td]
        try:
            assert resolve_lora("my-style") == (td, "my-style")
            assert resolve_lora("my-style.safetensors") == (td, "my-style")
            assert resolve_lora(fake) == (td, "my-style")
            assert list_loras()["my-style"] == fake
            p, args = lora_prompt("a cat", "my-style", 0.8)
            assert p == "a cat <lora:my-style:0.8>", p
            assert args == ["--lora-model-dir", td], args
        finally:
            generate.LORA_ENV_DIRS = old


def test_lora_invalid():
    import generate
    old = generate.LORA_ENV_DIRS
    generate.LORA_ENV_DIRS = []
    try:
        for bad_call in (lambda: resolve_lora(""),
                         lambda: resolve_lora("no-such-lora-xyz"),
                         lambda: lora_prompt("a cat", "x", 0),
                         lambda: lora_prompt("a cat", "x", "แรง")):
            try:
                bad_call()
            except (ValueError, FileNotFoundError):
                pass
            else:
                raise AssertionError("ควร raise ValueError/FileNotFoundError")
    finally:
        generate.LORA_ENV_DIRS = old


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


def test_model_files_sdxl_base_env_override():
    import os
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        fake = os.path.join(td, "sdxl-base-f16.safetensors")
        open(fake, "w").close()
        old = os.environ.get("TEXT2IMAGE_SDXL_BASE")
        os.environ["TEXT2IMAGE_SDXL_BASE"] = fake
        try:
            assert model_files("sdxl-base") == {"m": fake}
        finally:
            if old is None:
                os.environ.pop("TEXT2IMAGE_SDXL_BASE", None)
            else:
                os.environ["TEXT2IMAGE_SDXL_BASE"] = old


def test_extra_args_flag_mapping():
    assert _extra_args({"m": "x"}) == []
    assert _extra_args({"m": "x", "llm": "L", "vae": "V"}) == ["--llm", "L", "--vae", "V"]
    assert _extra_args({"m": "x", "clip_l": "L", "clip_g": "G", "vae": "V"}) == [
        "--vae", "V", "--clip_l", "L", "--clip_g", "G"]


def test_txt2img_sdxl_base():
    img, _ = txt2img("a red apple on a wooden table", steps=2, size=256, seed=7,
                     negative="blurry, watermark", guidance=5.0, model="sdxl-base")
    assert img.size == (256, 256), img.size
    px = img.tobytes()
    colors = {px[i:i + 3] for i in range(0, len(px), 3)}
    assert len(colors) > 10


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


def test_app_dir_source_and_frozen():
    import os
    import sys
    import tempfile
    import generate
    assert generate.app_dir() == os.path.dirname(os.path.abspath(generate.__file__))
    with tempfile.TemporaryDirectory() as td:
        had_frozen = hasattr(sys, "frozen")
        old_frozen, old_exe = getattr(sys, "frozen", False), sys.executable
        sys.frozen = True
        sys.executable = os.path.join(td, "GenJab.exe")
        try:
            assert os.path.normcase(generate.app_dir()) == os.path.normcase(td)
        finally:
            if had_frozen:
                sys.frozen = old_frozen
            else:
                del sys.frozen
            sys.executable = old_exe


def test_resolve_sd_cli_bundled_and_env():
    import os
    import tempfile
    import generate
    with tempfile.TemporaryDirectory() as td:
        bundled = os.path.join(td, "runtime", "sd-cli.exe")
        os.makedirs(os.path.dirname(bundled))
        open(bundled, "w").close()
        old_app_dir = generate.app_dir
        old_env = os.environ.get("TEXT2IMAGE_SDCLI")
        os.environ.pop("TEXT2IMAGE_SDCLI", None)
        generate.app_dir = lambda: td
        try:
            assert generate.resolve_sd_cli() == bundled
            custom = os.path.join(td, "custom.exe")
            os.environ["TEXT2IMAGE_SDCLI"] = custom
            assert generate.resolve_sd_cli() == custom  # env ชนะแม้ไฟล์ไม่มี
        finally:
            generate.app_dir = old_app_dir
            if old_env is None:
                os.environ.pop("TEXT2IMAGE_SDCLI", None)
            else:
                os.environ["TEXT2IMAGE_SDCLI"] = old_env


def test_model_files_sd_turbo_local_models():
    import os
    import tempfile
    import generate
    with tempfile.TemporaryDirectory() as td:
        models = os.path.join(td, "models")
        os.makedirs(models)
        fake = os.path.join(models, "sd_turbo.safetensors")
        open(fake, "w").close()
        empty_home = os.path.join(td, "home")
        os.makedirs(empty_home)
        old_model, old_local = generate.MODEL, generate.LOCAL_MODELS
        old_home, old_profile = os.environ.get("HOME"), os.environ.get("USERPROFILE")
        generate.MODEL, generate.LOCAL_MODELS = "", models
        os.environ["HOME"] = empty_home
        os.environ["USERPROFILE"] = empty_home
        try:
            assert generate.model_files("sd-turbo") == {"m": fake}
        finally:
            generate.MODEL, generate.LOCAL_MODELS = old_model, old_local
            if old_home is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = old_home
            if old_profile is None:
                os.environ.pop("USERPROFILE", None)
            else:
                os.environ["USERPROFILE"] = old_profile


def test_subprocess_hides_console():
    import os
    import subprocess
    import tempfile
    import types
    import generate
    from PIL import Image
    calls = []
    real_run = subprocess.run

    def fake_run(cmd, **kw):
        calls.append(kw)
        out = cmd[cmd.index("-o") + 1]
        if "%d" in out:
            n = int(cmd[cmd.index("-b") + 1])
            for i in range(n):
                Image.new("RGB", (8, 8)).save(out % i)
        else:
            Image.new("RGB", (8, 8)).save(out)
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    with tempfile.TemporaryDirectory() as td:
        fake_exe = os.path.join(td, "sd-cli.exe")
        fake_model = os.path.join(td, "sd_turbo.safetensors")
        open(fake_exe, "w").close()
        open(fake_model, "w").close()
        old_cli, old_model = generate.SD_CLI, generate.MODEL
        generate.SD_CLI, generate.MODEL = fake_exe, fake_model
        subprocess.run = fake_run
        try:
            txt2img("x", steps=1, size=256, seed=1)
            txt2img_batch("x", n=2, steps=1, size=256, seed=1)
        finally:
            subprocess.run = real_run
            generate.SD_CLI, generate.MODEL = old_cli, old_model
    assert len(calls) == 2
    want = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    for kw in calls:
        assert kw.get("creationflags") == want, kw


if __name__ == "__main__":
    import sys
    # --fast: ข้ามเทสเจนรูปจริง (CI ไม่มี sd-cli/โมเดล)
    backend = "--fast" not in sys.argv
    test_resolve_size_square()
    test_resolve_size_portrait()
    test_resolve_size_landscape()
    test_resolve_size_explicit_and_invalid()
    if backend:
        test_txt2img_returns_image()
        test_txt2img_negative_and_size()
        test_txt2img_anima()
        test_txt2img_anima_base()
        test_txt2img_anima_aesthetic()
        test_txt2img_sdxl_base()
        test_txt2img_batch()
        test_txt2img_batch_invalid_count()
    test_lora_prompt_and_resolve()
    test_lora_invalid()
    test_model_files_sdxl_turbo_env_override()
    test_model_files_unknown_model()
    test_app_dir_source_and_frozen()
    test_resolve_sd_cli_bundled_and_env()
    test_model_files_sd_turbo_local_models()
    test_subprocess_hides_console()
    test_batch_seeds_sequential()
    test_batch_seeds_never_repeat_or_overflow()
    if backend:
        test_random_seed_differs()
    print("smoke OK" if backend else "fast OK")
