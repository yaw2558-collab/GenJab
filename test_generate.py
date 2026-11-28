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


def test_resolve_sd_cli_alt_order():
    import os
    import tempfile
    import generate
    with tempfile.TemporaryDirectory() as td:
        old_app_dir = generate.app_dir
        old_env = os.environ.get("TEXT2IMAGE_SDCLI_ALT")
        os.environ.pop("TEXT2IMAGE_SDCLI_ALT", None)
        generate.app_dir = lambda: td
        try:
            assert generate.resolve_sd_cli_alt() == ""  # ไม่มีเลย
            new = os.path.join(td, "sdcli-new", "bin", "sd-cli.exe")
            os.makedirs(os.path.dirname(new))
            open(new, "w").close()
            assert generate.resolve_sd_cli_alt() == new
            v1106 = os.path.join(td, "sdcli-1106", "bin", "sd-cli.exe")
            os.makedirs(os.path.dirname(v1106))
            open(v1106, "w").close()
            assert generate.resolve_sd_cli_alt() == v1106  # 1106 ใหม่กว่ามาก่อน
            custom = os.path.join(td, "custom.exe")
            os.environ["TEXT2IMAGE_SDCLI_ALT"] = custom
            assert generate.resolve_sd_cli_alt() == custom  # env ชนะแม้ไฟล์ไม่มี
        finally:
            generate.app_dir = old_app_dir
            if old_env is None:
                os.environ.pop("TEXT2IMAGE_SDCLI_ALT", None)
            else:
                os.environ["TEXT2IMAGE_SDCLI_ALT"] = old_env


def test_path_tag():
    import generate
    assert generate.path_tag(r"C:\x\sdcli-1106\bin\sd-cli.exe") == "1106"
    assert generate.path_tag(r"C:\x\sdcli-new\bin\sd-cli.exe") == "new"
    assert generate.path_tag(
        r"C:\Users\u\AppData\Local\Amuse\RuntimeStableDiffusionCpp\vulkan\sd-cli.exe") == "amuse"
    assert generate.path_tag(r"C:\GenJab\runtime\sd-cli.exe") == "bundled"
    assert generate.path_tag("") == "—"


def test_sd_cli_for_selection():
    import os
    import tempfile
    import generate
    with tempfile.TemporaryDirectory() as td:
        main = os.path.join(td, "main.exe")
        alt = os.path.join(td, "alt.exe")
        open(main, "w").close()
        open(alt, "w").close()
        old, old_alt, old_def = generate.SD_CLI, generate.SD_CLI_ALT, generate.DEFAULT_ENGINE
        generate.SD_CLI, generate.SD_CLI_ALT, generate.DEFAULT_ENGINE = main, alt, "amuse"
        try:
            assert generate.sd_cli_for("amuse", "sd-turbo") == main
            assert generate.sd_cli_for("alt", "sd-turbo") == alt
            assert generate.sd_cli_for(None, "sd-turbo") == main  # default = amuse
            try:
                generate.sd_cli_for("cuda", "sd-turbo")
            except ValueError:
                pass
            else:
                raise AssertionError("bogus engine should raise ValueError")
            generate.SD_CLI_ALT = os.path.join(td, "missing.exe")
            try:
                generate.sd_cli_for("alt", "sd-turbo")
            except FileNotFoundError:
                pass
            else:
                raise AssertionError("missing alt should raise FileNotFoundError")
        finally:
            generate.SD_CLI, generate.SD_CLI_ALT = old, old_alt
            generate.DEFAULT_ENGINE = old_def


def test_sd_cli_for_preset_guard():
    import os
    import generate
    base = generate.app_dir()
    old_bin = os.path.join(base, "sdcli-new", "bin", "sd-cli.exe")
    new_bin = os.path.join(base, "sdcli-1106", "bin", "sd-cli.exe")
    if not os.path.isfile(old_bin) or not os.path.isfile(new_bin):
        return  # CI ไม่มีบิลด์สำรอง — ข้าม
    old_alt = generate.SD_CLI_ALT
    try:
        generate.SD_CLI_ALT = old_bin  # บิลด์ 9/11/2026 ไม่มี minimax-h3-image
        try:
            generate.sd_cli_for("alt", "minimax-h3-image")
        except RuntimeError as e:
            assert "minimax-h3-image" in str(e)
        else:
            raise AssertionError("old alt + minimax-h3-image should raise RuntimeError")
        assert generate.sd_cli_for("alt", "sd-turbo") == old_bin  # โมเดลอื่นใช้ได้
        generate.SD_CLI_ALT = new_bin  # บิลด์ 15/11/2026 มี preset แล้ว
        assert generate.sd_cli_for("alt", "minimax-h3-image") == new_bin
    finally:
        generate.SD_CLI_ALT = old_alt


def test_sd_cli_for_rocm():
    import os
    import generate
    old_rocm = generate.SD_CLI_ROCM
    try:
        generate.SD_CLI_ROCM = os.path.join("nowhere", "sd-cli.exe")
        try:
            generate.sd_cli_for("rocm", "sd-turbo")
        except FileNotFoundError as e:
            assert "TEXT2IMAGE_SDCLI_ROCM" in str(e)
        else:
            raise AssertionError("missing rocm should raise FileNotFoundError")
        # ถ้าเครื่องนี้มีไบนารี ROCm จริง ต้องเลือกถูก + โผล่ในเมนู
        if old_rocm and os.path.isfile(old_rocm):
            generate.SD_CLI_ROCM = old_rocm
            assert generate.sd_cli_for("rocm", "sd-turbo") == old_rocm
            assert "rocm" in generate.available_engines()
            assert generate.rocm_engine_tag() == generate.path_tag(old_rocm)
    finally:
        generate.SD_CLI_ROCM = old_rocm


def test_face_engine_fallback():
    """Amuse 4.0 ไม่มี --ip-adapter → face_engine ต้องสลับไป alt/rocm ที่มี; ไม่มีเลย raise."""
    import os
    import tempfile
    import generate
    old = (generate.SD_CLI, generate.SD_CLI_ALT, generate.SD_CLI_ROCM, generate.DEFAULT_ENGINE)
    old_cache = dict(generate._ENGINE_HELP_CACHE)
    with tempfile.TemporaryDirectory() as td:
        def fake(name, has_ip):
            p = os.path.join(td, name, "sd-cli.exe")
            os.makedirs(os.path.dirname(p))
            open(p, "wb").close()
            generate._ENGINE_HELP_CACHE[p] = ("--ip-adapter <string>" if has_ip else "--control-net") + " usage"
            return p
        amuse, alt, rocm = fake("amuse", False), fake("alt", True), fake("rocm", True)
        try:
            generate.SD_CLI, generate.SD_CLI_ALT, generate.SD_CLI_ROCM = amuse, alt, rocm
            generate.DEFAULT_ENGINE = "amuse"
            assert generate.face_engine("amuse", "sdxl-turbo") == ("alt", alt)
            assert generate.face_engine(None, "sdxl-turbo") == ("alt", alt)  # ว่าง = default
            assert generate.face_engine("rocm", "sdxl-turbo") == ("rocm", rocm)  # ตัวที่เลือกมีอยู่แล้ว
            generate.SD_CLI_ALT = ""  # ไม่มี alt → ไป rocm
            assert generate.face_engine("amuse", "sdxl-turbo") == ("rocm", rocm)
            generate.SD_CLI_ROCM = ""  # ไม่เหลือใคร
            try:
                generate.face_engine("amuse", "sdxl-turbo")
            except RuntimeError as e:
                assert "--ip-adapter" in str(e) and "sdcli-1106" in str(e)
            else:
                raise AssertionError("no engine with --ip-adapter should raise RuntimeError")
            generate._ENGINE_HELP_CACHE[amuse] = ""  # --help รันไม่ได้ → ถือว่ามี (ไม่ขวาง)
            assert generate.face_engine("amuse", "sdxl-turbo") == ("amuse", amuse)
        finally:
            generate.SD_CLI, generate.SD_CLI_ALT, generate.SD_CLI_ROCM, generate.DEFAULT_ENGINE = old
            generate._ENGINE_HELP_CACHE.clear()
            generate._ENGINE_HELP_CACHE.update(old_cache)


def test_preview_args_and_run_callback():
    """--preview proj ใส่เฉพาะ engine ที่รู้จัก + _run เรียก callback ตอนไฟล์ preview เปลี่ยน."""
    import os
    import sys
    import tempfile
    import generate
    from PIL import Image
    old_cache = dict(generate._ENGINE_HELP_CACHE)
    with tempfile.TemporaryDirectory() as td:
        try:
            generate._ENGINE_HELP_CACHE["new.exe"] = "--preview  preview method [none, proj, tae, vae]"
            generate._ENGINE_HELP_CACHE["old.exe"] = "--steps only"
            assert generate.preview_args("new.exe", td, None) == ([], None)  # ไม่ขอ = ไม่ใส่
            assert generate.preview_args("old.exe", td, print) == ([], None)  # engine ไม่มี
            args, watch = generate.preview_args("new.exe", td, print)
            assert args[:2] == ["--preview", "proj"] and watch[0] == args[3]
            assert os.path.dirname(watch[0]) == td
        finally:
            generate._ENGINE_HELP_CACHE.clear()
            generate._ENGINE_HELP_CACHE.update(old_cache)
        # โปรเซสปลอมเขียน preview 2 รอบ (สีต่างกัน) แล้วจบ
        pv = os.path.join(td, "preview.png")
        script_path = os.path.join(td, "fake_cli.py")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write("\n".join([
                "import os, sys, time",
                "from PIL import Image",
                "pv = sys.argv[1]",
                "for c in (10, 200):",
                "    Image.new('RGB', (8, 8), (c, 0, 0)).save(pv + '.tmp', 'PNG')",
                "    os.replace(pv + '.tmp', pv)",
                "    time.sleep(0.4)",
                ""]))
        script = [sys.executable, script_path, pv]
        got = []
        p = generate._run(script, None, (pv, lambda im: got.append(im.getpixel((0, 0))[0])))
        assert p.returncode == 0, p.stderr
        assert got and got[-1] == 200, got  # เห็นรูปล่าสุด
        boom = []

        def bad_cb(im):
            boom.append(1)
            raise ValueError("callback พัง")
        p = generate._run(script, None, (pv, bad_cb))
        assert p.returncode == 0 and boom  # callback พังไม่ล้มงานเจน


