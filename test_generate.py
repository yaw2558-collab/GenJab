"""Smoke test: backend (sd-cli + SD-Turbo) ต้องเจนรูปได้จริง — รันด้วย `python test_generate.py` (`--fast` ข้ามเทสเจนรูปจริงสำหรับ CI)."""
from generate import RATIOS, _batch_seeds, _extra_args, apply_style, fit_init_size, list_loras, lora_prompt, model_files, resolve_lora, resolve_size, txt2img, txt2img_batch, txt2vid


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


def test_model_files_qwen21():
    import os
    import tempfile
    import generate
    with tempfile.TemporaryDirectory() as td:
        diff = os.path.join(td, "Diffusion")
        te = os.path.join(td, "TextEncoder")
        ae = os.path.join(td, "AutoEncoder")
        os.makedirs(diff)
        os.makedirs(te)
        os.makedirs(ae)
        want = {"diffusion": os.path.join(diff, "qwen_image_2.1_bf16.safetensors"),
                "llm": os.path.join(te, "Qwen3VL-8B-Instruct-Q8_0.gguf"),
                "llm_vision": os.path.join(te, "mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf"),
                "vae": os.path.join(ae, "qwen_image_2.1_vae_bf16.safetensors")}
        for p in want.values():
            open(p, "w").close()
        old = generate.AMUSE_MODELS
        generate.AMUSE_MODELS = td
        try:
            assert model_files("qwen21") == want
            os.remove(want["vae"])
            try:
                model_files("qwen21")
            except FileNotFoundError:
                pass
            else:
                raise AssertionError("vae missing should raise FileNotFoundError")
        finally:
            generate.AMUSE_MODELS = old


def test_txt2img_qwen21():
    img, _ = txt2img("a red apple on a wooden table", steps=2, size=256, seed=7,
                     model="qwen21")
    assert img.size == (256, 256), img.size
    px = img.tobytes()
    colors = {px[i:i + 3] for i in range(0, len(px), 3)}
    assert len(colors) > 10


def test_model_files_iris3b():
    import os
    import tempfile
    import generate
    with tempfile.TemporaryDirectory() as td:
        diff = os.path.join(td, "Diffusion", "iris-3b")
        te = os.path.join(td, "TextEncoder")
        os.makedirs(diff)
        os.makedirs(te)
        want = {"diffusion": os.path.join(diff, "model.safetensors"),
                "llm": os.path.join(te, "Qwen3VL-4B-Instruct-Q8_0.gguf")}
        for p in want.values():
            open(p, "w").close()
        old = generate.AMUSE_MODELS
        generate.AMUSE_MODELS = td
        try:
            assert model_files("iris-3b") == want
            os.remove(want["llm"])
            try:
                model_files("iris-3b")
            except FileNotFoundError:
                pass
            else:
                raise AssertionError("llm missing should raise FileNotFoundError")
        finally:
            generate.AMUSE_MODELS = old


def test_model_files_minimax_h3():
    import os
    import tempfile
    import generate
    with tempfile.TemporaryDirectory() as td:
        diff = os.path.join(td, "Diffusion")
        te = os.path.join(td, "TextEncoder")
        ae = os.path.join(td, "AutoEncoder")
        os.makedirs(diff)
        os.makedirs(te)
        os.makedirs(ae)
        want = {"diffusion": os.path.join(diff, "minimax_h3_fl2va_pruned-Q8_0.gguf"),
                "llm": os.path.join(te, "qwen3vl_32b_minimax_h3-Q4_K_M.gguf"),
                "vae": os.path.join(ae, "minimax_h3_video_vae_fp16.safetensors"),
                "audio_vae": os.path.join(ae, "minimax_h3_audio_vae_fp32.safetensors")}
        for p in want.values():
            open(p, "w").close()
        old = generate.AMUSE_MODELS
        generate.AMUSE_MODELS = td
        try:
            assert model_files("minimax-h3") == want
            os.remove(want["vae"])
            try:
                model_files("minimax-h3")
            except FileNotFoundError:
                pass
            else:
                raise AssertionError("vae missing should raise FileNotFoundError")
        finally:
            generate.AMUSE_MODELS = old


