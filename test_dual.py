"""เทส logic backend คู่ (dual_backend + จุดต่อ genjab) — ไม่ต้องเปิด GUI: `python test_dual.py`"""
import json
import os
import tempfile
import unittest

import dual_backend as db


class SwitchTests(unittest.TestCase):
    def test_other_both_ways(self):
        self.assertEqual(db.other(db.LOCAL), db.CLOUD)
        self.assertEqual(db.other(db.CLOUD), db.LOCAL)


class ArgvTests(unittest.TestCase):
    def test_local_flag(self):
        self.assertEqual(db.parse_argv(["--local"]), db.LOCAL)

    def test_cloud_flag(self):
        self.assertEqual(db.parse_argv(["--cloud"]), db.CLOUD)

    def test_backend_equals(self):
        self.assertEqual(db.parse_argv(["--backend", "cloud"]), db.CLOUD)
        self.assertEqual(db.parse_argv(["--backend", "local"]), db.LOCAL)

    def test_backend_case_insensitive(self):
        self.assertEqual(db.parse_argv(["--backend", "Cloud"]), db.CLOUD)

    def test_no_flag(self):
        self.assertIsNone(db.parse_argv([]))
        self.assertIsNone(db.parse_argv(["--fast"]))

    def test_backend_bad_value(self):
        self.assertIsNone(db.parse_argv(["--backend", "zzz"]))
        self.assertIsNone(db.parse_argv(["--backend"]))


class SettingsTests(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "dual.json")
            self.assertTrue(db.save_backend(db.CLOUD, p))
            self.assertEqual(db.load_backend(p), db.CLOUD)
            self.assertTrue(db.save_backend(db.LOCAL, p))
            self.assertEqual(db.load_backend(p), db.LOCAL)

    def test_missing_file_returns_default(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(db.load_backend(os.path.join(d, "nope.json")), db.DEFAULT_BACKEND)

    def test_garbage_returns_default(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "dual.json")
            with open(p, "w", encoding="utf-8") as f:
                f.write("{not json")
            self.assertEqual(db.load_backend(p), db.DEFAULT_BACKEND)
            with open(p, "w", encoding="utf-8") as f:
                json.dump({"backend": "zzz"}, f)
            self.assertEqual(db.load_backend(p), db.DEFAULT_BACKEND)

    def test_save_invalid_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "dual.json")
            self.assertFalse(db.save_backend("zzz", p))
            self.assertFalse(os.path.exists(p))

    def test_save_unwritable_returns_false(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertFalse(db.save_backend(db.LOCAL, os.path.join(d, "no-dir", "dual.json")))


class WiringTests(unittest.TestCase):
    def test_apps_expose_switch(self):
        from app import App
        from cloud_app import CloudApp
        for cls in (App, CloudApp):
            self.assertTrue(callable(getattr(cls, "on_switch_backend", None)), cls.__name__)


if __name__ == "__main__":
    unittest.main(verbosity=1)