def test_sd_server_helpers():
    """แยกแท็ก LoRA แบบ sd-cli (เว้นวรรคเดิม) + ชื่อไฟล์ LoRA + ไม่มี sd-server ถอยไป sd-cli."""
    import os
    import tempfile
    import generate
    import sd_server
    assert sd_server.split_lora("a girl <lora:anima-x:0.8>") == ("a girl ", [("anima-x", 0.8)])
    assert sd_server.split_lora("no tag") == ("no tag", [])
    assert sd_server.split_lora("<lora:a:b:1.5> x <lora:c:0.5>") == (" x ", [("a:b", 1.5), ("c", 0.5)])
    with tempfile.TemporaryDirectory() as td:
        open(os.path.join(td, "anima-x.safetensors"), "w").close()
        assert sd_server.lora_field([("anima-x", 0.8)], td) == [{"path": "anima-x.safetensors", "multiplier": 0.8}]
        assert sd_server.lora_field([("missing", 1.0)], td) == [{"path": "missing", "multiplier": 1.0}]
        cli = os.path.join(td, "sd-cli.exe")
        open(cli, "w").close()
        assert sd_server.server_exe_for(cli) == ""  # ไม่มี sd-server ข้าง ๆ
        assert generate._server_gen(cli, "sd-turbo", {"m": "x"}, "p", [], "", 64, 64, 1, 1.0, 1) is None
        open(os.path.join(td, "sd-server.exe"), "w").close()
        assert sd_server.server_exe_for(cli) == os.path.join(td, "sd-server.exe")
        # โมเดลที่ต้องใช้ argv พิเศษไม่ผ่าน server
        assert generate._server_gen(cli, "minimax-h3-image", {"m": "x"}, "p", [], "", 64, 64, 1, 1.0, 1) is None
        assert generate._server_gen(cli, "flux2-dev", {"m": "x"}, "p", [], "", 64, 64, 1, 1.0, 1) is None
    sd_server.SERVER.stop()  # เรียกตอนไม่มี server ต้องไม่พัง
    assert not sd_server.SERVER.alive()


def test_controlnet_args():
    """ControlNet: หาไฟล์จาก models/controlnet + Amuse, ตรวจค่า, ย่อรูปควบคุม, canny ใช้ sd-cli หรือ PIL."""
    import os
    import tempfile
    import generate
    from PIL import Image
    old = (generate.CONTROLNET_DIR, generate.AMUSE_MODELS)
    old_cache = dict(generate._ENGINE_HELP_CACHE)
    with tempfile.TemporaryDirectory() as td:
        local = os.path.join(td, "local")
        amuse = os.path.join(td, "amuse")
        os.makedirs(local)
        os.makedirs(os.path.join(amuse, "controlnet"))
        generate.CONTROLNET_DIR, generate.AMUSE_MODELS = local, amuse
        try:
            assert generate.list_controlnets() == {}
            try:
                generate.resolve_controlnet()
            except FileNotFoundError as e:
                assert "controlnet-union-sdxl" in str(e)
            else:
                raise AssertionError("no controlnet should raise")
            net = os.path.join(amuse, "controlnet", "union-promax.safetensors")
            open(net, "w").close()
            open(os.path.join(amuse, "controlnet", "readme.txt"), "w").close()  # ไม่ใช่โมเดล
            assert generate.list_controlnets() == {"union-promax": net}
            assert generate.control_args("x.exe", "sdxl-turbo", None, 64, 64, td) == []
            ref = os.path.join(td, "ref.png")
            Image.new("RGB", (300, 200), (90, 90, 90)).save(ref)
            ctl = {"image": ref, "type": "canny", "strength": 0.8}
            generate._ENGINE_HELP_CACHE["new.exe"] = "--image-preprocess <string> --control-net"
            generate._ENGINE_HELP_CACHE["old.exe"] = "--control-net only"
            a = generate.control_args("new.exe", "sdxl-turbo", ctl, 512, 768, td)
            assert a[a.index("--control-net") + 1] == net
            assert a[a.index("--control-type") + 1] == "canny"
            assert a[a.index("--control-strength") + 1] == "0.8"
            assert a[a.index("--image-preprocess") + 1] == "target=control,canny=true"
            with Image.open(a[a.index("--control-image") + 1]) as im:
                assert im.size == (512, 768)  # ย่อ/ครอปเท่าขนาดเจน
            a = generate.control_args("old.exe", "sdxl-turbo", ctl, 64, 64, td)
            assert "--image-preprocess" not in a  # engine เก่าหาขอบด้วย PIL เอง
            a = generate.control_args("new.exe", "sdxl-base", dict(ctl, type="scribble"), 64, 64, td)
            assert "--image-preprocess" not in a and a[a.index("--control-type") + 1] == "scribble"
            for bad, err in [("sd-turbo", ValueError), ("anima-turbo", ValueError)]:
                try:
                    generate.control_args("new.exe", bad, ctl, 64, 64, td)
                except err:
                    pass
                else:
                    raise AssertionError(f"{bad} should be rejected")
            for kw in [{"type": "pose"}, {"strength": 0}, {"strength": "แรง"}, {"strength": 3}]:
                try:
                    generate.control_args("new.exe", "sdxl-turbo", dict(ctl, **kw), 64, 64, td)
                except ValueError:
                    pass
                else:
                    raise AssertionError(f"{kw} should raise ValueError")
            try:
                generate.control_args("new.exe", "sdxl-turbo", dict(ctl, image="nope.png"), 64, 64, td)
            except FileNotFoundError:
                pass
            else:
                raise AssertionError("missing control image should raise")
        finally:
            generate.CONTROLNET_DIR, generate.AMUSE_MODELS = old
            generate._ENGINE_HELP_CACHE.clear()
            generate._ENGINE_HELP_CACHE.update(old_cache)


def test_local_llm_helpers():
    """แปลในเครื่อง: ไม่มีอักษรไทยไม่เปิด server, ล้างคำตอบ, ไม่มีโมเดลบอกวิธี, generate ปิด LLM ก่อนเจน."""
    import os
    import local_llm
    import generate
    assert local_llm.translate("a red cat") == "a red cat"  # ไม่ใช่ไทย คืนเดิมไม่เปิด server
    assert not local_llm.LLM.alive()
    assert local_llm.clean('"English prompt: a cat"') == "a cat"
    assert local_llm.clean("<think>hmm</think>\n a dog ") == "a dog"
    old = os.environ.get("GENJAB_LLM_MODEL")
    os.environ["GENJAB_LLM_MODEL"] = os.path.join("nowhere", "x.gguf")
    try:
        assert local_llm.llm_model() == "" and not local_llm.available()
        local_llm.LLM.cache.pop("แมว", None)
        try:
            local_llm.translate("แมว")
        except FileNotFoundError as e:
            assert "Qwen3-4B" in str(e)
        else:
            raise AssertionError("missing model should raise")
    finally:
        if old is None:
            os.environ.pop("GENJAB_LLM_MODEL", None)
        else:
            os.environ["GENJAB_LLM_MODEL"] = old
    calls = []
    real = local_llm.LLM.stop
    local_llm.LLM.stop = lambda: calls.append(1)
    try:
        generate._stop_llm()
    finally:
        local_llm.LLM.stop = real
    assert calls == [1]


def test_audio_gen_helpers():
    """เพลงประกอบคลิป: จับชื่อ option, WAV float, ชื่อไฟล์ไม่ทับ, argv ffmpeg, ไม่มีโมเดลบอกที่โหลด."""
    import os
    import struct
    import tempfile
    import audio_gen
    declared = {"seconds": ("", "", "", ""), "steps": ("8", "", "", ""), "cfg_scale": ("1", "", "", "")}
    assert audio_gen.pick_options(declared, {"duration": "12", "steps": 8, "seed": 5, "cfg": None}) == \
        {"seconds": "12", "steps": "8"}  # seed ไม่ได้ประกาศ = ไม่ส่ง, cfg None = ไม่ส่ง
    # ไม่รู้ว่าโมเดลประกาศอะไร → ใช้ชื่อแรก (ชื่อจริงของ stable_audio ใน audio.cpp 0.9.6)
    assert audio_gen.pick_options({}, {"duration": "3", "seed": 1}) == {"duration_sec": "3", "seed": "1"}
    sa3 = {k: ("", "", "", "") for k in ("duration_sec", "num_inference_steps", "guidance_scale",
                                         "seed", "negative_prompt")}
    assert audio_gen.pick_options(sa3, {"duration": "8", "steps": 8, "seed": 42, "cfg": 1.0,
                                        "negative": "vocals"}) == {
        "duration_sec": "8", "num_inference_steps": "8", "seed": "42",
        "guidance_scale": "1.0", "negative_prompt": "vocals"}
    with tempfile.TemporaryDirectory() as td:
        wav = os.path.join(td, "x.wav")
        raw = struct.pack("<4f", 0.0, 0.5, -0.5, 0.25)
        audio_gen.write_wav_float(wav, raw, 44100, 2)
        b = open(wav, "rb").read()
        assert b[:4] == b"RIFF" and b[8:12] == b"WAVE"
        assert struct.unpack("<I", b[4:8])[0] == len(b) - 8  # ขนาด RIFF ถูก
        assert struct.unpack("<HHI", b[20:28]) == (3, 2, 44100)  # float, stereo, 44.1k
        assert b.endswith(raw)
        v = os.path.join(td, "vid001.webm")
        open(v, "w").close()
        assert audio_gen.music_out_path(v) == os.path.join(td, "vid001_music.webm")
        open(os.path.join(td, "vid001_music.webm"), "w").close()
        assert audio_gen.music_out_path(v) == os.path.join(td, "vid001_music_2.webm")
        a = audio_gen.mux_args("ff.exe", v, wav, os.path.join(td, "o.webm"), 4.0)
        assert a[a.index("-c:v") + 1] == "copy" and a[a.index("-c:a") + 1] == "libopus"
        assert a[a.index("-t") + 1] == "4.000" and "afade=t=out:st=2.50" in a[a.index("-af") + 1]
        a = audio_gen.mux_args("ff.exe", v, wav, os.path.join(td, "o.mp4"), 1.0)
        assert a[a.index("-c:a") + 1] == "aac" and "afade=t=out:st=0.00" in a[a.index("-af") + 1]
        old = os.environ.get("GENJAB_AUDIO_MODEL")
        os.environ["GENJAB_AUDIO_MODEL"] = os.path.join(td, "nope.gguf")
        try:
            assert audio_gen.music_model() == ""
            try:
                audio_gen.generate_music("calm piano", 5, wav)
            except FileNotFoundError as e:
                assert "stable-audio-3-small-music" in str(e)
            else:
                raise AssertionError("missing model should raise")
        finally:
            if old is None:
                os.environ.pop("GENJAB_AUDIO_MODEL", None)
            else:
                os.environ["GENJAB_AUDIO_MODEL"] = old
    for bad in [("", 5), ("x", 0), ("x", 500)]:
        try:
            audio_gen.generate_music(bad[0], bad[1], "x.wav", model_path="x.gguf")
        except ValueError:
            pass
        else:
            raise AssertionError(f"{bad} should raise ValueError")


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



