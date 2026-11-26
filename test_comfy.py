"""เทส backend ComfyUI (comfy_client + comfy_txt2img) แบบไม่ต่อ server จริง — `python test_comfy.py`"""
import io
import json
import os
import threading
import urllib.error
from unittest import mock

from PIL import Image

import comfy_client as cc
import generate
from generate import GenerationCancelled


def png_bytes(w=8, h=6, color="red"):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, "PNG")
    return buf.getvalue()


class FakeResp:
    def __init__(self, data):
        self.data = data

    def read(self):
        return self.data

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def fake_urlopen_factory(routes):
    """routes: list of (url_substring, bytes|Exception) — คืน response ตามคิวที่ตรง url."""
    calls = []

    def fake(req, timeout=None):
        url = req.full_url if hasattr(req, "full_url") else req
        calls.append(url)
        for sub, reply in routes:
            if sub in url:
                if isinstance(reply, Exception):
                    raise reply
                return FakeResp(reply() if callable(reply) else reply)
        raise AssertionError("unexpected url: " + url)

    fake.calls = calls
    return fake


# ---------- server_url ----------

def test_server_url_default():
    with mock.patch.dict(os.environ, {}, clear=False):
        os.environ.pop(cc.SERVER_ENV, None)
        assert cc.server_url() == cc.DEFAULT_SERVER, cc.server_url()


def test_server_url_env_and_slash():
    with mock.patch.dict(os.environ, {cc.SERVER_ENV: "http://192.168.1.51:8188/"}):
        assert cc.server_url() == "http://192.168.1.51:8188", cc.server_url()


# ---------- build_txt2img ----------

def test_build_injects_params():
    wf = cc.build_txt2img("a cat", negative="blurry", seed=7, steps=5, cfg=3.0,
                          w=768, h=512, ckpt="juggernaut-xl")
    assert wf["6"]["inputs"]["text"] == "a cat"
    assert wf["7"]["inputs"]["text"] == "blurry"
    assert wf["5"]["inputs"]["width"] == 768
    assert wf["5"]["inputs"]["height"] == 512
    ks = wf["3"]["inputs"]
    assert (ks["seed"], ks["steps"], ks["cfg"]) == (7, 5, 3.0), ks
    assert wf["4"]["inputs"]["ckpt_name"].endswith(".safetensors")
    assert "10" not in wf
    assert "comment" not in wf


def test_build_lora_rewires():
    wf = cc.build_txt2img("a cat", lora="lcm-lora-sdxl.safetensors", lora_strength=0.8)
    lora = wf["10"]
    assert lora["class_type"] == "LoraLoader"
    assert lora["inputs"]["lora_name"] == "lcm-lora-sdxl.safetensors"
    assert lora["inputs"]["strength_model"] == 0.8
    assert wf["6"]["inputs"]["clip"] == ["10", 1]
    assert wf["3"]["inputs"]["model"] == ["10", 0]


def test_build_empty_prompt_rejected():
    for bad in ("", "   ", None):
        try:
            cc.build_txt2img(bad)
        except cc.ComfyError:
            pass
        else:
            raise AssertionError("prompt ว่างควร raise: %r" % (bad,))


def test_build_raw_ckpt_passthrough():
    wf = cc.build_txt2img("a cat", ckpt="custom.safetensors")
    assert wf["4"]["inputs"]["ckpt_name"] == "custom.safetensors"


# ---------- queue_prompt ----------

def test_queue_ok():
    fake = fake_urlopen_factory([("/prompt", json.dumps({"prompt_id": "abc", "number": 0}).encode())])
    with mock.patch("comfy_client._open", fake):
        assert cc.queue_prompt({"3": {}}) == "abc"
    assert fake.calls[0].endswith("/prompt")


def test_queue_sends_workflow_body():
    seen = {}

    def fake(req, timeout=None):
        seen["body"] = json.loads(req.data.decode())
        return FakeResp(json.dumps({"prompt_id": "x"}).encode())

    with mock.patch("comfy_client._open", fake):
        cc.queue_prompt({"9": {"class_type": "SaveImage"}})
    assert seen["body"]["prompt"]["9"]["class_type"] == "SaveImage"