def test_model_files_wan22_5b():
    import os
    import tempfile
    import generate
    with tempfile.TemporaryDirectory() as td:
        diff = os.path.join(td, "Diffusion")
        te = os.path.join(td, "TextEncoder", "UMT5-XXL")
        ae = os.path.join(td, "AutoEncoder", "Wan22")
        os.makedirs(diff)
        os.makedirs(te)
        os.makedirs(ae)
        want = {"diffusion": os.path.join(diff, "Wan2.2-TI2V-5B-Q8_0.gguf"),
                "t5xxl": os.path.join(te, "model.safetensors"),
                "vae": os.path.join(ae, "wan2.2_vae.safetensors")}
        for p in want.values():
            open(p, "w").close()
        nolocal = os.path.join(td, "nolocal")
        os.makedirs(nolocal)
        old = generate.AMUSE_MODELS
        old_local = generate.LOCAL_MODELS
        generate.AMUSE_MODELS = td
        generate.LOCAL_MODELS = nolocal
        try:
            assert model_files("wan22-5b") == want
            os.remove(want["t5xxl"])
            try:
                model_files("wan22-5b")
            except FileNotFoundError:
                pass
            else:
                raise AssertionError("t5xxl missing should raise FileNotFoundError")
        finally:
            generate.AMUSE_MODELS = old
            generate.LOCAL_MODELS = old_local


def test_txt2vid_invalid():
    import os
    import tempfile
    try:
        txt2vid("a cat", model="sd-turbo", output=os.path.join(tempfile.gettempdir(), "x.webm"))
    except ValueError:
        pass
    else:
        raise AssertionError("non-video model should raise ValueError")
    try:
        txt2vid("a cat", model="wan22-5b", frames=0,
                output=os.path.join(tempfile.gettempdir(), "x.webm"))
    except ValueError:
        pass
    else:
        raise AssertionError("frames=0 should raise ValueError")
    try:
        txt2vid("a cat", model="wan22-5b",
                output=os.path.join(tempfile.gettempdir(), "x.mp4"))
    except ValueError:
        pass
    else:
        raise AssertionError("mp4 output should raise ValueError")


def test_txt2vid_wan22_5b():
    import os
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "probe.webm")
        path, _ = txt2vid("a cat walking in a garden", model="wan22-5b",
                          width=480, height=272, frames=17, fps=16,
                          steps=2, seed=7, output=out)
        assert os.path.isfile(path), path
        assert os.path.getsize(path) > 0
        with open(path, "rb") as f:
            assert f.read(4).hex() == "1a45dfa3"


def test_txt2img_iris3b():
    img, _ = txt2img("a red apple on a wooden table", steps=2, size=256, seed=7,
                     model="iris-3b")
    assert img.size == (256, 256), img.size
    px = img.tobytes()
    colors = {px[i:i + 3] for i in range(0, len(px), 3)}
    assert len(colors) > 10




def test_txt2img_cancel_no_spawn():
    import os
    import subprocess
    import tempfile
    import threading
    import generate
    from generate import GenerationCancelled, txt2img
    calls = []
    real_run, real_popen = subprocess.run, subprocess.Popen

    def spy_run(*a, **k):
        calls.append("run")
        return real_run(*a, **k)

    def spy_popen(*a, **k):
        calls.append("popen")
        return real_popen(*a, **k)

    with tempfile.TemporaryDirectory() as td:
        fake_exe = os.path.join(td, "sd-cli.exe")
        fake_model = os.path.join(td, "m.safetensors")
        open(fake_exe, "w").close()
        open(fake_model, "w").close()
        old_cli, old_model = generate.SD_CLI, generate.MODEL
        generate.SD_CLI, generate.MODEL = fake_exe, fake_model
        subprocess.run, subprocess.Popen = spy_run, spy_popen
        try:
            ev = threading.Event()
            ev.set()
            try:
                txt2img("x", steps=1, size=256, seed=1, cancel_event=ev)
            except GenerationCancelled:
                pass
            else:
                raise AssertionError("pre-set event should raise GenerationCancelled")
        finally:
            subprocess.run, subprocess.Popen = real_run, real_popen
            generate.SD_CLI, generate.MODEL = old_cli, old_model
    assert calls == [], calls


def test_run_kills_on_cancel():
    import sys
    import threading
    import time
    from generate import GenerationCancelled, _run
    ev = threading.Event()

    def setter():
        time.sleep(0.3)
        ev.set()

    t = threading.Thread(target=setter, daemon=True)
    t0 = time.time()
    t.start()
    try:
        _run([sys.executable, "-c", "import time; time.sleep(15)"], ev)
    except GenerationCancelled:
        pass
    else:
        raise AssertionError("set event should raise GenerationCancelled")
    assert time.time() - t0 < 10, "kill took too long"


def test_run_success_with_event():
    import sys
    import threading
    from generate import _run
    p = _run([sys.executable, "-c", "print('hi')"], threading.Event())
    assert p.returncode == 0 and p.stdout.strip() == "hi", p



def test_run_drains_pipes():
    import sys
    import threading
    from generate import _run
    want = "x" * 100000
    p = _run([sys.executable, "-c", "import sys; sys.stdout.write('x'*100000)"],
             threading.Event())
    assert p.returncode == 0, p
    assert p.stdout == want, len(p.stdout)