def test_model_files_fibo2_turbo():
    import os
    import tempfile
    import generate
    from generate import model_files
    with tempfile.TemporaryDirectory() as td:
        diff = os.path.join(td, "Diffusion")
        te = os.path.join(td, "TextEncoder")
        ae = os.path.join(td, "AutoEncoder", "Flux2")
        os.makedirs(diff)
        os.makedirs(te)
        os.makedirs(ae)
        want = {"diffusion": os.path.join(diff, "fibo2_edit_turbo-Q8_0.gguf"),
                "llm": os.path.join(te, "Qwen3VL-4B-Instruct-Q8_0.gguf"),
                "llm_vision": os.path.join(te, "mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf"),
                "vae": os.path.join(ae, "diffusion_pytorch_model.safetensors")}
        for f in want.values():
            open(f, "w").close()
        old = generate.AMUSE_MODELS
        generate.AMUSE_MODELS = td
        try:
            assert model_files("fibo2-turbo") == want
            os.remove(want["llm"])
            try:
                model_files("fibo2-turbo")
            except FileNotFoundError:
                pass
            else:
                raise AssertionError("llm missing should raise FileNotFoundError")
        finally:
            generate.AMUSE_MODELS = old


def test_txt2img_fibo2_argv():
    import os
    import subprocess
    import tempfile
    import types
    import generate
    from generate import txt2img
    from PIL import Image
    calls = []
    real_run = subprocess.run

    def fake_run(cmd, **kw):
        calls.append(cmd)
        out = cmd[cmd.index("-o") + 1]
        Image.new("RGB", (8, 8)).save(out)
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    with tempfile.TemporaryDirectory() as td:
        diff = os.path.join(td, "Diffusion")
        te = os.path.join(td, "TextEncoder")
        ae = os.path.join(td, "AutoEncoder", "Flux2")
        os.makedirs(diff)
        os.makedirs(te)
        os.makedirs(ae)
        for f in ("fibo2_edit_turbo-Q8_0.gguf",):
            open(os.path.join(diff, f), "w").close()
        for f in ("Qwen3VL-4B-Instruct-Q8_0.gguf", "mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf"):
            open(os.path.join(te, f), "w").close()
        open(os.path.join(ae, "diffusion_pytorch_model.safetensors"), "w").close()
        fake_cli = os.path.join(td, "sd-cli.exe")
        open(fake_cli, "w").close()
        old_cli, old_amuse = generate.SD_CLI, generate.AMUSE_MODELS
        generate.SD_CLI, generate.AMUSE_MODELS = fake_cli, td
        subprocess.run = fake_run
        try:
            txt2img("a cat astronaut", steps=1, size=256, seed=7, model="fibo2-turbo")
        finally:
            subprocess.run = real_run
            generate.SD_CLI, generate.AMUSE_MODELS = old_cli, old_amuse
    cmd = calls[0]
    assert cmd[cmd.index("--diffusion-model") + 1].endswith("fibo2_edit_turbo-Q8_0.gguf"), cmd
    assert cmd[cmd.index("--llm") + 1].endswith("Qwen3VL-4B-Instruct-Q8_0.gguf"), cmd
    assert cmd[cmd.index("--llm_vision") + 1].endswith("mmproj-Qwen3VL-4B-Instruct-Q8_0.gguf"), cmd
    assert cmd[cmd.index("--vae") + 1].endswith("diffusion_pytorch_model.safetensors"), cmd


def test_model_files_moss_sft():
    import os
    import tempfile
    import generate
    from generate import model_files
    with tempfile.TemporaryDirectory() as td:
        diff = os.path.join(td, "Diffusion")
        te = os.path.join(td, "TextEncoder")
        ae = os.path.join(td, "AutoEncoder", "Flux2")
        tok = os.path.join(td, "Tokenizer", "MossImage")
        os.makedirs(diff)
        os.makedirs(te)
        os.makedirs(ae)
        os.makedirs(tok)
        want = {"diffusion": os.path.join(diff, "MOSS-Image-SFT-Q8_0.gguf"),
                "llm": os.path.join(te, "Qwen3.5-9B-Q8_0.gguf"),
                "vae": os.path.join(ae, "diffusion_pytorch_model.safetensors"),
                "tokenizer": os.path.join(tok, "tokenizer.json")}
        for f in want.values():
            open(f, "w").close()
        old = generate.AMUSE_MODELS
        generate.AMUSE_MODELS = td
        try:
            assert model_files("moss-sft") == want
            os.remove(want["llm"])
            try:
                model_files("moss-sft")
            except FileNotFoundError:
                pass
            else:
                raise AssertionError("llm missing should raise FileNotFoundError")
        finally:
            generate.AMUSE_MODELS = old


def test_txt2img_moss_sft_argv():
    import os
    import subprocess
    import tempfile
    import types
    import generate
    from generate import txt2img
    from PIL import Image
    calls = []
    real_run = subprocess.run

    def fake_run(cmd, **kw):
        calls.append(cmd)
        out = cmd[cmd.index("-o") + 1]
        Image.new("RGB", (8, 8)).save(out)
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    with tempfile.TemporaryDirectory() as td:
        diff = os.path.join(td, "Diffusion")
        te = os.path.join(td, "TextEncoder")
        ae = os.path.join(td, "AutoEncoder", "Flux2")
        tok = os.path.join(td, "Tokenizer", "MossImage")
        os.makedirs(diff)
        os.makedirs(te)
        os.makedirs(ae)
        os.makedirs(tok)
        for f in ("MOSS-Image-SFT-Q8_0.gguf",):
            open(os.path.join(diff, f), "w").close()
        for f in ("Qwen3.5-9B-Q8_0.gguf",):
            open(os.path.join(te, f), "w").close()
        open(os.path.join(ae, "diffusion_pytorch_model.safetensors"), "w").close()
        open(os.path.join(tok, "tokenizer.json"), "w").close()
        fake_cli = os.path.join(td, "sd-cli.exe")
        open(fake_cli, "w").close()
        old_cli, old_amuse = generate.SD_CLI, generate.AMUSE_MODELS
        generate.SD_CLI, generate.AMUSE_MODELS = fake_cli, td
        subprocess.run = fake_run
        try:
            txt2img("a cat astronaut", steps=1, size=256, seed=7, model="moss-sft")
        finally:
            subprocess.run = real_run
            generate.SD_CLI, generate.AMUSE_MODELS = old_cli, old_amuse
    cmd = calls[0]
    assert cmd[cmd.index("--diffusion-model") + 1].endswith("MOSS-Image-SFT-Q8_0.gguf"), cmd
    assert cmd[cmd.index("--llm") + 1].endswith("Qwen3.5-9B-Q8_0.gguf"), cmd
    assert cmd[cmd.index("--vae") + 1].endswith("diffusion_pytorch_model.safetensors"), cmd
    assert cmd[cmd.index("--tokenizer") + 1].endswith("tokenizer.json"), cmd


def test_model_files_anima_turbo_v11():
    import os
    import tempfile
    import generate
    from generate import model_files
    with tempfile.TemporaryDirectory() as td:
        amuse_diff = os.path.join(td, "Amuse", "Diffusion")
        local = os.path.join(td, "models")
        te = os.path.join(td, "Amuse", "TextEncoder")
        ae = os.path.join(td, "Amuse", "AutoEncoder", "QwenImage")
        os.makedirs(amuse_diff)
        os.makedirs(local)
        os.makedirs(te)
        os.makedirs(ae)
        open(os.path.join(te, "Qwen3-0.6B-Q8_0.gguf"), "w").close()
        open(os.path.join(ae, "diffusion_pytorch_model.safetensors"), "w").close()
        v11 = os.path.join(amuse_diff, "anima-turbo-v1.1.safetensors")
        v10 = os.path.join(amuse_diff, "anima-turbo-v1.0.safetensors")
        open(v10, "w").close()
        old_amuse, old_local = generate.AMUSE_MODELS, generate.LOCAL_MODELS
        generate.AMUSE_MODELS = os.path.join(td, "Amuse")
        generate.LOCAL_MODELS = local
        try:
            # มีแค่ v1.0 → ใช้ v1.0 (กันเครื่องที่ Amuse ยังไม่อัปเดต)
            assert model_files("anima-turbo")["m"] == v10
            # มี v1.1 เพิ่ม → เลือก v1.1
            open(v11, "w").close()
            assert model_files("anima-turbo")["m"] == v11
            # ไฟล์ที่โหลดเองใน models/ ก็ใช้ได้
            os.remove(v11)
            os.remove(v10)
            local_v11 = os.path.join(local, "anima-turbo-v1.1.safetensors")
            open(local_v11, "w").close()
            assert model_files("anima-turbo")["m"] == local_v11
        finally:
            generate.AMUSE_MODELS, generate.LOCAL_MODELS = old_amuse, old_local


def test_model_files_iris_turbo():
    import os
    import tempfile
    import generate
    from generate import model_files
    with tempfile.TemporaryDirectory() as td:
        amuse_turbo = os.path.join(td, "Amuse", "Diffusion", "iris-3b", "turbo")
        local = os.path.join(td, "models")
        te = os.path.join(td, "Amuse", "TextEncoder")
        os.makedirs(amuse_turbo)
        os.makedirs(local)
        os.makedirs(te)
        open(os.path.join(te, "Qwen3VL-4B-Instruct-Q8_0.gguf"), "w").close()
        amuse_file = os.path.join(amuse_turbo, "model.safetensors")
        local_file = os.path.join(local, "iris-3b-turbo.safetensors")
        open(local_file, "w").close()
        old_amuse, old_local = generate.AMUSE_MODELS, generate.LOCAL_MODELS
        generate.AMUSE_MODELS = os.path.join(td, "Amuse")
        generate.LOCAL_MODELS = local
        try:
            # ของ Amuse มาก่อน
            open(amuse_file, "w").close()
            assert model_files("iris-turbo")["diffusion"] == amuse_file
            # ไม่มีของ Amuse → ใช้ไฟล์ใน models/
            os.remove(amuse_file)
            assert model_files("iris-turbo")["diffusion"] == local_file
            # env override ชนะทั้งหมด
            over = os.path.join(td, "custom-iris.gguf")
            open(over, "w").close()
            old_env = os.environ.get("TEXT2IMAGE_IRIS_TURBO")
            os.environ["TEXT2IMAGE_IRIS_TURBO"] = over
            try:
                assert model_files("iris-turbo")["diffusion"] == over
            finally:
                if old_env is None:
                    os.environ.pop("TEXT2IMAGE_IRIS_TURBO", None)
                else:
                    os.environ["TEXT2IMAGE_IRIS_TURBO"] = old_env
            # หายหมด → raise
            os.remove(local_file)
            try:
                model_files("iris-turbo")
            except FileNotFoundError:
                pass
            else:
                raise AssertionError("diffusion missing should raise FileNotFoundError")
        finally:
            generate.AMUSE_MODELS, generate.LOCAL_MODELS = old_amuse, old_local