def test_queue_validation_error():
    payload = json.dumps({"error": "bad prompt", "node_errors": {"3": "missing"}}).encode()
    fake = fake_urlopen_factory([("/prompt", payload)])
    with mock.patch("comfy_client._open", fake):
        try:
            cc.queue_prompt({})
        except cc.ComfyError as e:
            assert "bad prompt" in str(e), e
        else:
            raise AssertionError("validation error ควร raise")


def test_queue_node_errors_named():
    payload = json.dumps({"node_errors": {"7": "bad clip"}}).encode()
    fake = fake_urlopen_factory([("/prompt", payload)])
    with mock.patch("comfy_client._open", fake):
        try:
            cc.queue_prompt({})
        except cc.ComfyError as e:
            assert "7" in str(e), e
        else:
            raise AssertionError("node_errors ควร raise พร้อมชื่อโหนด")


def test_queue_http_error_thai():
    err = urllib.error.HTTPError("http://x/prompt", 400, "Bad", {}, io.BytesIO(b"nope"))
    fake = fake_urlopen_factory([("/prompt", err)])
    with mock.patch("comfy_client._open", fake):
        try:
            cc.queue_prompt({})
        except cc.ComfyError as e:
            assert "400" in str(e), e
        else:
            raise AssertionError("HTTPError ควรกลายเป็น ComfyError")


def test_queue_unreachable_thai():
    fake = fake_urlopen_factory([("/prompt", urllib.error.URLError("refused"))])
    with mock.patch("comfy_client._open", fake):
        try:
            cc.queue_prompt({})
        except cc.ComfyError as e:
            assert cc.DEFAULT_SERVER in str(e) or cc.SERVER_ENV in str(e), e
        else:
            raise AssertionError("ต่อไม่ได้ควร raise พร้อมบอกที่อยู่ server")


# ---------- wait_result ----------

def hist(outputs=None, error=None):
    if error:
        return {"pid": {"status": {"status_str": "error", "messages": [["e", error]]}}}
    d = {"pid": {"status": {"status_str": "ok"}}}
    if outputs is not None:
        d["pid"]["outputs"] = outputs
    return d


def test_wait_polls_until_outputs():
    outs = {"9": {"images": [{"filename": "a.png", "subfolder": "", "type": "output"}]}}
    resps = [json.dumps(hist()).encode(), json.dumps(hist(outs)).encode()]
    fake = fake_urlopen_factory([("/history", lambda: resps.pop(0))])
    with mock.patch("comfy_client._open", fake):
        got = cc.wait_result("pid", timeout=30, poll=0.01)
    assert got == outs
    assert len(fake.calls) == 2, fake.calls


def test_wait_exec_error():
    fake = fake_urlopen_factory([("/history", json.dumps(hist(error="node 3 boom")).encode())])
    with mock.patch("comfy_client._open", fake):
        try:
            cc.wait_result("pid", timeout=30, poll=0.01)
        except cc.ComfyError as e:
            assert "boom" in str(e), e
        else:
            raise AssertionError("exec error ควร raise")


def test_wait_timeout():
    fake = fake_urlopen_factory([("/history", json.dumps(hist()).encode())])
    with mock.patch("comfy_client._open", fake):
        try:
            cc.wait_result("pid", timeout=0.05, poll=0.01)
        except cc.ComfyError as e:
            assert "เกิน" in str(e), e
        else:
            raise AssertionError("หมดเวลาควร raise")


def test_wait_cancel_interrupts():
    fake = fake_urlopen_factory([("/interrupt", b"{}"),
                                 ("/history", json.dumps(hist()).encode())])
    ev = threading.Event()
    ev.set()
    with mock.patch("comfy_client._open", fake):
        try:
            cc.wait_result("pid", timeout=30, poll=0.01, cancel_event=ev)
        except GenerationCancelled:
            pass
        else:
            raise AssertionError("cancel ควร raise GenerationCancelled")
    assert any("/interrupt" in c for c in fake.calls), fake.calls


# ---------- fetch_images ----------

def test_fetch_images_ok():
    outs = {"9": {"images": [{"filename": "a_00001_.png", "subfolder": "", "type": "output"}]}}
    blob = png_bytes()
    fake = fake_urlopen_factory([("/view", blob)])
    with mock.patch("comfy_client._open", fake):
        got = cc.fetch_images(outs)
    assert got == [blob]
    assert "filename=a_00001_.png" in fake.calls[0], fake.calls