def test_model_files_qwen21_turbo():
    import os
    import tempfile
    import generate
    with tempfile.TemporaryDirectory() as td:
        diff = os.path.join(td, "Diffusion")
        te = os.path.join(td, "TextEncoder")
        ae = os.path.join(td, "AutoEncoder")
        os.makedirs(diff)
        os.makedirs(te)
        os.makedirs(ae)
        turbo = os.path.join(td, "models")
        os.makedirs(turbo)
        fake = os.path.join(turbo, "qwen_image_2.1_turbo_bf16.safetensors")
        open(fake, "w").close()
        want = {"diffusion": fake,
                "llm": os.path.join(te, "Qwen3VL-8B-Instruct-Q8_0.gguf"),
                "llm_vision": os.path.join(te, "mmproj-Qwen3VL-8B-Instruct-Q8_0.gguf"),
                "vae": os.path.join(ae, "qwen_image_2.1_vae_bf16.safetensors")}
        for p in want.values():
            if p != fake:
                open(p, "w").close()
        old_models, old_local = generate.AMUSE_MODELS, generate.LOCAL_MODELS
        generate.AMUSE_MODELS, generate.LOCAL_MODELS = td, turbo
        try:
            assert model_files("qwen21-turbo") == want
            os.remove(want["vae"])
            try:
                model_files("qwen21-turbo")
            except FileNotFoundError:
                pass
            else:
                raise AssertionError("vae missing should raise FileNotFoundError")
            open(want["vae"], "w").close()
            old_env = os.environ.get("TEXT2IMAGE_QWEN_TURBO")
            os.environ["TEXT2IMAGE_QWEN_TURBO"] = fake
            try:
                assert model_files("qwen21-turbo")["diffusion"] == fake
            finally:
                if old_env is None:
                    os.environ.pop("TEXT2IMAGE_QWEN_TURBO", None)
                else:
                    os.environ["TEXT2IMAGE_QWEN_TURBO"] = old_env
        finally:
            generate.AMUSE_MODELS, generate.LOCAL_MODELS = old_models, old_local


def test_txt2img_qwen21_turbo():
    img, _ = txt2img("a red apple on a wooden table", steps=2, size=256, seed=7,
                     model="qwen21-turbo")
    assert img.size == (256, 256), img.size
    px = img.tobytes()
    colors = {px[i:i + 3] for i in range(0, len(px), 3)}
    assert len(colors) > 10



def test_model_files_flux2_klein():
    import os
    import tempfile
    import generate
    with tempfile.TemporaryDirectory() as td:
        turbo = td
        for fn in ("flux-2-klein-4b-Q8_0.gguf", "qwen3-4b-q4_k_m.gguf", "flux2-vae.safetensors"):
            open(os.path.join(turbo, fn), "w").close()
        want = {"diffusion": os.path.join(turbo, "flux-2-klein-4b-Q8_0.gguf"),
                "llm": os.path.join(turbo, "qwen3-4b-q4_k_m.gguf"),
                "vae": os.path.join(turbo, "flux2-vae.safetensors")}
        old_local = generate.LOCAL_MODELS
        generate.LOCAL_MODELS = turbo
        try:
            assert model_files("flux2-klein") == want
            os.remove(want["vae"])
            try:
                model_files("flux2-klein")
            except FileNotFoundError:
                pass
            else:
                raise AssertionError("vae missing should raise FileNotFoundError")
            open(os.path.join(turbo, "flux2-vae.safetensors"), "w").close()
            # Windows: file name case-insensitive, both spellings hit the same file.
        finally:
            generate.LOCAL_MODELS = old_local


def test_flux1dev_lora_uses_cpu_offload():
    import os
    import subprocess
    import tempfile
    import types
    import generate
    from PIL import Image
    calls = []
    real_run = subprocess.run

    def fake_run(cmd, **kw):
        calls.append(cmd)
        out = cmd[cmd.index("-o") + 1]
        Image.new("RGB", (8, 8)).save(out)
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    with tempfile.TemporaryDirectory() as td:
        open(os.path.join(td, "flux-ada.safetensors"), "w").close()
        fake_cli = os.path.join(td, "sd-cli.exe")
        open(fake_cli, "w").close()
        old_cli, old_dirs, old_mf = generate.SD_CLI, generate.LORA_ENV_DIRS, generate.model_files
        generate.SD_CLI = fake_cli
        generate.LORA_ENV_DIRS = [td]
        generate.model_files = lambda name: {"diffusion": "d", "clip_l": "c",
                                             "t5xxl": "t", "vae": "v"}
        subprocess.run = fake_run
        try:
            generate.txt2img("ada-wong test", steps=1, size=256, seed=1,
                             model="flux1-dev", lora="flux-ada")
            generate.txt2img("plain test", steps=1, size=256, seed=1,
                             model="flux1-dev")
        finally:
            subprocess.run = real_run
            generate.SD_CLI, generate.LORA_ENV_DIRS, generate.model_files = old_cli, old_dirs, old_mf
    assert "--offload-to-cpu" in calls[0]
    assert "--offload-to-cpu" not in calls[1]