def test_model_files_flux2_dev():
    import os
    import tempfile
    import generate
    from generate import model_files
    with tempfile.TemporaryDirectory() as td:
        local = os.path.join(td, "models")
        os.makedirs(local)
        want = {"diffusion": os.path.join(local, "flux2-dev-Q4_K_M.gguf"),
                "llm": os.path.join(local, "Mistral-Small-3.2-24B-Instruct-2506-Q4_K_M.gguf"),
                "vae": os.path.join(local, "flux2-vae.safetensors")}
        for f in want.values():
            open(f, "w").close()
        old_local = generate.LOCAL_MODELS
        generate.LOCAL_MODELS = local
        try:
            from generate import model_files as mf
            assert mf("flux2-dev") == want
            os.remove(want["vae"])
            try:
                mf("flux2-dev")
            except FileNotFoundError:
                pass
            else:
                raise AssertionError("vae missing should raise FileNotFoundError")
            open(want["vae"], "w").close()
            old_env = os.environ.get("TEXT2IMAGE_FLUX2_DEV")
            os.environ["TEXT2IMAGE_FLUX2_DEV"] = want["diffusion"]
            try:
                assert mf("flux2-dev")["diffusion"] == want["diffusion"]
            finally:
                if old_env is None:
                    os.environ.pop("TEXT2IMAGE_FLUX2_DEV", None)
                else:
                    os.environ["TEXT2IMAGE_FLUX2_DEV"] = old_env
        finally:
            generate.LOCAL_MODELS = old_local


def test_txt2img_iris_turbo_argv():
    import os
    import subprocess
    import tempfile
    import types
    import generate
    from generate import txt2img
    from PIL import Image
    calls = []
    real_run = subprocess.run

    def fake_run(cmd, **kw):
        calls.append(cmd)
        out = cmd[cmd.index("-o") + 1]
        Image.new("RGB", (8, 8)).save(out)
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    with tempfile.TemporaryDirectory() as td:
        local = os.path.join(td, "models")
        te = os.path.join(td, "Amuse", "TextEncoder")
        os.makedirs(local)
        os.makedirs(te)
        open(os.path.join(local, "iris-3b-turbo.safetensors"), "w").close()
        open(os.path.join(te, "Qwen3VL-4B-Instruct-Q8_0.gguf"), "w").close()
        fake_cli = os.path.join(td, "sd-cli.exe")
        open(fake_cli, "w").close()
        old_cli, old_local, old_amuse = generate.SD_CLI, generate.LOCAL_MODELS, generate.AMUSE_MODELS
        generate.SD_CLI, generate.LOCAL_MODELS = fake_cli, local
        generate.AMUSE_MODELS = os.path.join(td, "Amuse")
        subprocess.run = fake_run
        try:
            txt2img("a cat astronaut", steps=1, size=256, seed=7, model="iris-turbo")
        finally:
            subprocess.run = real_run
            generate.SD_CLI, generate.LOCAL_MODELS, generate.AMUSE_MODELS = old_cli, old_local, old_amuse
    cmd = calls[0]
    assert cmd[cmd.index("--diffusion-model") + 1].endswith("iris-3b-turbo.safetensors"), cmd
    assert cmd[cmd.index("--llm") + 1].endswith("Qwen3VL-4B-Instruct-Q8_0.gguf"), cmd
    assert "--offload-to-cpu" not in cmd, cmd


def test_txt2img_flux2_dev_argv():
    import os
    import subprocess
    import tempfile
    import types
    import generate
    from generate import txt2img
    from PIL import Image
    calls = []
    real_run = subprocess.run

    def fake_run(cmd, **kw):
        calls.append(cmd)
        out = cmd[cmd.index("-o") + 1]
        Image.new("RGB", (8, 8)).save(out)
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    with tempfile.TemporaryDirectory() as td:
        local = os.path.join(td, "models")
        os.makedirs(local)
        for fn in ("flux2-dev-Q4_K_M.gguf", "Mistral-Small-3.2-24B-Instruct-2506-Q4_K_M.gguf",
                   "flux2-vae.safetensors"):
            open(os.path.join(local, fn), "w").close()
        fake_cli = os.path.join(td, "sd-cli.exe")
        open(fake_cli, "w").close()
        old_cli, old_local = generate.SD_CLI, generate.LOCAL_MODELS
        generate.SD_CLI, generate.LOCAL_MODELS = fake_cli, local
        subprocess.run = fake_run
        try:
            txt2img("a cat astronaut", steps=1, size=256, seed=7, model="flux2-dev")
        finally:
            subprocess.run = real_run
            generate.SD_CLI, generate.LOCAL_MODELS = old_cli, old_local
    cmd = calls[0]
    assert cmd[cmd.index("--diffusion-model") + 1].endswith("flux2-dev-Q4_K_M.gguf"), cmd
    assert cmd[cmd.index("--llm") + 1].endswith("Mistral-Small-3.2-24B-Instruct-2506-Q4_K_M.gguf"), cmd
    assert cmd[cmd.index("--vae") + 1].endswith("flux2-vae.safetensors"), cmd
    assert "--offload-to-cpu" in cmd, cmd


def test_model_files_minimax_h3_image():
    import os
    import tempfile
    import generate
    from generate import model_files
    with tempfile.TemporaryDirectory() as td:
        diff = os.path.join(td, "Diffusion")
        te = os.path.join(td, "TextEncoder")
        ae = os.path.join(td, "AutoEncoder")
        os.makedirs(diff)
        os.makedirs(te)
        os.makedirs(ae)
        want = {"diffusion": os.path.join(diff, "minimax_h3_image_pruned_int8_convrot.safetensors"),
                "llm": os.path.join(te, "qwen3vl_32b_minimax_h3-Q4_K_M.gguf"),
                "vae": os.path.join(ae, "minimax_h3_image_vae_fp16.safetensors")}
        for f in want.values():
            open(f, "w").close()
        old = generate.AMUSE_MODELS
        generate.AMUSE_MODELS = td
        try:
            assert model_files("minimax-h3-image") == want
            os.remove(want["vae"])
            try:
                model_files("minimax-h3-image")
            except FileNotFoundError:
                pass
            else:
                raise AssertionError("vae missing should raise FileNotFoundError")
        finally:
            generate.AMUSE_MODELS = old


def test_txt2img_minimax_h3_image_argv():
    import os
    import subprocess
    import tempfile
    import types
    import generate
    from generate import txt2img
    from PIL import Image
    calls = []
    real_run = subprocess.run

    def fake_run(cmd, **kw):
        calls.append(cmd)
        out = cmd[cmd.index("-o") + 1]
        Image.new("RGB", (8, 8)).save(out)
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    with tempfile.TemporaryDirectory() as td:
        diff = os.path.join(td, "Diffusion")
        te = os.path.join(td, "TextEncoder")
        ae = os.path.join(td, "AutoEncoder")
        os.makedirs(diff)
        os.makedirs(te)
        os.makedirs(ae)
        for f in ("minimax_h3_image_pruned_int8_convrot.safetensors",):
            open(os.path.join(diff, f), "w").close()
        for f in ("qwen3vl_32b_minimax_h3-Q4_K_M.gguf",):
            open(os.path.join(te, f), "w").close()
        open(os.path.join(ae, "minimax_h3_image_vae_fp16.safetensors"), "w").close()
        fake_cli = os.path.join(td, "sd-cli.exe")
        open(fake_cli, "w").close()
        old_cli, old_amuse = generate.SD_CLI, generate.AMUSE_MODELS
        generate.SD_CLI, generate.AMUSE_MODELS = fake_cli, td
        subprocess.run = fake_run
        try:
            txt2img("a cat astronaut", steps=1, size=256, seed=7, model="minimax-h3-image")
        finally:
            subprocess.run = real_run
            generate.SD_CLI, generate.AMUSE_MODELS = old_cli, old_amuse
    cmd = calls[0]
    assert cmd[cmd.index("--diffusion-model") + 1].endswith("minimax_h3_image_pruned_int8_convrot.safetensors"), cmd
    assert cmd[cmd.index("--llm") + 1].endswith("qwen3vl_32b_minimax_h3-Q4_K_M.gguf"), cmd
    assert cmd[cmd.index("--vae") + 1].endswith("minimax_h3_image_vae_fp16.safetensors"), cmd
    assert "--offload-to-cpu" in cmd, cmd
    assert cmd[cmd.index("--backend") + 1] == "cpu", cmd
    assert cmd[cmd.index("--sampling-method") + 1] == "euler", cmd
    assert cmd[cmd.index("--sigmas") + 1] == "minimax-h3-image", cmd
    assert cmd[cmd.index("--rng") + 1] == "cpu", cmd
    assert cmd[cmd.index("--flash-attn") + 1] == "off,diffusion=on", cmd
    assert "--vae-tiling" in cmd, cmd