def test_fetch_images_rejects_non_image():
    outs = {"9": {"images": [{"filename": "a.png", "subfolder": "", "type": "output"}]}}
    fake = fake_urlopen_factory([("/view", b"not an image")])
    with mock.patch("comfy_client._open", fake):
        try:
            cc.fetch_images(outs)
        except cc.ComfyError:
            pass
        else:
            raise AssertionError("ไฟล์ไม่ใช่รูปควร raise")


def test_fetch_images_empty_outputs():
    try:
        cc.fetch_images({})
    except cc.ComfyError:
        pass
    else:
        raise AssertionError("outputs ว่างควร raise")


# ---------- generate.comfy_txt2img ----------

def test_comfy_txt2img_wired():
    seen = {}
    real_q, real_w, real_f = cc.queue_prompt, cc.wait_result, cc.fetch_images
    real_e = cc.ensure_server
    outs = {"9": {"images": [{"filename": "a.png", "subfolder": "", "type": "output"}]}}
    try:
        cc.ensure_server = lambda **kw: True
        cc.queue_prompt = lambda wf: (seen.update(wf=wf), "pid")[1]
        cc.wait_result = lambda pid, **kw: outs
        cc.fetch_images = lambda o: [png_bytes(16, 12)]
        img, seed = generate.comfy_txt2img("a cat", steps=2, size=256, seed=11,
                                           ckpt="juggernaut-xl")
    finally:
        cc.queue_prompt, cc.wait_result, cc.fetch_images = real_q, real_w, real_f
        cc.ensure_server = real_e
    assert img.size == (16, 12), img.size  # คืนพิกเซลจริงจาก server ไม่ resize
    assert seed == 11
    assert seen["wf"]["5"]["inputs"]["width"] == 256
    assert seen["wf"]["3"]["inputs"]["steps"] == 2


def test_build_comfy_prefix_ckpt():
    wf = cc.build_txt2img("a cat", ckpt="comfy-juggernaut-xl")
    assert wf["4"]["inputs"]["ckpt_name"] == cc.COMFY_CKPTS["juggernaut-xl"]


def test_resolve_comfy_lora():
    assert cc.resolve_comfy_lora("ganjad-style-sdxl") == "ganjad-style-sdxl.safetensors"
    assert cc.resolve_comfy_lora("ganjad-style-sdxl-000004") == "ganjad-style-sdxl-000004.safetensors"
    assert cc.resolve_comfy_lora("lcm-lora-sdxl.safetensors") == "lcm-lora-sdxl.safetensors"
    assert cc.resolve_comfy_lora("C:\\models\\custom.safetensors") == "custom.safetensors"
    for bad in ("", "(ไม่ใช้)", None, "flux-ada", "anima-ganjad-style-anima",
                "moss-bolly-test", "ganjad-style-sdxl-000008"):
        assert cc.resolve_comfy_lora(bad) is None, bad


def test_check_lora_on_server_ok_and_missing():
    real = cc.list_models
    try:
        cc.list_models = lambda folder, timeout=30: ["ganjad-style-sdxl.safetensors",
                                                     "lcm-lora-sdxl.safetensors"]
        assert cc.check_lora_on_server("ganjad-style-sdxl.safetensors") is True
        try:
            cc.check_lora_on_server("nope.safetensors")
        except cc.ComfyError as e:
            assert "nope.safetensors" in str(e) and "lcm-lora" in str(e), e
        else:
            raise AssertionError("ไฟล์ไม่มีบน server ควร raise พร้อมรายชื่อ")
    finally:
        cc.list_models = real


def test_comfy_txt2img_rejects_unresolvable_lora():
    real_q = cc.queue_prompt
    try:
        cc.queue_prompt = lambda wf: (_ for _ in ()).throw(AssertionError("must not queue"))
        try:
            generate.comfy_txt2img("a cat", ckpt="juggernaut-xl", lora="flux-ada")
        except cc.ComfyError as e:
            assert "flux-ada" in str(e), e
        else:
            raise AssertionError("LoRA ใช้ไม่ได้ควร raise ก่อนยิงเน็ต")
    finally:
        cc.queue_prompt = real_q