def test_model_files_flux1_dev():
    import os
    import tempfile
    import generate
    with tempfile.TemporaryDirectory() as td:
        for fn in ("flux1-dev-fp8.safetensors", "clip_l.safetensors",
                   "t5xxl_fp8_e4m3fn.safetensors", "flux-vae-bf16.safetensors"):
            open(os.path.join(td, fn), "w").close()
        want = {"diffusion": os.path.join(td, "flux1-dev-fp8.safetensors"),
                "clip_l": os.path.join(td, "clip_l.safetensors"),
                "t5xxl": os.path.join(td, "t5xxl_fp8_e4m3fn.safetensors"),
                "vae": os.path.join(td, "flux-vae-bf16.safetensors")}
        old_local = generate.LOCAL_MODELS
        generate.LOCAL_MODELS = td
        try:
            assert model_files("flux1-dev") == want
            os.remove(want["vae"])
            try:
                model_files("flux1-dev")
            except FileNotFoundError:
                pass
            else:
                raise AssertionError("vae missing should raise FileNotFoundError")
            open(os.path.join(td, "flux-vae-bf16.safetensors"), "w").close()
            old_env = os.environ.get("TEXT2IMAGE_FLUX1_DEV")
            os.environ["TEXT2IMAGE_FLUX1_DEV"] = os.path.join(td, "flux1-dev-fp8.safetensors")
            try:
                assert model_files("flux1-dev")["diffusion"] == os.path.join(td, "flux1-dev-fp8.safetensors")
            finally:
                if old_env is None:
                    os.environ.pop("TEXT2IMAGE_FLUX1_DEV", None)
                else:
                    os.environ["TEXT2IMAGE_FLUX1_DEV"] = old_env
        finally:
            generate.LOCAL_MODELS = old_local
def test_txt2img_flux2_klein():
    img, _ = txt2img("a red apple on a wooden table", steps=2, size=256, seed=7,
                     model="flux2-klein")
    assert img.size == (256, 256), img.size
    px = img.tobytes()
    colors = {px[i:i + 3] for i in range(0, len(px), 3)}
    assert len(colors) > 10


def test_txt2vid_invalid_without_sdcli():
    """Arg validation must raise ValueError even when sd-cli is missing (CI has no Amuse)."""
    import os
    import tempfile
    import generate
    old = generate.SD_CLI
    generate.SD_CLI = os.path.join(tempfile.gettempdir(), "nonexistent-sdcli.exe")
    assert not os.path.isfile(generate.SD_CLI)
    try:
        cases = [
            lambda: txt2vid("a cat", model="sd-turbo",
                            output=os.path.join(tempfile.gettempdir(), "x.webm")),
            lambda: txt2vid("a cat", model="wan22-5b", frames=0,
                            output=os.path.join(tempfile.gettempdir(), "x.webm")),
            lambda: txt2vid("a cat", model="wan22-5b", fps=0,
                            output=os.path.join(tempfile.gettempdir(), "x.webm")),
            lambda: txt2vid("a cat", model="wan22-5b", width=0,
                            output=os.path.join(tempfile.gettempdir(), "x.webm")),
            lambda: txt2vid("a cat", model="wan22-5b",
                            output=os.path.join(tempfile.gettempdir(), "x.mp4")),
        ]
        for bad in cases:
            try:
                bad()
            except ValueError:
                pass
            else:
                raise AssertionError("invalid video args should raise ValueError without sd-cli")
    finally:
        generate.SD_CLI = old
def test_style_presets_shape():
    from generate import NO_STYLE, STYLE_PRESETS
    assert NO_STYLE == "(ไม่ใช้สไตล์)"
    assert set(STYLE_PRESETS) == {"สงกรานต์", "ลอยกระทง", "งานวัด",
                                  "Diwali", "Holi", "คาร์นิวัล"}
    for name, frag in STYLE_PRESETS.items():
        assert set(frag) == {"prompt", "negative"}, name
        assert frag["prompt"].strip() and frag["negative"].strip(), name
        assert frag["prompt"].isascii() and frag["negative"].isascii(), name