def test_model_files_zimage_turbo():
    import os
    import tempfile
    import generate
    with tempfile.TemporaryDirectory() as td:
        local = os.path.join(td, "models")
        ae = os.path.join(td, "Amuse", "AutoEncoder", "Flux1")
        os.makedirs(local)
        os.makedirs(ae)
        for fn in ("z_image_turbo-Q4_K.gguf", "Qwen3-4B-Instruct-2507-Q4_K_M.gguf"):
            open(os.path.join(local, fn), "w").close()
        open(os.path.join(ae, "diffusion_pytorch_model.safetensors"), "w").close()
        want = {"diffusion": os.path.join(local, "z_image_turbo-Q4_K.gguf"),
                "llm": os.path.join(local, "Qwen3-4B-Instruct-2507-Q4_K_M.gguf"),
                "vae": os.path.join(ae, "diffusion_pytorch_model.safetensors")}
        old_local, old_amuse = generate.LOCAL_MODELS, generate.AMUSE_MODELS
        generate.LOCAL_MODELS = local
        generate.AMUSE_MODELS = os.path.join(td, "Amuse")
        try:
            assert model_files("zimage-turbo") == want
            os.remove(want["vae"])
            try:
                model_files("zimage-turbo")
            except FileNotFoundError:
                pass
            else:
                raise AssertionError("vae missing should raise FileNotFoundError")
            open(os.path.join(ae, "diffusion_pytorch_model.safetensors"), "w").close()
            old_env = os.environ.get("TEXT2IMAGE_ZIMAGE_TURBO")
            os.environ["TEXT2IMAGE_ZIMAGE_TURBO"] = os.path.join(local, "z_image_turbo-Q4_K.gguf")
            try:
                assert model_files("zimage-turbo")["diffusion"] == os.path.join(local, "z_image_turbo-Q4_K.gguf")
            finally:
                if old_env is None:
                    os.environ.pop("TEXT2IMAGE_ZIMAGE_TURBO", None)
                else:
                    os.environ["TEXT2IMAGE_ZIMAGE_TURBO"] = old_env
        finally:
            generate.LOCAL_MODELS, generate.AMUSE_MODELS = old_local, old_amuse


def test_txt2img_zimage_argv():
    import os
    import subprocess
    import tempfile
    import types
    import generate
    from generate import txt2img
    from PIL import Image
    calls = []
    real_run = subprocess.run

    def fake_run(cmd, **kw):
        calls.append(cmd)
        out = cmd[cmd.index("-o") + 1]
        Image.new("RGB", (8, 8)).save(out)
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    with tempfile.TemporaryDirectory() as td:
        local = os.path.join(td, "models")
        ae = os.path.join(td, "Amuse", "AutoEncoder", "Flux1")
        os.makedirs(local)
        os.makedirs(ae)
        for f in ("z_image_turbo-Q4_K.gguf", "Qwen3-4B-Instruct-2507-Q4_K_M.gguf"):
            open(os.path.join(local, f), "w").close()
        open(os.path.join(ae, "diffusion_pytorch_model.safetensors"), "w").close()
        fake_cli = os.path.join(td, "sd-cli.exe")
        open(fake_cli, "w").close()
        old_cli, old_local, old_amuse = generate.SD_CLI, generate.LOCAL_MODELS, generate.AMUSE_MODELS
        generate.SD_CLI, generate.LOCAL_MODELS = fake_cli, local
        generate.AMUSE_MODELS = os.path.join(td, "Amuse")
        subprocess.run = fake_run
        try:
            txt2img("a cat astronaut", steps=1, size=256, seed=7, model="zimage-turbo")
        finally:
            subprocess.run = real_run
            generate.SD_CLI, generate.LOCAL_MODELS = old_cli, old_local
            generate.AMUSE_MODELS = old_amuse
    cmd = calls[0]
    assert cmd[cmd.index("--diffusion-model") + 1].endswith("z_image_turbo-Q4_K.gguf"), cmd
    assert cmd[cmd.index("--llm") + 1].endswith("Qwen3-4B-Instruct-2507-Q4_K_M.gguf"), cmd
    assert cmd[cmd.index("--vae") + 1].endswith("diffusion_pytorch_model.safetensors"), cmd


def test_txt2img_zimage_turbo():
    img, _ = txt2img("a red apple on a wooden table", steps=2, size=256, seed=7,
                     model="zimage-turbo")
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
        generate._ENGINE_HELP_CACHE[fake_exe] = "--ip-adapter <string>"  # ไม่ให้ fake_run โดน --help
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


def test_img2img_mask_argv():
    import os
    import subprocess
    import tempfile
    import types
    import generate
    from PIL import Image
    seen = {}
    real_run = subprocess.run

    def fake_run(cmd, **kw):
        m = cmd[cmd.index("--mask") + 1]
        with Image.open(m) as im:
            seen["mask_size"], seen["mode"] = im.size, im.mode
        Image.new("RGB", (8, 8)).save(cmd[cmd.index("-o") + 1])
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    with tempfile.TemporaryDirectory() as td:
        fake_exe = os.path.join(td, "sd-cli.exe")
        fake_model = os.path.join(td, "sd_turbo.safetensors")
        open(fake_exe, "w").close()
        open(fake_model, "w").close()
        init = os.path.join(td, "in.png")
        Image.new("RGB", (200, 100)).save(init)
        mask = os.path.join(td, "mask.png")
        Image.new("RGB", (50, 25), (255, 255, 255)).save(mask)
        old_cli, old_model = generate.SD_CLI, generate.MODEL
        generate.SD_CLI, generate.MODEL = fake_exe, fake_model
        subprocess.run = fake_run
        try:
            generate.img2img(init, "x", steps=1, size=256, seed=1, mask=mask)
            try:
                generate.img2img(init, "x", steps=1, size=256, seed=1,
                                 mask=os.path.join(td, "nope.png"))
            except FileNotFoundError:
                pass
            else:
                raise AssertionError("มาสก์หายต้อง raise")
        finally:
            subprocess.run = real_run
            generate.SD_CLI, generate.MODEL = old_cli, old_model
    # sd-cli ต้องการมาสก์ขนาดเท่ารูปต้นฉบับ (ไม่ใช่ขนาดผลลัพธ์)
    assert seen == {"mask_size": (200, 100), "mode": "L"}, seen


def test_upscale_argv_and_failures():
    import os
    import subprocess
    import tempfile
    import types
    import generate
    from PIL import Image
    calls = []
    real_run = subprocess.run
    factor = {"v": 4}

    def fake_run(cmd, **kw):
        calls.append(cmd)
        src = cmd[cmd.index("-i") + 1]
        with Image.open(src) as im:
            w, h = im.size
        Image.new("RGB", (w * factor["v"], h * factor["v"])).save(cmd[cmd.index("-o") + 1])
        return types.SimpleNamespace(returncode=0, stdout="", stderr="new_upscaler_ctx failed")

    with tempfile.TemporaryDirectory() as td:
        fake_exe = os.path.join(td, "sd-cli.exe")
        open(fake_exe, "w").close()
        up_dir = os.path.join(td, "upscale")
        os.makedirs(up_dir)
        src = os.path.join(td, "pic.png")
        Image.new("RGB", (10, 6)).save(src)
        old = generate.SD_CLI, generate.UPSCALE_DIR, os.environ.pop("TEXT2IMAGE_UPSCALER", None)
        generate.SD_CLI, generate.UPSCALE_DIR = fake_exe, up_dir
        subprocess.run = fake_run
        try:
            try:
                generate.upscale(src)
            except FileNotFoundError as e:
                assert "models/upscale" in str(e)
            else:
                raise AssertionError("ไม่มีโมเดลต้อง raise")
            open(os.path.join(up_dir, "notes.txt"), "w").close()
            model = os.path.join(up_dir, "RealESRGAN_x4plus_anime_6B.pth")
            open(model, "w").close()
            assert generate.list_upscalers() == {"RealESRGAN_x4plus_anime_6B": model}
            img = generate.upscale(src, repeats=2)
            assert img.size == (40, 24)
            cmd = calls[-1]
            assert cmd[cmd.index("-M") + 1] == "upscale"
            assert cmd[cmd.index("--upscale-model") + 1] == model
            assert cmd[cmd.index("--upscale-repeats") + 1] == "2"
            # โมเดลโหลดไม่ขึ้น: sd-cli คืน 0 แต่เซฟรูปเดิม — ต้องรู้ว่าพัง
            factor["v"] = 1
            try:
                generate.upscale(src)
            except RuntimeError as e:
                assert "ขยายรูปไม่สำเร็จ" in str(e)
            else:
                raise AssertionError("ขนาดเท่าเดิมต้อง raise")
            for bad in ({"repeats": 0}, {"repeats": 9}, {"upscaler": "nope"}):
                try:
                    generate.upscale(src, **bad)
                except ValueError:
                    pass
                else:
                    raise AssertionError(bad)
        finally:
            subprocess.run = real_run
            generate.SD_CLI, generate.UPSCALE_DIR = old[0], old[1]
            if old[2] is not None:
                os.environ["TEXT2IMAGE_UPSCALER"] = old[2]


def test_lora_family_and_compat():
    import json
    import os
    import struct
    import tempfile
    import generate

    def fake_lora(path, names):
        h = json.dumps({n: {"dtype": "F16", "shape": [1], "data_offsets": [0, 2]} for n in names}).encode()
        with open(path, "wb") as f:
            f.write(struct.pack("<Q", len(h)) + h + bytes(2))

    with tempfile.TemporaryDirectory() as td:
        cases = {"a": ["diffusion_model.blocks.0.adaln_modulation_cross_attn.1.lora_A.weight"],
                 "k": ["diffusion_model.blocks.0.mlp.layer1.lora_A.weight",
                       "diffusion_model.blocks.0.mlp.layer1.alpha"],
                 "x": ["lora_te2_text_model_encoder_layers_0_mlp_fc1.lora_down.weight"],
                 "f": ["lora_unet_double_blocks_0_img_attn_proj.lora_down.weight"],
                 "u": ["something_else.weight"]}
        for n, keys in cases.items():
            fake_lora(os.path.join(td, n + ".safetensors"), keys)
        bad = os.path.join(td, "bad.safetensors")
        open(bad, "wb").write(b"junk")
        fam = {n: generate.lora_family(os.path.join(td, n + ".safetensors")) for n in cases}
        assert fam == {"a": "anima", "k": "anima", "x": "sdxl", "f": "flux1", "u": None}, fam
        assert generate.lora_family(bad) is None
        assert generate.lora_family(os.path.join(td, "nope.safetensors")) is None
        old = generate.LORA_ENV_DIRS
        generate.LORA_ENV_DIRS = [td]
        try:
            assert generate.lora_compatible("a", "anima-turbo")
            assert not generate.lora_compatible("a", "sdxl-base")
            assert not generate.lora_compatible("x", "anima-base")
            assert generate.lora_compatible("x", "sdxl-turbo")
            assert generate.lora_compatible("u", "sdxl-base")  # ไม่รู้ตระกูล → ไม่กัน
            assert generate.lora_compatible("a", "qwen21")  # โมเดลไม่อยู่ในตาราง → ไม่กัน
            assert generate.lora_compatible(None, "sdxl-base")
        finally:
            generate.LORA_ENV_DIRS = old