def test_comfy_txt2img_lora_wired():
    seen = {}
    real_q, real_w, real_f, real_l = cc.queue_prompt, cc.wait_result, cc.fetch_images, cc.list_models
    real_e = cc.ensure_server
    try:
        cc.ensure_server = lambda **kw: True
        cc.list_models = lambda folder, timeout=30: ["ganjad-style-sdxl-000002.safetensors"]
        cc.queue_prompt = lambda wf: (seen.update(wf=wf), "pid")[1]
        cc.wait_result = lambda pid, **kw: {}
        cc.fetch_images = lambda o: [png_bytes(16, 12)]
        img, _ = generate.comfy_txt2img("a cat", ckpt="juggernaut-xl",
                                        lora="ganjad-style-sdxl-000002", lora_strength=0.7)
    finally:
        cc.queue_prompt, cc.wait_result, cc.fetch_images, cc.list_models = real_q, real_w, real_f, real_l
        cc.ensure_server = real_e
    lora = seen["wf"]["10"]
    assert lora["inputs"]["lora_name"] == "ganjad-style-sdxl-000002.safetensors"
    assert lora["inputs"]["strength_model"] == 0.7
    assert img.size == (16, 12)


def test_upload_image_ok_and_errors():
    blob = png_bytes(10, 10)
    seen = {}
    real_open = cc._open

    def fake(req, timeout=None):
        seen["ctype"] = req.get_header("Content-type")
        seen["body"] = req.data
        return FakeResp(json.dumps({"name": "up_init.png", "subfolder": "", "type": "input"}).encode())

    import tempfile
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "init.png")
        with open(p, "wb") as f:
            f.write(blob)
        cc._open = fake
        try:
            assert cc.upload_image(p) == "up_init.png"
        finally:
            cc._open = real_open
    assert "multipart/form-data" in seen["ctype"], seen["ctype"]
    assert blob in seen["body"]
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "note.txt")
        with open(p, "w") as f:
            f.write("hello")
        try:
            cc.upload_image(p)
        except cc.ComfyError as e:
            assert "PNG/JPEG/WebP" in str(e), e
        else:
            raise AssertionError("ไฟล์ที่ไม่ใช่รูปควร raise")


def test_upload_image_server_rejects():
    import tempfile
    real_open = cc._open
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "a.png")
        with open(p, "wb") as f:
            f.write(png_bytes())
        cc._open = lambda req, timeout=None: FakeResp(b"{}")
        try:
            cc.upload_image(p)
        except cc.ComfyError:
            pass
        else:
            raise AssertionError("ตอบกลับไม่มี name ควร raise")
        finally:
            cc._open = real_open


def test_build_img2img_plain_and_mask():
    wf = cc.build_img2img("a cat", seed=3, steps=5, cfg=1.5, ckpt="juggernaut-xl",
                          init_image="up.png", strength=0.7)
    assert wf["11"] == {"class_type": "LoadImage", "inputs": {"image": "up.png"}}
    assert wf["12"]["class_type"] == "VAEEncode"
    assert wf["12"]["inputs"] == {"pixels": ["11", 0], "vae": ["4", 2]}
    assert wf["3"]["inputs"]["denoise"] == 0.7
    assert wf["3"]["inputs"]["latent_image"] == ["12", 0]
    assert "13" not in wf
    m = cc.build_img2img("a cat", init_image="up.png", mask_image="m.png")
    assert m["12"]["class_type"] == "VAEEncodeForInpaint"
    assert m["12"]["inputs"]["mask"] == ["14", 0]
    assert m["12"]["inputs"]["grow_mask_by"] == 6
    assert m["13"] == {"class_type": "LoadImage", "inputs": {"image": "m.png"}}
    assert m["14"] == {"class_type": "ImageToMask",
                       "inputs": {"image": ["13", 0], "channel": "red"}}


def test_build_img2img_rejects():
    for kw in ({"prompt": "  ", "init_image": "a.png"},
               {"prompt": "x", "init_image": ""}):
        try:
            cc.build_img2img(**kw)
        except cc.ComfyError:
            pass
        else:
            raise AssertionError("prompt ว่าง/ไม่มีรูปต้นฉบับควร raise: %r" % (kw,))


