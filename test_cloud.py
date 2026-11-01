"""เทส GenJab Cloud แบบไม่ต่อเน็ต (จำลอง urlopen) — python test_cloud.py"""
import base64
import io
import json
import os
import tempfile
import unittest
import urllib.error
from unittest import mock

from PIL import Image

import cloud_core
import cloud_providers as cp


def png_bytes(w=8, h=6, color="red"):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, "PNG")
    return buf.getvalue()


class FakeResp:
    def __init__(self, data, ctype):
        self.data, self.headers = data, {"Content-Type": ctype}

    def read(self):
        return self.data

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class Recorder:
    """จำ request ที่ยิง แล้วตอบตามฟังก์ชันที่ให้."""

    def __init__(self, reply):
        self.reply, self.reqs = reply, []

    def __call__(self, req, timeout=None):
        self.reqs.append(req)
        return self.reply(req)


class ValidationTests(unittest.TestCase):
    def test_empty_prompt(self):
        with self.assertRaises(cp.CloudError):
            cp.generate("pollinations", "   ")

    def test_unknown_provider(self):
        with self.assertRaises(cp.CloudError):
            cp.generate("nope", "cat")

    def test_key_required(self):
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            with self.assertRaises(cp.CloudError) as cm:
                cp.generate("openai", "cat")
        self.assertIn("คีย์", str(cm.exception))

    def test_env_key_used(self):
        with mock.patch.dict(os.environ, {"STABILITY_API_KEY": "envkey"}):
            self.assertEqual(cp.resolve_key("stability"), "envkey")
            self.assertEqual(cp.resolve_key("stability", " typed "), "typed")

    def test_label_roundtrip(self):
        for pid, p in cp.PROVIDERS.items():
            self.assertEqual(cp.label_to_id(p["label"]), pid)