def test_custom_sdxl_checkpoints():
    import os
    import tempfile
    import generate
    with tempfile.TemporaryDirectory() as td:
        old = generate.SDXL_DIR
        generate.SDXL_DIR = td
        try:
            assert generate.list_sdxl_checkpoints() == {}
            ck = os.path.join(td, "RealVisXL_V5.0_Lightning_fp16.safetensors")
            open(ck, "w").close()
            open(os.path.join(td, "readme.txt"), "w").close()
            assert generate.list_sdxl_checkpoints() == {"RealVisXL_V5.0_Lightning_fp16": ck}
            mid = "sdxl:RealVisXL_V5.0_Lightning_fp16"
            assert generate.model_files(mid) == {"m": ck}
            try:
                generate.model_files("sdxl:gone")
            except FileNotFoundError as e:
                assert "RealVisXL" in str(e)
            else:
                raise AssertionError("ไฟล์หายต้อง raise")
            assert generate.model_family(mid) == "sdxl"
            assert generate.model_family("anima-turbo") == "anima"
            assert generate.model_family("qwen21") is None
            assert generate.supports_ip_adapter(mid)
            assert generate.supports_ip_adapter("sdxl-base")
            assert not generate.supports_ip_adapter("anima-turbo")
        finally:
            generate.SDXL_DIR = old


def test_extend_segments_needed():
    from generate import extend_segments_needed
    assert extend_segments_needed(1.0, 17, 16) == 1
    assert extend_segments_needed(3.0, 17, 16) == 3
    assert extend_segments_needed(5.0, 121, 24) == 1
    assert extend_segments_needed(10.0, 121, 24) == 2
    for bad in (lambda: extend_segments_needed(0, 17, 16),
                lambda: extend_segments_needed(-2, 17, 16),
                lambda: extend_segments_needed(3, 0, 16),
                lambda: extend_segments_needed(3, 17, 0),
                lambda: extend_segments_needed("นาน", 17, 16)):
        try:
            bad()
        except ValueError:
            pass
        else:
            raise AssertionError("ค่าผิดควร raise ValueError")


def test_resolve_ffmpeg_env_and_missing():
    import os
    import tempfile
    import generate
    with tempfile.TemporaryDirectory() as td:
        fake = os.path.join(td, "ffmpeg.exe")
        open(fake, "w").close()
        old_env = os.environ.get("GENJAB_FFMPEG")
        os.environ["GENJAB_FFMPEG"] = fake
        try:
            assert generate.resolve_ffmpeg() == fake
        finally:
            if old_env is None:
                os.environ.pop("GENJAB_FFMPEG", None)
            else:
                os.environ["GENJAB_FFMPEG"] = old_env
        old_env = os.environ.get("GENJAB_FFMPEG")
        old_path = os.environ.get("PATH")
        old_dir = generate.app_dir
        sub = os.path.join(td, "empty")
        os.makedirs(sub)
        old_pf = os.environ.get("ProgramFiles")
        os.environ["GENJAB_FFMPEG"] = os.path.join(sub, "nope.exe")
        os.environ["PATH"] = sub
        os.environ["ProgramFiles"] = sub  # ซ่อน ffmpeg ที่ติดมากับ Amuse ด้วย
        generate.app_dir = lambda: sub
        try:
            try:
                generate.resolve_ffmpeg()
            except FileNotFoundError as e:
                assert "ffmpeg" in str(e).lower(), e
            else:
                raise AssertionError("หา ffmpeg ไม่เจอควร raise FileNotFoundError")
            # มี ffmpeg ของ Amuse (Program Files\Amuse) → ใช้ตัวนั้น
            amuse = os.path.join(sub, "Amuse", "ffmpeg.exe")
            os.makedirs(os.path.dirname(amuse))
            open(amuse, "w").close()
            assert generate.resolve_ffmpeg() == amuse
        finally:
            if old_pf is None:
                os.environ.pop("ProgramFiles", None)
            else:
                os.environ["ProgramFiles"] = old_pf
            if old_env is None:
                os.environ.pop("GENJAB_FFMPEG", None)
            else:
                os.environ["GENJAB_FFMPEG"] = old_env
            if old_path is None:
                os.environ.pop("PATH", None)
            else:
                os.environ["PATH"] = old_path
            generate.app_dir = old_dir


def test_extract_frame_invalid():
    import os
    import tempfile
    from generate import extract_frame
    with tempfile.TemporaryDirectory() as td:
        missing = os.path.join(td, "nope.webm")
        try:
            extract_frame(missing, os.path.join(td, "f.png"))
        except FileNotFoundError:
            pass
        else:
            raise AssertionError("วิดีโอหายควร raise FileNotFoundError")
        real = os.path.join(td, "v.webm")
        open(real, "w").close()
        try:
            extract_frame(real, os.path.join(td, "f.png"), which="กลาง")
        except ValueError:
            pass
        else:
            raise AssertionError("which ผิดควร raise ValueError")


def test_extract_frame_sends_argv():
    import os
    import subprocess
    import tempfile
    import types
    import generate
    calls = []
    real_run = subprocess.run

    def fake_run(cmd, **kw):
        calls.append(cmd)
        open(cmd[-1], "w").close()
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    with tempfile.TemporaryDirectory() as td:
        vid = os.path.join(td, "v.webm")
        open(vid, "w").close()
        old = generate.resolve_ffmpeg
        generate.resolve_ffmpeg = lambda: os.path.join(td, "ffmpeg.exe")
        subprocess.run = fake_run
        try:
            out = generate.extract_frame(vid, os.path.join(td, "last.png"), which="last")
            assert os.path.isfile(out), out
            first = generate.extract_frame(vid, os.path.join(td, "first.png"), which="first")
            assert os.path.isfile(first), first
        finally:
            subprocess.run = real_run
            generate.resolve_ffmpeg = old
    assert calls[0][calls[0].index("-i") + 1] == vid
    assert "-sseof" in calls[0], calls[0]
    assert "-sseof" not in calls[1], calls[1]


def test_concat_videos_invalid():
    import os
    import tempfile
    from generate import concat_videos
    with tempfile.TemporaryDirectory() as td:
        try:
            concat_videos([], os.path.join(td, "o.webm"))
        except ValueError:
            pass
        else:
            raise AssertionError("parts ว่างควร raise ValueError")
        try:
            concat_videos([os.path.join(td, "nope.webm")], os.path.join(td, "o.webm"))
        except FileNotFoundError:
            pass
        else:
            raise AssertionError("ท่อนหายควร raise FileNotFoundError")
        real = os.path.join(td, "a.webm")
        open(real, "w").close()
        try:
            concat_videos([real], os.path.join(td, "o.mp4"))
        except ValueError:
            pass
        else:
            raise AssertionError("นามสกุลผิดควร raise ValueError")


def test_concat_videos_sends_argv():
    import os
    import subprocess
    import tempfile
    import types
    import generate
    calls = []
    real_run = subprocess.run

    def fake_run(cmd, **kw):
        calls.append(cmd)
        open(cmd[-1], "w").close()
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    with tempfile.TemporaryDirectory() as td:
        parts = []
        for name in ("a.webm", "b.webm"):
            p = os.path.join(td, name)
            open(p, "w").close()
            parts.append(p)
        out = os.path.join(td, "o.webm")
        old = generate.resolve_ffmpeg
        generate.resolve_ffmpeg = lambda: os.path.join(td, "ffmpeg.exe")
        subprocess.run = fake_run
        try:
            got = generate.concat_videos(parts, out)
        finally:
            subprocess.run = real_run
            generate.resolve_ffmpeg = old
    assert got == os.path.abspath(out), got
    cmd = calls[0]
    assert cmd[cmd.index("-f") + 1] == "concat", cmd
    assert cmd[cmd.index("-c") + 1] == "copy", cmd
    assert cmd[-1] == os.path.abspath(out), cmd


def test_img2vid_extend_invalid_without_sdcli():
    import os
    import tempfile
    import generate
    from generate import img2vid_extend
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
                lambda: img2vid_extend(missing, "x", segments=2, output=out),
                lambda: img2vid_extend(init, "x", segments=2, model="sd-turbo", output=out),
                lambda: img2vid_extend(init, "x", output=out),  # ไม่บอก target/segs
                lambda: img2vid_extend(init, "x", target_secs=0, output=out),
                lambda: img2vid_extend(init, "x", target_secs=-5, output=out),
                lambda: img2vid_extend(init, "x", target_secs="นาน", output=out),
                lambda: img2vid_extend(init, "x", segments=0, output=out),
                lambda: img2vid_extend(init, "x", segments=2, frames=0, output=out),
                lambda: img2vid_extend(init, "x", segments=2, fps=0, output=out),
                lambda: img2vid_extend(init, "x", segments=2,
                                      output=os.path.join(td, "x.mp4")),
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


def test_img2vid_extend_chains():
    import os
    import tempfile
    import generate
    from generate import img2vid_extend
    vid_calls, grabs, cats, segs_cb = [], [], [], []
    old_vid, old_grab, old_cat = (generate.img2vid, generate.extract_frame,
                                  generate.concat_videos)
    old_ff, old_cli = generate.resolve_ffmpeg, generate.SD_CLI

    def fake_vid(init_path, prompt, **kw):
        vid_calls.append((init_path, kw.get("seed")))
        seg = os.path.join(kw["output"])
        open(seg, "w").close()
        return seg, kw.get("seed")

    def fake_grab(video, out_png, which="last"):
        grabs.append((video, out_png, which))
        open(out_png, "w").close()
        return out_png

    def fake_cat(parts, output):
        cats.append((list(parts), output))
        open(output, "w").close()
        return os.path.abspath(output)

    generate.img2vid, generate.extract_frame, generate.concat_videos = fake_vid, fake_grab, fake_cat
    generate.resolve_ffmpeg = lambda: os.path.join("nowhere", "ffmpeg.exe")
    try:
        with tempfile.TemporaryDirectory() as td:
            # CI ไม่มี Amuse — ชี้ SD_CLI ไปไฟล์ปลอมให้ผ่านเช็ก isfile
            fake_cli = os.path.join(td, "sd-cli.exe")
            open(fake_cli, "w").close()
            generate.SD_CLI = fake_cli
            init = os.path.join(td, "in.png")
            open(init, "w").close()
            out = os.path.join(td, "long.webm")
            got, seeds = img2vid_extend(init, "drift", target_secs=3.0, frames=17,
                                       fps=16, size=256, seed=7, output=out,
                                       on_segment=lambda i, n: segs_cb.append((i, n)))
    finally:
        (generate.img2vid, generate.extract_frame,
         generate.concat_videos) = old_vid, old_grab, old_cat
        generate.resolve_ffmpeg, generate.SD_CLI = old_ff, old_cli
    assert got == os.path.abspath(out), got
    assert seeds == [7, 8, 9], seeds  # 3วิ*16fps=48f -> ceil(48/17)=3 ท่อน
    assert len(vid_calls) == 3, vid_calls
    assert vid_calls[0][0] == os.path.abspath(init), vid_calls
    assert vid_calls[1][0] == grabs[0][1], (vid_calls, grabs)  # ท่อน2ใช้เฟรมท้ายท่อน1
    assert vid_calls[2][0] == grabs[1][1], (vid_calls, grabs)
    assert segs_cb == [(1, 3), (2, 3), (3, 3)], segs_cb
    assert len(cats) == 1 and len(cats[0][0]) == 3, cats