def test_comfy_img2img_validation():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        init = os.path.join(td, "init.png")
        Image.new("RGB", (64, 48)).save(init)
        for bad in (0, 1, 1.5, -0.2, "x"):
            try:
                generate.comfy_img2img(init, "p", strength=bad)
            except ValueError as e:
                assert "strength" in str(e), e
            else:
                raise AssertionError("strength %r ควร raise" % (bad,))
        try:
            generate.comfy_img2img(os.path.join(td, "no.png"), "p")
        except FileNotFoundError:
            pass
        else:
            raise AssertionError("ไม่มีรูปต้นฉบับควร raise")
        try:
            generate.comfy_img2img(init, "p", mask=os.path.join(td, "no.png"))
        except FileNotFoundError as e:
            assert "มาสก์" in str(e), e
        else:
            raise AssertionError("ไม่มีมาสก์ควร raise")
        try:
            generate.comfy_img2img(init, "p", width=100)
        except ValueError as e:
            assert "width/height" in str(e), e
        else:
            raise AssertionError("width ข้างเดียวควร raise")


def test_comfy_img2img_wired():
    import tempfile
    seen = {}
    real = (cc.upload_image, cc.queue_prompt, cc.wait_result, cc.fetch_images)
    real_e = cc.ensure_server
    try:
        cc.ensure_server = lambda **kw: True
        cc.upload_image = lambda p, timeout=120: (seen.setdefault("up", []).append(p), "srv.png")[1]
        cc.queue_prompt = lambda wf: (seen.update(wf=wf), "pid")[1]
        cc.wait_result = lambda pid, **kw: {}
        cc.fetch_images = lambda o: [png_bytes(32, 24)]
        with tempfile.TemporaryDirectory() as td:
            init = os.path.join(td, "init.png")
            Image.new("RGB", (64, 48)).save(init)
            mask = os.path.join(td, "m.png")
            Image.new("L", (64, 48), 255).save(mask)
            img, seed = generate.comfy_img2img(init, "a cat", strength=0.5, steps=2,
                                               size=256, seed=9, ckpt="sd15", mask=mask)
    finally:
        cc.upload_image, cc.queue_prompt, cc.wait_result, cc.fetch_images = real
        cc.ensure_server = real_e
    assert img.size == (32, 24) and seed == 9
    assert len(seen["up"]) == 2
    assert seen["wf"]["11"]["inputs"]["image"] == "srv.png"
    assert seen["wf"]["13"]["inputs"]["image"] == "srv.png"
    assert seen["wf"]["12"]["class_type"] == "VAEEncodeForInpaint"
    assert seen["wf"]["3"]["inputs"]["denoise"] == 0.5


def _down_open(req, timeout=None):
    raise urllib.error.URLError("refused")


def test_ensure_server_healthy_no_launch():
    import subprocess
    real_open, real_popen = cc._open, subprocess.Popen
    try:
        cc._open = lambda req, timeout=None: FakeResp(b'{"devices": []}')
        subprocess.Popen = lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("server ติดอยู่แล้วต้องไม่สตาร์ท"))
        assert cc.ensure_server() is True
    finally:
        cc._open, subprocess.Popen = real_open, real_popen


def test_ensure_server_starts_wsl_then_healthy():
    import shutil
    import subprocess
    real_open, real_popen, real_which = cc._open, subprocess.Popen, shutil.which
    calls = []
    state = {"up": False}

    def fake_open(req, timeout=None):
        if state["up"]:
            return FakeResp(b'{"devices": []}')
        raise urllib.error.URLError("refused")

    def fake_popen(*a, **k):
        calls.append(a[0])
        state["up"] = True
        return None

    cc._open = fake_open
    subprocess.Popen = fake_popen
    shutil.which = lambda c: "C:\\Windows\\System32\\wsl.exe"
    try:
        assert cc.ensure_server(timeout=30, poll=0.01) is True
    finally:
        cc._open, subprocess.Popen, shutil.which = real_open, real_popen, real_which
    assert calls and calls[0][:4] == ["wsl", "-e", "bash", "-lc"], calls
    assert "start-comfy" in calls[0][4], calls


def test_ensure_server_remote_url_manual():
    import shutil
    real_open, real_which = cc._open, shutil.which
    launched = []
    cc._open = _down_open
    shutil.which = lambda c: (launched.append(c), "wsl")[1]
    try:
        with mock.patch.dict(os.environ, {cc.SERVER_ENV: "http://192.168.1.51:8188"}):
            try:
                cc.ensure_server(timeout=5, poll=0.01)
            except cc.ComfyError as e:
                assert "192.168.1.51" in str(e), e
            else:
                raise AssertionError("URL อื่นควรให้เปิด server เอง ไม่สตาร์ท wsl")
    finally:
        cc._open, shutil.which = real_open, real_which
    assert launched == []