def test_apply_style_combines():
    from generate import NO_STYLE, STYLE_PRESETS, apply_style
    p, n = apply_style("a portrait", "blurry", "สงกรานต์")
    assert p == "a portrait, " + STYLE_PRESETS["สงกรานต์"]["prompt"], p
    assert n == "blurry, " + STYLE_PRESETS["สงกรานต์"]["negative"], n
    p, n = apply_style("", "", "Holi")
    assert (p, n) == (STYLE_PRESETS["Holi"]["prompt"],
                      STYLE_PRESETS["Holi"]["negative"])
    assert apply_style("a", "b", None) == ("a", "b")
    assert apply_style("a", "b", NO_STYLE) == ("a", "b")
    try:
        apply_style("a", "b", "ไม่มีสไตล์นี้")
    except ValueError:
        pass
    else:
        raise AssertionError("สไตล์ไม่รู้จักควร raise ValueError")


def test_fit_init_size():
    assert fit_init_size(1024, 768, 512) == (512, 384)
    assert fit_init_size(768, 1024, 512) == (384, 512)
    assert fit_init_size(300, 300, 256) == (256, 256)
    assert fit_init_size(200, 100, 256) == (256, 128)
    w, h = fit_init_size(3000, 100, 512)
    assert (w, h) == (512, 64) and w % 64 == 0 and h % 64 == 0
    for bad in (lambda: fit_init_size(0, 5),
                lambda: fit_init_size(5, -1),
                lambda: fit_init_size(5, 5, 0)):
        try:
            bad()
        except ValueError:
            pass
        else:
            raise AssertionError("ขนาดไม่ถูกต้องควร raise ValueError")


def test_img2img_invalid_without_sdcli():
    """ตรวจ args ก่อนเช็ค sd-cli — CI ไม่มี Amuse ต้องได้ error ตรงเคส."""
    import os
    import tempfile
    import generate
    from generate import img2img
    old = generate.SD_CLI
    generate.SD_CLI = os.path.join(tempfile.gettempdir(), "nonexistent-sdcli.exe")
    assert not os.path.isfile(generate.SD_CLI)
    try:
        with tempfile.TemporaryDirectory() as td:
            init = os.path.join(td, "in.png")
            open(init, "w").close()
            missing = os.path.join(td, "nope.png")
            value_cases = [
                lambda: img2img(init, "x", strength=0),
                lambda: img2img(init, "x", strength=1),
                lambda: img2img(init, "x", strength=2),
                lambda: img2img(init, "x", strength="แรง"),
                lambda: img2img(init, "x", model="wan22-5b"),
                lambda: img2img(init, "x", width=512),
                lambda: img2img(init, "x", width=0, height=64),
            ]
            for bad in value_cases:
                try:
                    bad()
                except ValueError:
                    pass
                else:
                    raise AssertionError("args ผิดควร raise ValueError (ไม่มี sd-cli)")
            try:
                img2img(missing, "x")
            except FileNotFoundError:
                pass
            else:
                raise AssertionError("รูปต้นฉบับหายควร raise FileNotFoundError")
    finally:
        generate.SD_CLI = old


def test_img2img_sends_init_and_strength():
    import os
    import subprocess
    import tempfile
    import types
    import generate
    from PIL import Image
    calls = []
    real_run = subprocess.run

    def fake_run(cmd, **kw):
        calls.append(cmd)
        out = cmd[cmd.index("-o") + 1]
        Image.new("RGB", (8, 8)).save(out)
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    with tempfile.TemporaryDirectory() as td:
        fake_exe = os.path.join(td, "sd-cli.exe")
        fake_model = os.path.join(td, "sd_turbo.safetensors")
        open(fake_exe, "w").close()
        open(fake_model, "w").close()
        init = os.path.join(td, "in.png")
        Image.new("RGB", (200, 100), (10, 20, 30)).save(init)
        old_cli, old_model = generate.SD_CLI, generate.MODEL
        generate.SD_CLI, generate.MODEL = fake_exe, fake_model
        subprocess.run = fake_run
        try:
            img, seed = generate.img2img(init, "festive", strength=0.6, steps=1,
                                         size=256, seed=3)
        finally:
            subprocess.run = real_run
            generate.SD_CLI, generate.MODEL = old_cli, old_model
    assert seed == 3 and img.size == (8, 8)
    cmd = calls[0]
    assert cmd[cmd.index("-i") + 1] == init, cmd
    assert cmd[cmd.index("--strength") + 1] == "0.6", cmd
    assert cmd[cmd.index("-W") + 1] == "256", cmd
    assert cmd[cmd.index("-H") + 1] == "128", cmd