def test_concat_mp4_copy_invalid():
    import os
    import tempfile
    import generate
    with tempfile.TemporaryDirectory() as td:
        try:
            generate._concat_mp4_copy([], os.path.join(td, "o.mp4"))
        except ValueError:
            pass
        else:
            raise AssertionError("parts ว่างควร raise ValueError")
        try:
            generate._concat_mp4_copy([os.path.join(td, "nope.mp4")],
                                      os.path.join(td, "o.mp4"))
        except FileNotFoundError:
            pass
        else:
            raise AssertionError("ท่อนหายควร raise FileNotFoundError")
        real = os.path.join(td, "a.mp4")
        open(real, "w").close()
        try:
            generate._concat_mp4_copy([real], os.path.join(td, "o.webm"))
        except ValueError:
            pass
        else:
            raise AssertionError("นามสกุลผิดควร raise ValueError")


def test_img2vid_extend_comfy_routes():
    import os
    import tempfile
    import generate
    from generate import img2vid_extend
    vid_calls, grabs, cats = [], [], []
    old = (generate.comfy_i2v, generate.extract_frame,
           generate._concat_mp4_copy, generate.resolve_ffmpeg)

    def fake_vid(init_path, prompt, **kw):
        vid_calls.append((init_path, kw.get("seed"), kw.get("output")))
        open(kw["output"], "w").close()
        return kw["output"], kw.get("seed")

    def fake_grab(video, out_png, which="last"):
        grabs.append((video, out_png, which))
        open(out_png, "w").close()
        return out_png

    def fake_cat(parts, output):
        cats.append((list(parts), output))
        open(output, "w").close()
        return os.path.abspath(output)

    generate.comfy_i2v = fake_vid
    generate.extract_frame = fake_grab
    generate._concat_mp4_copy = fake_cat
    generate.resolve_ffmpeg = lambda: os.path.join("nowhere", "ffmpeg.exe")
    try:
        with tempfile.TemporaryDirectory() as td:
            init = os.path.join(td, "in.png")
            open(init, "w").close()
            # ท่อนเดียว + output .webm → สลับเป็น .mp4 อัตโนมัติ
            got, seeds = img2vid_extend(init, "drift", segments=1,
                                        frames=17, fps=16, size=256, seed=7,
                                        model="wan22-14b-comfy",
                                        output=os.path.join(td, "one.webm"))
            assert got.endswith(".mp4") and seeds == [7], (got, seeds)
            assert len(vid_calls) == 1 and vid_calls[0][2].endswith(".mp4")
            # หลายท่อน → ต่อด้วย mp4 helper ไม่ใช่ concat_videos
            got2, seeds2 = img2vid_extend(init, "drift", segments=2,
                                          frames=17, fps=16, size=256, seed=7,
                                          model="wan22-14b-comfy",
                                          output=os.path.join(td, "two.mp4"))
            assert got2.endswith(".mp4") and seeds2 == [7, 8], (got2, seeds2)
            assert len(cats) == 1 and len(cats[0][0]) == 2, cats
            assert len(vid_calls) == 3, vid_calls
    finally:
        (generate.comfy_i2v, generate.extract_frame,
         generate._concat_mp4_copy, generate.resolve_ffmpeg) = old


def test_img2vid_extend_tiny_real():
    import os
    import tempfile
    from PIL import Image, ImageDraw
    import generate
    from generate import img2vid_extend
    try:
        generate.resolve_ffmpeg()
    except FileNotFoundError as e:
        print("SKIP extend_real (ไม่มี ffmpeg):", e)
        return
    with tempfile.TemporaryDirectory() as td:
        init = os.path.join(td, "in.png")
        base = Image.new("RGB", (256, 144), (20, 30, 60))
        ImageDraw.Draw(base).ellipse([100, 40, 156, 100], fill=(200, 150, 80))
        base.save(init)
        out = os.path.join(td, "long.webm")
        path, seeds = img2vid_extend(init, "moon glowing softly", segments=2,
                                    frames=9, fps=16, steps=2, size=256,
                                    seed=7, output=out)
        assert os.path.isfile(path), path
        assert seeds == [7, 8], seeds
        assert os.path.getsize(path) > 0
        with open(path, "rb") as f:
            assert f.read(4).hex() == "1a45dfa3"


def test_amuse_path_layouts():
    import os
    import tempfile
    import generate
    from generate import amuse_path, amuse_subdirs
    with tempfile.TemporaryDirectory() as td:
        old = generate.AMUSE_MODELS
        generate.AMUSE_MODELS = td
        try:
            assert amuse_subdirs("diffusion") == [os.path.join(td, "diffusion_models"),
                                                 os.path.join(td, "Diffusion")]
            assert amuse_subdirs("lora") == [os.path.join(td, "loras"),
                                             os.path.join(td, "LoraAdapter")]
            # ไม่มีเลย → คืนชื่อใหม่ (layout ปัจจุบัน)
            assert amuse_path("diffusion", "x.gguf") == os.path.join(td, "diffusion_models", "x.gguf")
            # มีแค่เก่า → คืนเก่า (เครื่อง Amuse 3.x ยังใช้ได้)
            old_p = os.path.join(td, "Diffusion", "x.gguf")
            os.makedirs(os.path.dirname(old_p))
            open(old_p, "w").close()
            assert amuse_path("diffusion", "x.gguf") == old_p
            # มีทั้งคู่ → ใหม่ชนะ
            new_p = os.path.join(td, "diffusion_models", "x.gguf")
            os.makedirs(os.path.dirname(new_p))
            open(new_p, "w").close()
            assert amuse_path("diffusion", "x.gguf") == new_p
        finally:
            generate.AMUSE_MODELS = old


def test_model_files_qwen21_v4_layout():
    import os
    import tempfile
    import generate
    with tempfile.TemporaryDirectory() as td:
        diff = os.path.join(td, "diffusion_models")
        te = os.path.join(td, "text_encoders")
        ae = os.path.join(td, "vae")
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


def test_model_files_moss_sft_mixed_layout():
    import os
    import tempfile
    import generate
    with tempfile.TemporaryDirectory() as td:
        # diffusion/te/vae ชื่อใหม่ (4.0) + tokenizer ค้างชื่อเก่า → ต้องเจอหมด
        diff = os.path.join(td, "diffusion_models")
        te = os.path.join(td, "text_encoders")
        ae = os.path.join(td, "vae", "Flux2")
        tok = os.path.join(td, "Tokenizer", "MossImage")
        os.makedirs(diff)
        os.makedirs(te)
        os.makedirs(ae)
        os.makedirs(tok)
        want = {"diffusion": os.path.join(diff, "MOSS-Image-SFT-Q8_0.gguf"),
                "llm": os.path.join(te, "Qwen3.5-9B-Q8_0.gguf"),
                "vae": os.path.join(ae, "diffusion_pytorch_model.safetensors"),
                "tokenizer": os.path.join(tok, "tokenizer.json")}
        for p in want.values():
            open(p, "w").close()
        old = generate.AMUSE_MODELS
        generate.AMUSE_MODELS = td
        try:
            assert model_files("moss-sft") == want
        finally:
            generate.AMUSE_MODELS = old


def test_model_files_anima_turbo_v4_layout():
    import os
    import tempfile
    import generate
    from generate import model_files
    with tempfile.TemporaryDirectory() as td:
        amuse_diff = os.path.join(td, "Amuse", "diffusion_models")
        local = os.path.join(td, "models")
        te = os.path.join(td, "Amuse", "text_encoders")
        ae = os.path.join(td, "Amuse", "vae", "QwenImage")
        os.makedirs(amuse_diff)
        os.makedirs(local)
        os.makedirs(te)
        os.makedirs(ae)
        open(os.path.join(te, "Qwen3-0.6B-Q8_0.gguf"), "w").close()
        open(os.path.join(ae, "diffusion_pytorch_model.safetensors"), "w").close()
        v11 = os.path.join(amuse_diff, "anima-turbo-v1.1.safetensors")
        open(v11, "w").close()
        old_amuse, old_local = generate.AMUSE_MODELS, generate.LOCAL_MODELS
        generate.AMUSE_MODELS = os.path.join(td, "Amuse")
        generate.LOCAL_MODELS = local
        try:
            assert model_files("anima-turbo")["m"] == v11
            # ลบของ Amuse แล้ว → ตกไปใช้ไฟล์ใน models/
            os.remove(v11)
            local_v11 = os.path.join(local, "anima-turbo-v1.1.safetensors")
            open(local_v11, "w").close()
            assert model_files("anima-turbo")["m"] == local_v11
        finally:
            generate.AMUSE_MODELS, generate.LOCAL_MODELS = old_amuse, old_local


def test_lora_dirs_v4_layout():
    import os
    import tempfile
    import generate
    with tempfile.TemporaryDirectory() as td:
        new_d = os.path.join(td, "loras")
        old_d = os.path.join(td, "LoraAdapter")
        os.makedirs(new_d)
        os.makedirs(old_d)
        new_f = os.path.join(new_d, "v4-layout-probe-new.safetensors")
        old_f = os.path.join(old_d, "v4-layout-probe-old.safetensors")
        dup_new = os.path.join(new_d, "v4-layout-dup.safetensors")
        dup_old = os.path.join(old_d, "v4-layout-dup.safetensors")
        for p in (new_f, old_f, dup_new, dup_old):
            open(p, "w").close()
        old_amuse, old_env = generate.AMUSE_MODELS, generate.LORA_ENV_DIRS
        generate.AMUSE_MODELS = td
        generate.LORA_ENV_DIRS = []
        try:
            found = list_loras()
            assert found["v4-layout-probe-new"] == new_f
            assert found["v4-layout-probe-old"] == old_f
            assert found["v4-layout-dup"] == dup_new
        finally:
            generate.AMUSE_MODELS, generate.LORA_ENV_DIRS = old_amuse, old_env