def test_ensure_server_no_wsl():
    import shutil
    real_open, real_which = cc._open, shutil.which
    cc._open = _down_open
    shutil.which = lambda c: None
    try:
        cc.ensure_server(timeout=5, poll=0.01)
    except cc.ComfyError as e:
        assert "wsl" in str(e).lower(), e
    else:
        raise AssertionError("ไม่มี wsl ควร raise")
    finally:
        cc._open, shutil.which = real_open, real_which


def test_ensure_server_timeout_and_cancel():
    import shutil
    import subprocess
    real_open, real_popen, real_which = cc._open, subprocess.Popen, shutil.which
    cc._open = _down_open
    subprocess.Popen = lambda *a, **k: None
    shutil.which = lambda c: "wsl"
    try:
        try:
            cc.ensure_server(timeout=0.05, poll=0.01)
        except cc.ComfyError as e:
            assert "ไม่ติด" in str(e), e
        else:
            raise AssertionError("หมดเวลาควร raise")
        ev = threading.Event()
        ev.set()
        try:
            cc.ensure_server(timeout=30, poll=0.01, cancel_event=ev)
        except GenerationCancelled:
            pass
        else:
            raise AssertionError("cancel ควร raise GenerationCancelled")
    finally:
        cc._open, subprocess.Popen, shutil.which = real_open, real_popen, real_which


def test_comfy_txt2img_random_seed():
    real_q, real_w, real_f = cc.queue_prompt, cc.wait_result, cc.fetch_images
    real_e = cc.ensure_server
    try:
        cc.ensure_server = lambda **kw: True
        cc.queue_prompt = lambda wf: "pid"
        cc.wait_result = lambda pid, **kw: {}
        cc.fetch_images = lambda o: [png_bytes()]
        _, s1 = generate.comfy_txt2img("a cat", ckpt="sd15")
        _, s2 = generate.comfy_txt2img("a cat", ckpt="sd15")
    finally:
        cc.queue_prompt, cc.wait_result, cc.fetch_images = real_q, real_w, real_f
        cc.ensure_server = real_e
    assert 0 <= s1 <= 2**31 - 1 and 0 <= s2 <= 2**31 - 1


# ---------- build_wan22_i2v (dual-expert 14B) ----------

def test_build_wan22_i2v_structure():
    wf = cc.build_wan22_i2v("a girl waving", seed=5, steps=20, width=832,
                            height=480, length=49, fps=16, init_image="init.png")
    assert wf["10"]["class_type"] == "UNETLoader"
    assert wf["10"]["inputs"]["unet_name"] == cc.WAN22_I2V_HIGH
    assert wf["13"]["inputs"]["unet_name"] == cc.WAN22_I2V_LOW
    assert wf["20"]["inputs"] == {"clip_name": cc.WAN22_I2V_UMT5, "type": "wan"}
    assert wf["21"]["inputs"] == {"vae_name": cc.WAN22_I2V_VAE}
    assert wf["24"] == {"class_type": "LoadImage", "inputs": {"image": "init.png"}}
    assert wf["26"] == {"class_type": "CLIPVisionLoader",
                        "inputs": {"clip_name": cc.WAN22_I2V_CLIP_VISION}}
    enc = wf["27"]
    assert enc["class_type"] == "CLIPVisionEncode"
    assert enc["inputs"]["clip_vision"] == ["26", 0]
    assert enc["inputs"]["image"] == ["24", 0]
    lat = wf["25"]
    assert lat["class_type"] == "WanImageToVideo"
    assert (lat["inputs"]["width"], lat["inputs"]["height"],
            lat["inputs"]["length"]) == (832, 480, 49)
    assert lat["inputs"]["positive"] == ["22", 0]
    assert lat["inputs"]["negative"] == ["23", 0]
    assert lat["inputs"]["clip_vision_output"] == ["27", 0]
    assert lat["inputs"]["start_image"] == ["24", 0]
    s1, s2 = wf["30"]["inputs"], wf["31"]["inputs"]
    assert (s1["start_at_step"], s1["end_at_step"]) == (0, 10)
    assert s1["return_with_leftover_noise"] == "enable"
    assert s1["add_noise"] == "enable"
    assert (s2["start_at_step"], s2["end_at_step"]) == (10, 20)
    assert s2["return_with_leftover_noise"] == "disable"
    assert s2["add_noise"] == "disable"
    assert s1["latent_image"] == ["25", 2] and s2["latent_image"] == ["30", 0]
    assert s1["positive"] == s2["positive"] == ["25", 0]
    assert s1["negative"] == s2["negative"] == ["25", 1]
    assert wf["22"]["inputs"]["text"] == "a girl waving"
    assert wf["10-shift"]["inputs"]["model"] == ["10", 0]
    assert wf["13-shift"]["inputs"]["model"] == ["13", 0]
    assert wf["30"]["inputs"]["model"] == ["10-shift", 0]
    assert wf["31"]["inputs"]["model"] == ["13-shift", 0]
    assert wf["32"]["class_type"] == "VAEDecode"
    assert wf["32"]["inputs"]["samples"] == ["31", 0]
    assert wf["32"]["inputs"]["vae"] == ["21", 0]
    assert wf["33"]["class_type"] == "VHS_VideoCombine"
    assert wf["33"]["inputs"]["images"] == ["32", 0]
    assert wf["33"]["inputs"]["format"] == "video/h264-mp4"
    assert "vae" not in wf["33"]["inputs"]
    assert "10-lora" not in wf and "13-lora" not in wf


