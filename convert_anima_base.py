"""แปลง anima-base-v1.0.safetensors ของ Amuse (ชื่อ tensor แบบ `net.*`)
ให้ sd-cli อ่านได้ (แบบ `model.diffusion_model.*` เหมือนไฟล์ turbo) — รันครั้งเดียว:

    python convert_anima_base.py

ได้ไฟล์ `models/anima-base-sd.cpp.safetensors` (ค่า weight เหมือนเดิมทุกบิต)."""
import json
import os
import struct

SRC = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Amuse", "Models",
                   "Diffusion", "anima-base-v1.0.safetensors")
DST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models",
                   "anima-base-sd.cpp.safetensors")


def main():
    if not os.path.isfile(SRC):
        raise SystemExit(f"ไม่พบไฟล์ต้นฉบับที่ {SRC} (ต้องลงโมเดลในแอป Amuse ก่อน)")
    os.makedirs(os.path.dirname(DST), exist_ok=True)
    with open(SRC, "rb") as f:
        hlen = struct.unpack("<Q", f.read(8))[0]
        header = json.loads(f.read(hlen))
        fixed = {}
        for k, v in header.items():
            if k == "__metadata__":
                fixed[k] = v
                continue
            assert k.startswith("net."), k
            fixed["model.diffusion_model." + k[4:]] = v
        blob = json.dumps(fixed, separators=(",", ":")).encode()
        with open(DST, "wb") as out:
            out.write(struct.pack("<Q", len(blob)))
            out.write(blob)
            while True:
                chunk = f.read(64 * 1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
    print("saved:", DST)


if __name__ == "__main__":
    main()