def test_ip_adapter_files_found_and_missing():
    import os
    import tempfile
    import generate
    with tempfile.TemporaryDirectory() as td:
        old = generate.LOCAL_MODELS
        generate.LOCAL_MODELS = td
        old_env = (os.environ.pop("TEXT2IMAGE_IP_ADAPTER", None),
                   os.environ.pop("TEXT2IMAGE_CLIP_VISION", None))
        try:
            try:
                generate.ip_adapter_files()
            except FileNotFoundError as e:
                assert "ip-adapter-plus_sdxl_vit-h" in str(e), e
                assert "huggingface.co/h94/IP-Adapter" in str(e), e
            else:
                raise AssertionError("ไฟล์ขาดควร raise FileNotFoundError")
            a = os.path.join(td, "ip-adapter-plus_sdxl_vit-h.safetensors")
            v = os.path.join(td, "clip_vision_h.safetensors")
            open(a, "w").close()
            open(v, "w").close()
            assert generate.ip_adapter_files() == {"ip_adapter": a, "clip_vision": v}
        finally:
            generate.LOCAL_MODELS = old
            for k, v in (("TEXT2IMAGE_IP_ADAPTER", old_env[0]),
                         ("TEXT2IMAGE_CLIP_VISION", old_env[1])):
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


def test_img2img_face_invalid_without_sdcli():
    import os
    import tempfile
    import generate
    from generate import img2img
    old = generate.SD_CLI
    generate.SD_CLI = os.path.join(tempfile.gettempdir(), "nonexistent-sdcli.exe")
    assert not os.path.isfile(generate.SD_CLI)
    try:
        with tempfile.TemporaryDirectory() as td:
            init = os.path.join(td, "in.png")
            open(init, "w").close()
            missing = os.path.join(td, "nope.png")
            value_cases = [
                lambda: img2img(init, "x", face_ref=init),  # sd-turbo ใช้คงหน้าไม่ได้
                lambda: img2img(init, "x", model="sdxl-turbo",
                                face_ref=init, face_strength=0),
                lambda: img2img(init, "x", model="sdxl-turbo",
                                face_ref=init, face_strength=1.5),
                lambda: img2img(init, "x", model="sdxl-turbo",
                                face_ref=init, face_strength="แรง"),
            ]
            for bad in value_cases:
                try:
                    bad()
                except ValueError:
                    pass
                else:
                    raise AssertionError("args คงหน้าผิดควร raise ValueError (ไม่มี sd-cli)")
            try:
                img2img(init, "x", model="sdxl-turbo", face_ref=missing)
            except FileNotFoundError:
                pass
            else:
                raise AssertionError("รูปอ้างอิงหายควร raise FileNotFoundError")
    finally:
        generate.SD_CLI = old


def test_img2img_face_sends_argv():
    import os
    import subprocess
    import tempfile
    import types
    import generate
    from PIL import Image
    calls = []
    real_run = subprocess.run

    def fake_run(cmd, **kw):
        calls.append(cmd)
        out = cmd[cmd.index("-o") + 1]
        Image.new("RGB", (8, 8)).save(out)
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    with tempfile.TemporaryDirectory() as td:
        fake_exe = os.path.join(td, "sd-cli.exe")
        fake_model = os.path.join(td, "sd_xl_turbo_1.0_fp16.safetensors")
        open(fake_exe, "w").close()
        open(fake_model, "w").close()
        a = os.path.join(td, "ip-adapter-plus_sdxl_vit-h.safetensors")
        v = os.path.join(td, "clip_vision_h.safetensors")
        open(a, "w").close()
        open(v, "w").close()
        init = os.path.join(td, "in.png")
        Image.new("RGB", (200, 100), (10, 20, 30)).save(init)
        old_cli, old_turbo, old_local = generate.SD_CLI, generate.SDXL_TURBO, generate.LOCAL_MODELS
        generate.SD_CLI, generate.SDXL_TURBO, generate.LOCAL_MODELS = fake_exe, fake_model, td
        subprocess.run = fake_run
        try:
            img, seed = generate.img2img(init, "festive", strength=0.6, steps=1,
                                         size=256, seed=3, model="sdxl-turbo",
                                         face_ref=init, face_strength=0.7)
        finally:
            subprocess.run = real_run
            generate.SD_CLI, generate.SDXL_TURBO, generate.LOCAL_MODELS = old_cli, old_turbo, old_local
    assert seed == 3 and img.size == (8, 8)
    cmd = calls[0]
    assert cmd[cmd.index("--ip-adapter") + 1] == a, cmd
    assert cmd[cmd.index("--clip_vision") + 1] == v, cmd
    assert cmd[cmd.index("--ip-adapter-image") + 1] == os.path.abspath(init), cmd
    assert cmd[cmd.index("--ip-adapter-strength") + 1] == "0.7", cmd