def test_build_wan22_i2v_lora():
    wf = cc.build_wan22_i2v("x", init_image="i.png",
                            lora_high=cc.WAN22_I2V_LORA_HIGH,
                            lora_low=cc.WAN22_I2V_LORA_LOW,
                            lora_strength=0.7)
    assert wf["10-lora"]["class_type"] == "LoraLoaderModelOnly"
    assert wf["10-lora"]["inputs"]["lora_name"] == cc.WAN22_I2V_LORA_HIGH
    assert wf["10-lora"]["inputs"]["strength_model"] == 0.7
    assert wf["10-shift"]["inputs"]["model"] == ["10-lora", 0]
    assert wf["13-shift"]["inputs"]["model"] == ["13-lora", 0]
    assert wf["30"]["inputs"]["model"] == ["10-shift", 0]
    assert wf["31"]["inputs"]["model"] == ["13-shift", 0]


def test_build_wan22_i2v_rejects():
    bad = [lambda: cc.build_wan22_i2v("", init_image="i.png"),
           lambda: cc.build_wan22_i2v("x", init_image=""),
           lambda: cc.build_wan22_i2v("x", init_image="i.png", steps=1),
           lambda: cc.build_wan22_i2v("x", init_image="i.png", split_at=0),
           lambda: cc.build_wan22_i2v("x", init_image="i.png", split_at=20),
           lambda: cc.build_wan22_i2v("x", init_image="i.png",
                                      width=100, height=100)]
    for b in bad:
        try:
            b()
        except cc.ComfyError:
            pass
        else:
            raise AssertionError("args ผิดควร raise ComfyError")


def test_fetch_videos_ok():
    mp4 = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 16
    fake = fake_urlopen_factory([("/view", mp4)])
    with mock.patch("comfy_client._open", fake):
        outs = {"32": {"gifs": [{"filename": "a.mp4", "subfolder": "",
                                 "type": "output"}]}}
        assert cc.fetch_videos(outs) == [mp4]
    assert fake.calls[0].startswith(cc.server_url() + "/view?")


def test_fetch_videos_rejects():
    fake = fake_urlopen_factory([("/view", b"not a video........")])
    with mock.patch("comfy_client._open", fake):
        try:
            cc.fetch_videos({"32": {"gifs": [{"filename": "a.mp4"}]}})
        except cc.ComfyError:
            pass
        else:
            raise AssertionError("ไฟล์ปลอมควร raise")
    try:
        cc.fetch_videos({"32": {}})
    except cc.ComfyError:
        pass
    else:
        raise AssertionError("ไม่มี gifs ควร raise")


