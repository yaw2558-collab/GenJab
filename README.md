# เจนจ๊าบ GenJab

โปรแกรม Windows สำหรับเจนรูปจากข้อความด้วย **SD-Turbo / SDXL-Turbo / Anima Turbo / Anima Base / Anima Aesthetic**
ผ่าน **sd-cli.exe**
(stable-diffusion.cpp + Vulkan — ตัวเดียวกับที่แอป Amuse ใช้)
รันบนการ์ดจอ AMD ได้เลย เบากว่า Amuse ใช้งานออฟไลน์ได้

UI โทนดาร์ก: แผงควบคุมซ้าย (prompt / negative / โมเดล / ขนาด / steps / CFG / seed / จำนวนรูป)
+ จอแสดงรูป + แถบแกลเลอรีรูปที่เคยเจนด้านล่าง (กดดูย้อนหลังได้)
+ ปุ่ม "ลบรูปนี้" เหนือจอแสดงรูป (ถามยืนยันก่อน ส่งลงถังขยะ กู้คืนได้)

## วิธีรัน

ดับเบิลคลิก `dist\GenJab.exe` (บิลด์ไว้ให้แล้ว — ยังต้องมีแอป Amuse + ไฟล์โมเดลในเครื่องนี้อยู่ดี)
หรือดับเบิลคลิก `run.bat` (มันจะเรียก venv ให้เอง)

## วิธีบิลด์ exe เอง

```
.venv\Scripts\pip.exe install pyinstaller
.venv\Scripts\pyinstaller.exe --noconfirm --onefile --windowed --name GenJab app.py
```
ไฟล์ออกที่ `dist\GenJab.exe` (`dist/ build/ *.spec` ถูก ignore จาก git แล้ว)

หรือผ่าน command line:

```
cd GenJab
.venv\Scripts\activate
python app.py
```

แล้วพิมพ์คำบรรยายภาษาอังกฤษ กด "เจนรูป" รูปจะอยู่ในโฟลเดอร์ `out/`
(เปลี่ยนที่เก็บได้ด้วยปุ่ม "เลือก..." หรือวาง path ในช่องแล้วกด "ใช้" — ไม่ต้องรอหน้าต่างเลือกโฟลเดอร์)

## ไฟล์

- `app.py` — หน้าต่างโปรแกรม (CustomTkinter โทนดาร์ก + แกลเลอรี)
- `generate.py` — ตัวเจนรูปทีละหลายรูปได้ (`--count`, โหลดโมเดลครั้งเดียว, seed ต่อกัน) + สัดส่วนแนวตั้ง/แนวนอน (`--ratio 3:4` / `9:16` / `16:9`, หรือ `--width`/`--height`)
- `test_generate.py` — smoke test (`python test_generate.py`)
- `test_app.py` — เทส logic ฝั่งแอป (`python test_app.py`)
- `convert_anima_base.py` — แปลงชื่อ tensor ของ anima-base ให้ sd-cli อ่านได้ (รันครั้งเดียว)
- `requirements.txt` — ไลบรารีที่ใช้ (pillow + customtkinter + send2trash)

## สิ่งที่ต้องมีในเครื่อง

- แอป **Amuse** (ยืม `sd-cli.exe` จาก `%LOCALAPPDATA%\Amuse\RuntimeStableDiffusionCpp\vulkan\`)
  — เปลี่ยน path ได้ผ่าน env `TEXT2IMAGE_SDCLI`
- โมเดล **SD-Turbo** ไฟล์เดียว `sd_turbo.safetensors` ใน HF cache
  (`models--stabilityai--sd-turbo`) — เปลี่ยน path ได้ผ่าน env `TEXT2IMAGE_MODEL`
- โมเดล **SDXL-Turbo** ไฟล์ `sd_xl_turbo_1.0_fp16.safetensors`
  (โหลดจาก `stabilityai/sdxl-turbo` วางในโฟลเดอร์ `models/` — เปลี่ยน path ได้ผ่าน env `TEXT2IMAGE_SDXL_TURBO`)
- โมเดล **Anima Turbo / Base / Aesthetic** (ถ้าเลือกใน GUI): ใช้ไฟล์ในโฟลเดอร์ Amuse
  (`Models\Diffusion\anima-turbo-v1.0.safetensors` + `TextEncoder\Qwen3-0.6B-Q8_0.gguf`
  + `AutoEncoder\QwenImage\...`) — ต้องเคยโหลดโมเดลนี้ในแอป Amuse มาก่อน
- โมเดล **Anima Base** ต้องรัน `python convert_anima_base.py` ครั้งเดียวก่อน
  (แปลงไฟล์ 4 GB ไว้ในโฟลเดอร์ `models/` ซึ่งถูก ignore จาก git แล้ว)

## หมายเหตุ

- SD-Turbo ใช้ steps แค่ 1–8 (default 4) กับ CFG 1.0 — เพิ่ม steps ไม่ได้รูปดีขึ้นแบบ SD ปกติ
- GUI เลือกขนาดรูปได้ (ตัวเลข = ด้านยาว, SD-Turbo สูงสุด 1024 / Anima Turbo สูงสุด 1344) + สัดส่วน 1:1 จัตุรัส / 3:4 แนวตั้ง / 9:16 แนวตั้งมือถือ / 16:9 แนวนอน (เช่น 512 + 3:4 = 384x512) + ช่อง negative prompt (ต้องดัน CFG > 1 ถึงมีผล เพราะ CFG 1.0 ปิด guidance)
- ไฟล์ `lens_turbo` / `ernie-image-turbo` ในโฟลเดอร์ Amuse เป็นฟอร์แมตเฉพาะของ Amuse — `sd-cli.exe` ตัวที่ยืมมาอ่านไม่ออก (ลองแล้ว) เลยยังต่อเข้าโปรเจกต์ไม่ได้ ต้องเจนสองตัวนั้นในแอป Amuse โดยตรง
- LoRA: เลือกใน GUI ได้ (รายชื่อจากโฟลเดอร์ Amuse `LoraAdapter` + `loras/`) หรือ CLI `--lora anima-turbo-lora-v0.2 --lora-strength 0.8` — **LoRA ต้องตรงสถาปัตยกรรมโมเดล** (เช่น `anima-*` ใช้กับ Anima เท่านั้น)
- แถบ "การใช้งานเครื่อง" ใต้ปุ่มเจนรูปแสดง CPU / GPU / RAM อัปเดตทุก 2 วินาที (GPU รวม VRAM ที่ใช้อยู่ — อ่านผ่าน Windows Performance Counter ไม่ต้องลงอะไรเพิ่ม ถ้าอ่านไม่ได้ขึ้น — แผงซ้ายเลื่อนดูได้ถ้าจอเล็ก)
- พิมพ์ prompt ภาษาอังกฤษจะได้รูปตรงกว่า
- ประวัติ: เดิมใช้ diffusers + torch-directml แต่พังบนเครื่องนี้
  (fp32 512px OOM / fp16 ค้าง) เลยย้ายมา sd.cpp ตามที่ user เสนอให้ดูโมเดล Amuse