def test_img2img_face_sdxl_turbo():
    import os
    import tempfile
    from PIL import Image, ImageDraw
    from generate import img2img
    with tempfile.TemporaryDirectory() as td:
        init = os.path.join(td, "in.png")
        base = Image.new("RGB", (256, 256), (200, 180, 150))
        ImageDraw.Draw(base).ellipse([88, 60, 168, 150], fill=(150, 100, 80))
        base.save(init)
        img, seed = img2img(init, "portrait photo", strength=0.5, steps=2,
                            size=256, seed=7, model="sdxl-turbo",
                            face_ref=init, face_strength=0.6)
    assert seed == 7, seed
    assert img.size == (256, 256), img.size
    px = img.tobytes()
    colors = {px[i:i + 3] for i in range(0, len(px), 3)}
    assert len(colors) > 10


def test_fit_video_size():
    from generate import fit_video_size
    assert fit_video_size(1024, 576, 512) == (512, 288)
    assert fit_video_size(576, 1024, 512) == (288, 512)
    assert fit_video_size(1024, 576, 256) == (256, 144)
    w, h = fit_video_size(3000, 100, 512)
    assert (w, h) == (512, 16) and w % 16 == 0 and h % 16 == 0
    for bad in (lambda: fit_video_size(0, 5),
                lambda: fit_video_size(5, 5, 0)):
        try:
            bad()
        except ValueError:
            pass
        else:
            raise AssertionError("ขนาดไม่ถูกต้องควร raise ValueError")


def test_model_files_wan22_local_first():
    import os
    import tempfile
    import generate
    with tempfile.TemporaryDirectory() as td:
        want = {"diffusion": os.path.join(td, "Wan2.2-TI2V-5B-Q8_0.gguf"),
                "t5xxl": os.path.join(td, "umt5-xxl-encoder-Q8_0.gguf"),
                "vae": os.path.join(td, "wan2.2_vae.safetensors")}
        for p in want.values():
            open(p, "w").close()
        old_local = generate.LOCAL_MODELS
        generate.LOCAL_MODELS = td
        try:
            assert model_files("wan22-5b") == want
        finally:
            generate.LOCAL_MODELS = old_local


def test_img2vid_invalid_without_sdcli():
    import os
    import tempfile
    import generate
    from generate import img2vid
    old = generate.SD_CLI
    generate.SD_CLI = os.path.join(tempfile.gettempdir(), "nonexistent-sdcli.exe")
    assert not os.path.isfile(generate.SD_CLI)
    try:
        with tempfile.TemporaryDirectory() as td:
            init = os.path.join(td, "in.png")
            open(init, "w").close()
            missing = os.path.join(td, "nope.png")
            out = os.path.join(td, "x.webm")
            value_cases = [
                lambda: img2vid(missing, "x", output=out),  # รูปต้นฉบับหาย
                lambda: img2vid(init, "x", model="sd-turbo", output=out),
                lambda: img2vid(init, "x", model="minimax-h3", output=out),
                lambda: img2vid(init, "x", frames=0, output=out),
                lambda: img2vid(init, "x", fps=0, output=out),
                lambda: img2vid(init, "x", output=os.path.join(td, "x.mp4")),
            ]
            for bad in value_cases:
                try:
                    bad()
                except (ValueError, FileNotFoundError):
                    pass
                else:
                    raise AssertionError("args ผิดควร raise (ไม่มี sd-cli)")
    finally:
        generate.SD_CLI = old


def test_img2vid_sends_argv():
    import os
    import subprocess
    import tempfile
    import types
    import generate
    from PIL import Image
    calls = []
    real_run = subprocess.run

    def fake_run(cmd, **kw):
        calls.append(cmd)
        out = cmd[cmd.index("-o") + 1]
        with open(out, "wb") as f:
            f.write(bytes.fromhex("1a45dfa3"))
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    with tempfile.TemporaryDirectory() as td:
        fake_exe = os.path.join(td, "sd-cli.exe")
        open(fake_exe, "w").close()
        trio = {"diffusion": os.path.join(td, "Wan2.2-TI2V-5B-Q8_0.gguf"),
                "t5xxl": os.path.join(td, "umt5-xxl-encoder-Q8_0.gguf"),
                "vae": os.path.join(td, "wan2.2_vae.safetensors")}
        for p in trio.values():
            open(p, "w").close()
        init = os.path.join(td, "in.png")
        Image.new("RGB", (1024, 576), (10, 20, 30)).save(init)
        old_cli, old_local = generate.SD_CLI, generate.LOCAL_MODELS
        generate.SD_CLI, generate.LOCAL_MODELS = fake_exe, td
        subprocess.run = fake_run
        try:
            path, seed = generate.img2vid(init, "drift", size=512, frames=17,
                                          fps=16, steps=10, seed=5,
                                          output=os.path.join(td, "v.webm"))
        finally:
            subprocess.run = real_run
            generate.SD_CLI, generate.LOCAL_MODELS = old_cli, old_local
    assert seed == 5 and path.endswith("v.webm")
    cmd = calls[0]
    assert cmd[cmd.index("-M") + 1] == "vid_gen", cmd
    assert cmd[cmd.index("--diffusion-model") + 1] == trio["diffusion"], cmd
    assert cmd[cmd.index("--t5xxl") + 1] == trio["t5xxl"], cmd
    assert cmd[cmd.index("--vae") + 1] == trio["vae"], cmd
    assert cmd[cmd.index("-i") + 1] == os.path.abspath(init), cmd
    assert cmd[cmd.index("-W") + 1] == "512", cmd
    assert cmd[cmd.index("-H") + 1] == "288", cmd
    assert cmd[cmd.index("--video-frames") + 1] == "17", cmd
    assert cmd[cmd.index("--flow-shift") + 1] == "3.0", cmd
    assert cmd[cmd.index("--sampling-method") + 1] == "euler", cmd