def test_check_wan22_i2v_models():
    real = cc.list_models
    try:
        cc.list_models = lambda folder, timeout=30: list(cc.WAN22_I2V_FILES[folder])
        assert cc.check_wan22_i2v_models() is True
        cc.list_models = lambda folder, timeout=30: []
        try:
            cc.check_wan22_i2v_models()
        except cc.ComfyError as e:
            assert "Wan 2.2 14B I2V" in str(e), e
        else:
            raise AssertionError("โมเดลหายควร raise")
    finally:
        cc.list_models = real


def test_comfy_i2v_wired():
    import tempfile
    real = (cc.ensure_server, cc.check_wan22_i2v_models, cc.upload_image,
            cc.build_wan22_i2v, cc.queue_prompt, cc.wait_result, cc.fetch_videos)
    seen = {}
    try:
        cc.ensure_server = lambda **kw: True
        cc.check_wan22_i2v_models = lambda **kw: True
        cc.upload_image = lambda p, **kw: "up.png"

        def fake_build(prompt, **kw):
            seen.update(kw)
            seen["prompt"] = prompt
            assert kw["init_image"] == "up.png"
            return {"32": {}}

        cc.build_wan22_i2v = fake_build
        cc.queue_prompt = lambda wf: "pid9"
        cc.wait_result = lambda pid, **kw: {"32": {}}
        cc.fetch_videos = lambda o: [b"\x00\x00\x00\x18ftypisom" + b"\x00" * 16]
        with tempfile.TemporaryDirectory() as td:
            init = os.path.join(td, "in.png")
            Image.new("RGB", (64, 48), "blue").save(init)
            out = os.path.join(td, "v.mp4")
            path, seed = generate.comfy_i2v(init, "a girl waving",
                                            seed=3, output=out)
            assert path == os.path.abspath(out) and os.path.isfile(out)
            assert seed == 3 and seen["width"] % 16 == 0
            assert seen["prompt"] == "a girl waving"
    finally:
        (cc.ensure_server, cc.check_wan22_i2v_models, cc.upload_image,
         cc.build_wan22_i2v, cc.queue_prompt, cc.wait_result,
         cc.fetch_videos) = real


def test_comfy_i2v_rejects():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        init = os.path.join(td, "in.png")
        Image.new("RGB", (16, 16)).save(init)
        cases = [{"model": "wan22-5b"},
                 {"frames": 0}, {"fps": 0},
                 {"output": os.path.join(td, "x.txt")}]
        for kw in cases:
            try:
                generate.comfy_i2v(init, "x", **kw)
            except (ValueError, FileNotFoundError):
                pass
            else:
                raise AssertionError("ควร raise: %r" % (kw,))


ALL = [test_server_url_default, test_server_url_env_and_slash,
       test_build_injects_params, test_build_lora_rewires,
       test_build_empty_prompt_rejected, test_build_raw_ckpt_passthrough,
       test_queue_ok, test_queue_sends_workflow_body,
       test_queue_validation_error, test_queue_node_errors_named,
       test_queue_http_error_thai, test_queue_unreachable_thai,
       test_wait_polls_until_outputs, test_wait_exec_error,
       test_wait_timeout, test_wait_cancel_interrupts,
       test_fetch_images_ok, test_fetch_images_rejects_non_image,
       test_fetch_images_empty_outputs, test_build_comfy_prefix_ckpt,
       test_resolve_comfy_lora, test_check_lora_on_server_ok_and_missing,
       test_comfy_txt2img_rejects_unresolvable_lora, test_comfy_txt2img_lora_wired,
       test_upload_image_ok_and_errors, test_upload_image_server_rejects,
       test_build_img2img_plain_and_mask, test_build_img2img_rejects,
       test_comfy_img2img_validation, test_comfy_img2img_wired,
       test_ensure_server_healthy_no_launch, test_ensure_server_starts_wsl_then_healthy,
       test_ensure_server_remote_url_manual, test_ensure_server_no_wsl,
       test_ensure_server_timeout_and_cancel,
       test_comfy_txt2img_wired, test_comfy_txt2img_random_seed,
       test_build_wan22_i2v_structure, test_build_wan22_i2v_lora,
       test_build_wan22_i2v_rejects, test_fetch_videos_ok,
       test_fetch_videos_rejects, test_check_wan22_i2v_models,
       test_comfy_i2v_wired, test_comfy_i2v_rejects]


if __name__ == "__main__":
    for t in ALL:
        t()
        print("PASS", t.__name__)
    print("comfy tests OK (%d)" % len(ALL))