def test_restyle_video_invalid():
    import os
    import tempfile
    from generate import restyle_video
    with tempfile.TemporaryDirectory() as td:
        missing = os.path.join(td, "nope.mp4")
        try:
            restyle_video(missing, "drift", output=os.path.join(td, "o.webm"))
        except FileNotFoundError:
            pass
        else:
            raise AssertionError("วิดีโอหายควร raise FileNotFoundError")
        real = os.path.join(td, "v.mp4")
        open(real, "w").close()
        bad = [
            lambda: restyle_video(real, "x", model="wan22-5b",
                                  output=os.path.join(td, "o.webm")),
            lambda: restyle_video(real, "x", strength=0,
                                  output=os.path.join(td, "o.webm")),
            lambda: restyle_video(real, "x", strength=1.5,
                                  output=os.path.join(td, "o.webm")),
            lambda: restyle_video(real, "x", fps=0,
                                  output=os.path.join(td, "o.webm")),
            lambda: restyle_video(real, "x", size=0,
                                  output=os.path.join(td, "o.webm")),
            lambda: restyle_video(real, "x", output=os.path.join(td, "o.mp4")),
        ]
        for fn in bad:
            try:
                fn()
            except ValueError:
                pass
            else:
                raise AssertionError("เคสผิดควร raise ValueError")


def test_restyle_video_chains_frames_with_fixed_seed():
    import os
    import subprocess
    import tempfile
    import threading
    import types
    from PIL import Image
    import generate
    from generate import restyle_video
    calls = []
    seen_seeds = []
    prompts = []
    real_run = subprocess.run
    real_img2img = generate.img2img

    def fake_img2img(init_path, prompt="", **kw):
        seen_seeds.append(kw.get("seed"))
        prompts.append(prompt)
        with Image.open(init_path) as im:
            return im.convert("RGB"), kw.get("seed")

    def fake_run(cmd, **kw):
        calls.append(cmd)
        if "-vf" in cmd:
            d = os.path.dirname(cmd[-1])
            for i in (1, 2, 3):
                Image.new("RGB", (64, 64), (i * 40, 10, 10)).save(
                    os.path.join(d, f"frame{i:05d}.png"))
        else:
            open(cmd[-1], "w").close()
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, "in.mp4")
        open(src, "w").close()
        out = os.path.join(td, "toon.webm")
        old_ff = generate.resolve_ffmpeg
        generate.resolve_ffmpeg = lambda: os.path.join(td, "ffmpeg.exe")
        generate.img2img = fake_img2img
        subprocess.run = fake_run
        progress = []
        try:
            got, seed, n = restyle_video(
                src, "a fox", output=out, model="sdxl-turbo", size=256,
                fps=8, strength=0.5, steps=1, seed=11,
                on_frame=lambda i, total: progress.append((i, total)))
        finally:
            subprocess.run = real_run
            generate.img2img = real_img2img
            generate.resolve_ffmpeg = old_ff
    assert got == os.path.abspath(out), got
    assert seed == 11 and n == 3, (seed, n)
    assert seen_seeds == [11, 11, 11], seen_seeds
    assert all("3d cartoon" in p for p in prompts), prompts
    assert progress == [(1, 3), (2, 3), (3, 3)], progress
    extract, encode = calls
    assert extract[extract.index("-vf") + 1] == "fps=8", extract
    assert "-framerate" in encode and "libvpx-vp9" in encode, encode
    # เสียงต้นฉบับต้องถูก map กลับมา + แปลงเป็น opus (copy AAC ลง webm ไม่ได้)
    assert "1:a?" in encode and "-shortest" in encode, encode
    assert "libopus" in encode and "copy" not in encode, encode


def test_restyle_video_aac_audio_webm_real():
    """ประกอบคลิป restyle จาก AAC-source จริงต้องได้ webm (opus) — กันพังซ้ำจุด user เจอ."""
    import os
    import subprocess
    import tempfile
    from PIL import Image
    import generate
    from generate import restyle_video
    try:
        ff = generate.resolve_ffmpeg()
    except FileNotFoundError as e:
        print("SKIP restyle_audio_real (ไม่มี ffmpeg):", e)
        return
    real_img2img = generate.img2img

    def fake_img2img(init_path, prompt="", **kw):
        with Image.open(init_path) as im:
            return im.convert("RGB"), kw.get("seed", 0)

    generate.img2img = fake_img2img
    try:
        with tempfile.TemporaryDirectory() as td:
            src = os.path.join(td, "in.mp4")
            p = subprocess.run(
                [ff, "-y", "-v", "error", "-f", "lavfi",
                 "-i", "testsrc=duration=2:size=64x64:rate=1",
                 "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
                 "-pix_fmt", "yuv420p", "-c:a", "aac", src],
                capture_output=True, text=True, errors="replace")
            assert p.returncode == 0 and os.path.isfile(src), p.stderr[-400:]
            out = os.path.join(td, "toon.webm")
            got, seed, n = restyle_video(
                src, "a fox", output=out, size=64, fps=1,
                strength=0.5, steps=1, seed=3)
            assert os.path.isfile(got) and os.path.getsize(got) > 1000, got
            assert n == 2, n
            probed = subprocess.run(
                [ff, "-hide_banner", "-i", got],
                capture_output=True, text=True, errors="replace")
            assert "Audio: opus" in probed.stderr, probed.stderr[-400:]
    finally:
        generate.img2img = real_img2img


def test_restyle_video_failed_encode_removes_stub():
    """encode พังต้องไม่ทิ้งไฟล์ซากเปิดไม่ได้ไว้หลอกว่าเป็นคลิป."""
    import os
    import subprocess
    import tempfile
    import types
    from PIL import Image
    import generate
    from generate import restyle_video
    real_run = subprocess.run
    real_img2img = generate.img2img

    def fake_img2img(init_path, prompt="", **kw):
        with Image.open(init_path) as im:
            return im.convert("RGB"), kw.get("seed", 0)

    def fake_run(cmd, **kw):
        if "-vf" in cmd:
            d = os.path.dirname(cmd[-1])
            Image.new("RGB", (64, 64), (10, 10, 10)).save(
                os.path.join(d, "frame00001.png"))
        else:
            open(cmd[-1], "w").close()  # ทิ้งซากแบบ ffmpeg ตอน header เขียนไม่ผ่าน
        return types.SimpleNamespace(returncode=1, stdout="", stderr="boom")

    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, "in.mp4")
        open(src, "w").close()
        out = os.path.join(td, "toon.webm")
        old_ff = generate.resolve_ffmpeg
        generate.resolve_ffmpeg = lambda: os.path.join(td, "ffmpeg.exe")
        generate.img2img = fake_img2img
        subprocess.run = fake_run
        try:
            try:
                restyle_video(src, "x", output=out, size=64, fps=1,
                              strength=0.5, steps=1, seed=1)
            except RuntimeError:
                pass
            else:
                raise AssertionError("encode พังควร raise RuntimeError")
            assert not os.path.isfile(out), "ต้องลบไฟล์ซากทิ้ง"
        finally:
            subprocess.run = real_run
            generate.img2img = real_img2img
            generate.resolve_ffmpeg = old_ff


def test_restyle_video_cancelled():
    import os
    import tempfile
    import threading
    from generate import GenerationCancelled, restyle_video
    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, "in.mp4")
        open(src, "w").close()
        ev = threading.Event()
        ev.set()
        try:
            restyle_video(src, "x", output=os.path.join(td, "o.webm"),
                          cancel_event=ev)
        except GenerationCancelled:
            pass
        else:
            raise AssertionError("cancel ก่อนเริ่มควร raise GenerationCancelled")


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
        test_txt2img_zimage_turbo()
        test_txt2vid_wan22_5b()
        test_txt2img_batch()
        test_txt2img_batch_invalid_count()
        test_img2img_sd_turbo()
        test_img2img_face_sdxl_turbo()
        test_img2vid_wan22_tiny()
        test_img2vid_extend_tiny_real()
    test_lora_prompt_and_resolve()
    test_lora_invalid()
    test_model_files_sdxl_turbo_env_override()
    test_model_files_unknown_model()
    test_app_dir_source_and_frozen()
    test_resolve_sd_cli_bundled_and_env()
    test_resolve_sd_cli_alt_order()
    test_path_tag()
    test_sd_cli_for_selection()
    test_sd_cli_for_preset_guard()
    test_sd_cli_for_rocm()
    test_face_engine_fallback()
    test_preview_args_and_run_callback()
    test_sd_server_helpers()
    test_controlnet_args()
    test_local_llm_helpers()
    test_audio_gen_helpers()
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
    test_model_files_fibo2_turbo()
    test_txt2img_fibo2_argv()
    test_model_files_minimax_h3_image()
    test_txt2img_minimax_h3_image_argv()
    test_model_files_moss_sft()
    test_txt2img_moss_sft_argv()
    test_model_files_anima_turbo_v11()
    test_model_files_iris_turbo()
    test_txt2img_iris_turbo_argv()
    test_model_files_flux2_dev()
    test_txt2img_flux2_dev_argv()
    test_model_files_zimage_turbo()
    test_amuse_path_layouts()
    test_model_files_qwen21_v4_layout()
    test_model_files_moss_sft_mixed_layout()
    test_model_files_anima_turbo_v4_layout()
    test_lora_dirs_v4_layout()
    test_txt2img_zimage_argv()
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
    test_img2img_mask_argv()
    test_upscale_argv_and_failures()
    test_lora_family_and_compat()
    test_custom_sdxl_checkpoints()
    test_fit_video_size()
    test_model_files_wan22_local_first()
    test_img2vid_invalid_without_sdcli()
    test_img2vid_sends_argv()
    test_extend_segments_needed()
    test_resolve_ffmpeg_env_and_missing()
    test_extract_frame_invalid()
    test_extract_frame_sends_argv()
    test_concat_videos_invalid()
    test_concat_videos_sends_argv()
    test_img2vid_extend_invalid_without_sdcli()
    test_img2vid_extend_chains()
    test_concat_mp4_copy_invalid()
    test_img2vid_extend_comfy_routes()
    test_restyle_video_invalid()
    test_restyle_video_chains_frames_with_fixed_seed()
    test_restyle_video_aac_audio_webm_real()
    test_restyle_video_failed_encode_removes_stub()
    test_restyle_video_cancelled()
    if backend:
        test_random_seed_differs()
    print("smoke OK" if backend else "fast OK")