def test_img2vid_wan22_tiny():
    import os
    import tempfile
    from PIL import Image, ImageDraw
    from generate import img2vid
    with tempfile.TemporaryDirectory() as td:
        init = os.path.join(td, "in.png")
        base = Image.new("RGB", (256, 144), (20, 30, 60))
        ImageDraw.Draw(base).ellipse([100, 40, 156, 100], fill=(200, 150, 80))
        base.save(init)
        out = os.path.join(td, "tiny.webm")
        path, seed = img2vid(init, "moon glowing softly", size=256, frames=9,
                             fps=16, steps=4, seed=7, output=out)
        assert os.path.isfile(path), path
        assert os.path.getsize(path) > 0
        with open(path, "rb") as f:
            assert f.read(4).hex() == "1a45dfa3"


def test_img2img_sd_turbo():
    import os
    import tempfile
    from PIL import Image, ImageDraw
    from generate import img2img
    with tempfile.TemporaryDirectory() as td:
        init = os.path.join(td, "in.png")
        base = Image.new("RGB", (256, 256), (200, 30, 30))
        ImageDraw.Draw(base).rectangle([64, 64, 192, 192], fill=(30, 60, 200))
        base.save(init)
        img, seed = img2img(init, "a red apple on a wooden table", strength=0.5,
                            steps=2, size=256, seed=7)
    assert seed == 7, seed
    assert img.size == (256, 256), img.size
    px = img.tobytes()
    colors = {px[i:i + 3] for i in range(0, len(px), 3)}
    assert len(colors) > 10


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
        test_txt2img_qwen21()
        test_txt2img_iris3b()
        test_txt2img_qwen21_turbo()
        test_txt2img_flux2_klein()
        test_txt2vid_wan22_5b()
        test_txt2img_batch()
        test_txt2img_batch_invalid_count()
        test_img2img_sd_turbo()
        test_img2img_face_sdxl_turbo()
        test_img2vid_wan22_tiny()
    test_lora_prompt_and_resolve()
    test_lora_invalid()
    test_model_files_sdxl_turbo_env_override()
    test_model_files_unknown_model()
    test_app_dir_source_and_frozen()
    test_resolve_sd_cli_bundled_and_env()
    test_model_files_sd_turbo_local_models()
    test_model_files_sdxl_base_env_override()
    test_extra_args_flag_mapping()
    test_subprocess_hides_console()
    test_txt2img_cancel_no_spawn()
    test_run_kills_on_cancel()
    test_run_success_with_event()
    test_run_drains_pipes()


    test_model_files_qwen21()
    test_model_files_iris3b()
    test_model_files_minimax_h3()
    test_model_files_wan22_5b()
    test_model_files_qwen21_turbo()
    test_model_files_flux2_klein()
    test_model_files_flux1_dev()
    test_flux1dev_lora_uses_cpu_offload()
    test_txt2vid_invalid()
    test_txt2vid_invalid_without_sdcli()
    test_batch_seeds_sequential()
    test_batch_seeds_never_repeat_or_overflow()
    test_style_presets_shape()
    test_apply_style_combines()
    test_fit_init_size()
    test_img2img_invalid_without_sdcli()
    test_img2img_sends_init_and_strength()
    test_ip_adapter_files_found_and_missing()
    test_img2img_face_invalid_without_sdcli()
    test_img2img_face_sends_argv()
    test_fit_video_size()
    test_model_files_wan22_local_first()
    test_img2vid_invalid_without_sdcli()
    test_img2vid_sends_argv()
    if backend:
        test_random_seed_differs()
    print("smoke OK" if backend else "fast OK")
