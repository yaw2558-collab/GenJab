# เจนจ๊าบ GenJab

โปรแกรม Windows สำหรับเจนรูปจากข้อความด้วย **SD-Turbo / Anima Turbo** ผ่าน **sd-cli.exe**
(stable-diffusion.cpp + Vulkan — ตัวเดียวกับที่แอป Amuse ใช้)
รันบนการ์ดจอ AMD ได้เลย เบากว่า Amuse ใช้งานออฟไลน์ได้

UI โทนดาร์ก: แผงควบคุมซ้าย (prompt / negative / โมเดล / ขนาด / steps / CFG / seed)
+ จอแสดงรูป + แถบแกลเลอรีรูปที่เคยเจนด้านล่าง (กดดูย้อนหลังได้)
+ ปุ่ม "ลบรูปนี้" เหนือจอแสดงรูป (ถามยืนยันก่อน ส่งลงถังขยะ กู้คืนได้)

## วิธีรัน

ดับเบิลคลิก `run.bat` ในโฟลเดอร์ `text2image/` (มันจะเรียก venv ให้เอง)

หรือผ่าน command line:

```
cd text2image
.venv\Scripts\activate
python app.py
```

แล้วพิมพ์คำบรรยายภาษาอังกฤษ กด "เจนรูป" รูปจะอยู่ในโฟลเดอร์ `out/`

## ไฟล์

- `app.py` — หน้าต่างโปรแกรม (CustomTkinter โทนดาร์ก + แกลเลอรี)
- `generate.py` — ตัวเจนรูป (เรียกจาก command line ก็ได้)
- `test_generate.py` — smoke test (`python test_generate.py`)
- `requirements.txt` — ไลบรารีที่ใช้ (pillow + customtkinter + send2trash)

## สิ่งที่ต้องมีในเครื่อง

- แอป **Amuse** (ยืม `sd-cli.exe` จาก `%LOCALAPPDATA%\Amuse\RuntimeStableDiffusionCpp\vulkan\`)
  — เปลี่ยน path ได้ผ่าน env `TEXT2IMAGE_SDCLI`
- โมเดล **SD-Turbo** ไฟล์เดียว `sd_turbo.safetensors` ใน HF cache
  (`models--stabilityai--sd-turbo`) — เปลี่ยน path ได้ผ่าน env `TEXT2IMAGE_MODEL`
- โมเดล **Anima Turbo** (ถ้าเลือกใน GUI): ใช้ไฟล์ในโฟลเดอร์ Amuse
  (`Models\Diffusion\anima-turbo-v1.0.safetensors` + `TextEncoder\Qwen3-0.6B-Q8_0.gguf`
  + `AutoEncoder\QwenImage\...`) — ต้องเคยโหลดโมเดลนี้ในแอป Amuse มาก่อน

## หมายเหตุ

- SD-Turbo ใช้ steps แค่ 1–8 (default 4) กับ CFG 1.0 — เพิ่ม steps ไม่ได้รูปดีขึ้นแบบ SD ปกติ
- GUI เลือกขนาดรูปได้ (SD-Turbo สูงสุด 1024 / Anima Turbo สูงสุด 1344 — Turbo ที่ 1344 ภาพซ้ำเป็นกระเบื้องเลยไม่เปิดให้) + ช่อง negative prompt (ต้องดัน CFG > 1 ถึงมีผล เพราะ CFG 1.0 ปิด guidance)
- พิมพ์ prompt ภาษาอังกฤษจะได้รูปตรงกว่า
- ประวัติ: เดิมใช้ diffusers + torch-directml แต่พังบนเครื่องนี้
  (fp32 512px OOM / fp16 ค้าง) เลยย้ายมา sd.cpp ตามที่ user เสนอให้ดูโมเดล Amuse