class ProviderTests(unittest.TestCase):
    def test_pollinations(self):
        rec = Recorder(lambda r: FakeResp(png_bytes(), "image/jpeg"))
        with mock.patch("urllib.request.urlopen", rec):
            imgs, seed = cp.generate("pollinations", "a red cat", negative="blurry",
                                     ratio="16:9", seed=42, count=2)
        self.assertEqual(seed, 42)
        self.assertEqual(len(imgs), 2)
        self.assertIn("a%20red%20cat", rec.reqs[0].full_url)
        self.assertIn("width=1024&height=576", rec.reqs[0].full_url)
        self.assertIn("seed=42", rec.reqs[0].full_url)
        self.assertIn("seed=43", rec.reqs[1].full_url)
        self.assertIn("negative_prompt=blurry", rec.reqs[0].full_url)
        self.assertIsNone(rec.reqs[0].get_header("Authorization"))

    def test_random_seed(self):
        rec = Recorder(lambda r: FakeResp(png_bytes(), "image/png"))
        with mock.patch("urllib.request.urlopen", rec):
            _, seed = cp.generate("pollinations", "cat", seed=-1)
        self.assertGreaterEqual(seed, 0)

    def test_openai(self):
        b64 = base64.b64encode(png_bytes()).decode()
        rec = Recorder(lambda r: FakeResp(json.dumps({"data": [{"b64_json": b64}] * 3}).encode(),
                                          "application/json"))
        with mock.patch("urllib.request.urlopen", rec):
            imgs, _ = cp.generate("openai", "cat", ratio="9:16", key="sk-x", count=3, negative="ignored")
        self.assertEqual(len(imgs), 3)
        body = json.loads(rec.reqs[0].data)
        self.assertEqual(body["size"], "1024x1536")
        self.assertEqual(body["n"], 3)
        self.assertEqual(body["model"], "gpt-image-1")
        self.assertEqual(rec.reqs[0].get_header("Authorization"), "Bearer sk-x")

    def test_gemini(self):
        b64 = base64.b64encode(png_bytes()).decode()
        resp = {"candidates": [{"content": {"parts": [{"text": "here"},
                                                      {"inlineData": {"mimeType": "image/png", "data": b64}}]}}]}
        rec = Recorder(lambda r: FakeResp(json.dumps(resp).encode(), "application/json"))
        with mock.patch("urllib.request.urlopen", rec):
            imgs, _ = cp.generate("gemini", "cat", ratio="4:3", key="g", count=2)
        self.assertEqual(len(imgs), 2)
        body = json.loads(rec.reqs[0].data)
        self.assertEqual(body["generationConfig"]["imageConfig"]["aspectRatio"], "4:3")
        self.assertIn("gemini-2.5-flash-image:generateContent", rec.reqs[0].full_url)
        self.assertEqual(rec.reqs[0].get_header("X-goog-api-key"), "g")

    def test_gemini_blocked(self):
        resp = {"promptFeedback": {"blockReason": "SAFETY"}}
        rec = Recorder(lambda r: FakeResp(json.dumps(resp).encode(), "application/json"))
        with mock.patch("urllib.request.urlopen", rec), self.assertRaises(cp.CloudError) as cm:
            cp.generate("gemini", "cat", key="g")
        self.assertIn("SAFETY", str(cm.exception))

    def test_stability(self):
        rec = Recorder(lambda r: FakeResp(png_bytes(), "image/png"))
        with mock.patch("urllib.request.urlopen", rec):
            cp.generate("stability", "cat", negative="ugly", model="sd3.5-large", key="k", seed=7)
        req = rec.reqs[0]
        self.assertTrue(req.full_url.endswith("/generate/sd3"))
        self.assertIn(b'name="model"\r\n\r\nsd3.5-large', req.data)
        self.assertIn(b'name="negative_prompt"\r\n\r\nugly', req.data)
        self.assertIn(b'name="seed"\r\n\r\n7', req.data)
        self.assertTrue(req.get_header("Content-type").startswith("multipart/form-data; boundary="))

    def test_http_error_thai(self):
        def boom(req):
            raise urllib.error.HTTPError(req.full_url, 401, "x", {},
                                         io.BytesIO(b'{"error": {"message": "Invalid key"}}'))
        with mock.patch("urllib.request.urlopen", Recorder(boom)), self.assertRaises(cp.CloudError) as cm:
            cp.generate("openai", "cat", key="bad")
        self.assertIn("คีย์ API ไม่ถูกต้อง", str(cm.exception))
        self.assertIn("Invalid key", str(cm.exception))

    def test_non_image_reply(self):
        rec = Recorder(lambda r: FakeResp(b"<html>oops</html>", "text/html"))
        with mock.patch("urllib.request.urlopen", rec), self.assertRaises(cp.CloudError):
            cp.generate("pollinations", "cat")


class CoreTests(unittest.TestCase):
    def test_save_and_read(self):
        with tempfile.TemporaryDirectory() as d:
            paths = cloud_core.save_images([png_bytes(), png_bytes(color="blue")], d,
                                           {"provider": "openai", "model": "m", "prompt": "cat", "seed": 5})
            self.assertEqual([os.path.basename(p) for p in paths], ["cloud001.png", "cloud002.png"])
            p = cloud_core.read_params(paths[1])
            self.assertEqual(p["prompt"], "cat")
            self.assertEqual(p["seed"], 5)
            self.assertEqual(len(cloud_core.gallery_paths(d)), 2)
            more = cloud_core.save_images([png_bytes()], d, {})
            self.assertEqual(os.path.basename(more[0]), "cloud003.png")

    def test_settings_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, "s.json")
            s = cloud_core.default_settings()
            s.update(provider="gemini", model="x", ratio="9:16", count=9, keys={"gemini": "k", "bogus": "z"})
            cloud_core.save_settings(s, f)
            got = cloud_core.load_settings(f)
            self.assertEqual(got["provider"], "gemini")
            self.assertEqual(got["count"], 4)
            self.assertEqual(got["keys"], {"gemini": "k"})
            self.assertEqual(cloud_core.load_settings(os.path.join(d, "missing.json"))["provider"], "pollinations")

    def test_normalize_garbage(self):
        s = cloud_core.normalize_settings({"provider": "zzz", "ratio": "5:5", "seed": "abc", "count": "x"})
        self.assertEqual(s, cloud_core.default_settings())


if __name__ == "__main__":
    unittest.main(verbosity=1)
