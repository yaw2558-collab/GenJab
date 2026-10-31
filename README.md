# เจนจ๊าบ GenJab

โปรแกรม Windows สำหรับเจนรูปจากข้อความด้วย **SD-Turbo / SDXL-Turbo / Anima Turbo / Anima Base / Anima Aesthetic**
ผ่าน **sd-cli.exe**
(stable-diffusion.cpp + Vulkan — ตัวเดียวกับที่แอป Amuse ใช้)
รันบนการ์ดจอ AMD ได้เลย เบากว่า Amuse ใช้งานออฟไลน์ได้

UI โทนดาร์ก: แผงควบคุมซ้าย (prompt / negative / โมเดล / ขนาด / steps / CFG / seed / จำนวนรูป)
+ จอแสดงรูป + แถบแกลเลอรีรูปที่เคยเจนด้านล่าง (กดดูย้อนหลังได้)
+ โหมด "แปลงรูป" (ปุ่มเจนรูป/แปลงรูปบนแผงซ้าย): เลือกรูปต้นฉบับ + สไตล์เทศกาล (สงกรานต์/ลอยกระทง/งานวัด/Diwali/Holi/คาร์นิวัล) + ความแรงแปลงรูป แล้วกดแปลงรูป (ใช้กับโมเดลรูปเท่านั้น) + ติ๊ก "คงหน้าเดิม" ได้ถ้าใช้โมเดล SDXL-Turbo/Base (ใช้ IP-Adapter คงใบหน้าจากรูปต้นฉบับ)
+ ปุ่ม "ทำภาพขยับได้" ท้ายแผงแปลงรูป: ใช้โมเดล Wan2.2 5B ทำรูปต้นฉบับเป็นคลิป (เลือกความยาว 1–120 วินาที โปรแกรมเจนทีละท่อนสั้น ๆ แล้วต่อให้เอง ยิ่งยาวยิ่งใช้เวลานาน — พิมพ์ prompt บอกด้วยว่าอยากให้อะไรขยับ)
+ ปุ่ม "ลบรูปนี้" เหนือจอแสดงรูป (ถามยืนยันก่อน ส่งลงถังขยะ กู้คืนได้)
+ ปุ่ม "ส่งไป Flow" ข้างปุ่มลบ: ก๊อปรูปที่โชว์อยู่ไปโฟลเดอร์ `flow/` แล้วเปิด flow.google.com ให้ลากรูปเข้าไปทำวิดีโอต่อ
+ ทุกรูปที่เจนฝังค่าที่ใช้ไว้ในไฟล์ PNG (prompt / negative / โมเดล / ขนาด / steps / CFG / seed / LoRA / ค่าแปลงรูป) — กดรูปในแกลเลอรีแล้วกด **"ใช้ค่ารูปนี้"** ค่าทั้งหมดกลับมาที่แผงซ้าย กดเจนซ้ำได้เลย (ไม่ฝังที่เก็บรูปของเครื่อง; มีบรรทัด `parameters` แบบ A1111 ให้โปรแกรมอื่นอ่านด้วย — รูปที่เจนก่อนมีฟีเจอร์นี้ไม่มีค่าให้ดึง)
+ ปุ่ม **"ขยายรูป"**: ขยายรูปที่โชว์อยู่ด้วย ESRGAN (ผ่าน `sd-cli -M upscale`) เซฟเป็น `ชื่อเดิม_up.png` ไม่ทับของเดิม — ต้องมีโมเดลใน `models/upscale/` (ดูด้านล่าง)
+ **แก้เฉพาะจุด (inpaint)** ในโหมดแปลงรูป: กด "ระบาย..." แล้วระบายส่วนที่อยากเจนใหม่ (คลิกซ้าย = ระบาย, คลิกขวา = ลบ, ปรับขนาดแปรง / ล้าง / กลับด้านได้) กด "ใช้มาสก์นี้" แล้วกดแปลงรูป — ส่วนที่ไม่ได้ระบายคงเดิม (ความแรง ~0.8 จะเห็นการเปลี่ยนชัด) เปลี่ยนรูปต้นฉบับแล้วมาสก์ล้างให้เอง

## วิธีรัน

ดับเบิลคลิก `dist\GenJab.exe` (บิลด์ไว้ให้แล้ว — ยังต้องมีแอป Amuse + ไฟล์โมเดลในเครื่องนี้อยู่ดี)
หรือดับเบิลคลิก `run.bat` (มันจะเรียก venv ให้เอง แบบไม่มีหน้าต่างดำ — ถ้าเปิดไม่ขึ้นดู `error.log`)

## วิธีบิลด์ exe เอง

```
.venv\Scripts\pip.exe install pyinstaller
.venv\Scripts\pyinstaller.exe --noconfirm --onefile --windowed --name GenJab app.py
```
ไฟล์ออกที่ `dist\GenJab.exe` (`dist/ build/ *.spec` ถูก ignore จาก git แล้ว)

## วิธีทำไฟล์ติดตั้ง (setup.exe)

```
powershell -ExecutionPolicy Bypass -File installer\build.ps1
```

ได้ไฟล์ใน `installer\Output\` (`setup.exe` + ไฟล์ `.bin` รวม ~5GB — ห่อ sd.cpp
runtime + โมเดล SD-Turbo มาด้วย) ก๊อปทั้งโฟลเดอร์ไปติดตั้งเครื่องอื่นได้เลย
ไม่ต้องมี Amuse/Python พร้อมไฟล์ zip ไฟล์เดียว (`installer\GenJab-Setup-*.zip`) สำหรับก๊อปไปเครื่องอื่น
ติดตั้งแบบ per-user ที่ `%LocalAppData%\GenJab` ไม่ต้องสิทธิ์แอดมิน

เงื่อนไขเครื่องที่บิลด์: มี venv, มีแอป Amuse (ยืม `sd-cli.exe` + DLL),
มี `sd_turbo.safetensors` ใน HF cache, และมี
Inno Setup (`winget install JRSoftware.InnoSetup`)

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
- `appcore.py` — ส่วนที่ไม่ใช่หน้าต่าง: เมนู/ค่าเริ่มของแต่ละโมเดล (`MODEL_DEFAULTS`), จำค่า, ชื่อไฟล์, ฝัง/อ่านค่าใน PNG
- `mask_editor.py` — หน้าต่างระบายมาสก์สำหรับ inpaint
- `generate.py` — ตัวเจนรูปทีละหลายรูปได้ (`--count`, โหลดโมเดลครั้งเดียว, seed ต่อกัน) + สัดส่วนแนวตั้ง/แนวนอน (`--ratio 3:4` / `9:16` / `16:9`, หรือ `--width`/`--height`) + แปลงรูปจากไฟล์ (`--init-img in.png --style สงกรานต์ --strength 0.6`, แก้เฉพาะจุดเพิ่ม `--mask mask.png) + คลิปยาว (`--init-img in.png --model wan22-5b --target-secs 10` หรือ `--segments 3`)
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
  — **ใช้ที่ 512px** (เทรนมาที่ 512 — 1024 ได้คนซ้ำ/ตัวเพี้ยน)
- **SDXL ที่วางเอง** (เหมาะกับรูปคนเหมือนจริง): วางไฟล์ SDXL ไฟล์เดี่ยว `.safetensors` ในโฟลเดอร์ `models/sdxl/`
  แล้วเปิดโปรแกรมใหม่ จะขึ้นในเมนูโมเดลเป็น `ชื่อไฟล์ (SDXL)` — ใช้ "คงหน้าเดิม" + LoRA ของ SDXL ได้
  ค่าเริ่มเดาจากชื่อไฟล์: มีคำว่า Lightning/Hyper = 5 steps CFG 1.5, Turbo = 6 steps CFG 2, อื่น ๆ = 25 steps CFG 5
  เช่น `RealVisXL_V5.0_Lightning_fp16.safetensors` (~7GB จาก `SG161222/RealVisXL_V5.0_Lightning`)
  หรือ Juggernaut XL (โหลดเวอร์ชันไฟล์เดี่ยว ไม่ใช่โฟลเดอร์ diffusers)
- โมเดล **Anima Turbo / Base / Aesthetic** (ถ้าเลือกใน GUI): ใช้ไฟล์ในโฟลเดอร์ Amuse
  (`Models\Diffusion\anima-turbo-v1.0.safetensors` + `TextEncoder\Qwen3-0.6B-Q8_0.gguf`
  + `AutoEncoder\QwenImage\...`) — ต้องเคยโหลดโมเดลนี้ในแอป Amuse มาก่อน
- โมเดล **Anima Base** ต้องรัน `python convert_anima_base.py` ครั้งเดียวก่อน
  (แปลงไฟล์ 4 GB ไว้ในโฟลเดอร์ `models/` ซึ่งถูก ignore จาก git แล้ว)
- ตัวเลือก "คงหน้าเดิม" (เฉพาะโมเดล SDXL): ต้องมีไฟล์ในโฟลเดอร์ `models/` 2 ตัว
  (`ip-adapter-plus_sdxl_vit-h.safetensors` 847MB + `clip_vision_h.safetensors` 2.4GB
  โหลดจาก `h94/IP-Adapter`: `sdxl_models/ip-adapter-plus_sdxl_vit-h.safetensors`
  กับ `models/image_encoder/model.safetensors` แล้วเปลี่ยนชื่อเป็น `clip_vision_h.safetensors`
  — ระวังอย่าโหลด encoder ในโฟลเดอร์ `sdxl_models` เพราะเป็น ViT-bigG ใช้ไม่ได้)
- ปุ่ม "ทำภาพขยับได้": ต้องมีไฟล์ Wan2.2 ในโฟลเดอร์ `models/` 3 ตัว (~12GB):
  `Wan2.2-TI2V-5B-Q8_0.gguf` (จาก `QuantStack/Wan2.2-TI2V-5B-GGUF`) +
  `umt5-xxl-encoder-Q8_0.gguf` (จาก `city96/umt5-xxl-encoder-gguf`) +
  `wan2.2_vae.safetensors` (จาก `QuantStack/Wan2.2-TI2V-5B-GGUF` โฟลเดอร์ `VAE/`)
- คลิปยาวเกิน 1 ท่อน (เลือกความยาว > 1 วินาที): ต้องมี `ffmpeg.exe`
  (วางไว้ข้างโปรแกรม หรือตั้ง path ผ่าน env `GENJAB_FFMPEG` — ใช้ดึงเฟรมท้ายท่อน + ต่อคลิป)

- ปุ่ม "ขยายรูป": ต้องมีโมเดล ESRGAN (`.pth` / `.safetensors`) ในโฟลเดอร์ `models/upscale/`
  (เลือกตัวที่ใช้จากเมนูข้างปุ่ม — โปรแกรมจำตัวที่เลือกไว้) จาก https://github.com/xinntao/Real-ESRGAN/releases:
  `RealESRGAN_x4plus.pth` (~64MB, v0.1.0) สำหรับรูปเหมือนจริง ~3 วิ/รูป
  และ `RealESRGAN_x4plus_anime_6B.pth` (~17MB, v0.2.2.4) สำหรับรูปการ์ตูน/อนิเมะ ~1.3 วิ/รูป (ขยาย 4 เท่า)
  — เปลี่ยน path ได้ผ่าน env `TEXT2IMAGE_UPSCALER` (ไฟล์ `.onnx` ในโฟลเดอร์ Upscale ของ Amuse ใช้กับ sd-cli ไม่ได้)

## หมายเหตุ

- SD-Turbo ใช้ steps แค่ 1–8 (default 4) กับ CFG 1.0 — เพิ่ม steps ไม่ได้รูปดีขึ้นแบบ SD ปกติ
- GUI เลือกขนาดรูปได้ (ตัวเลข = ด้านยาว, SD-Turbo สูงสุด 1024 / Anima Turbo สูงสุด 1344) + สัดส่วน 1:1 จัตุรัส / 3:4 แนวตั้ง / 9:16 แนวตั้งมือถือ / 16:9 แนวนอน (เช่น 512 + 3:4 = 384x512) + ช่อง negative prompt (ต้องดัน CFG > 1 ถึงมีผล เพราะ CFG 1.0 ปิด guidance)
- ไฟล์ `lens_turbo` / `ernie-image-turbo` ในโฟลเดอร์ Amuse เป็นฟอร์แมตเฉพาะของ Amuse — `sd-cli.exe` ตัวที่ยืมมาอ่านไม่ออก (ลองแล้ว) เลยยังต่อเข้าโปรเจกต์ไม่ได้ ต้องเจนสองตัวนั้นในแอป Amuse โดยตรง
- LoRA: เลือกใน GUI ได้ (รายชื่อจากโฟลเดอร์ Amuse `LoraAdapter` + `loras/`) หรือ CLI `--lora anima-turbo-lora-v0.2 --lora-strength 0.8` — **LoRA ต้องตรงสถาปัตยกรรมโมเดล** (เช่น `anima-*` ใช้กับ Anima เท่านั้น) — โปรแกรมดูตระกูลจากข้างในไฟล์ LoRA: เปลี่ยนโมเดลแล้ว LoRA ไม่ตรงรุ่นถูกเอาออกให้ และกดเจนด้วย LoRA ผิดรุ่นจะขึ้นเตือน
- แถบ "การใช้งานเครื่อง" ใต้ปุ่มเจนรูปแสดง CPU / GPU / RAM อัปเดตทุก 2 วินาที (GPU รวม VRAM ที่ใช้อยู่ — อ่านผ่าน Windows Performance Counter ไม่ต้องลงอะไรเพิ่ม ถ้าอ่านไม่ได้ขึ้น — แผงซ้ายเลื่อนดูได้ถ้าจอเล็ก)
- พิมพ์ prompt ภาษาอังกฤษจะได้รูปตรงกว่า
- โหมดแปลงรูป: strength น้อย = คงรูปเดิมมาก (แนะนำ 0.4–0.7) + ขนาดผลลัพธ์ย่อจากรูปต้นฉบับให้ด้านยาวเท่าที่เลือก (ปุ่มจำนวนรูปใช้ได้เหมือนโหมดเจนรูป)
- โปรแกรมจำพรอมล่าสุด + การตั้งค่าทั้งหมด (เก็บใน `settings.json`) — เปิดใหม่ได้ค่าเดิมทุกช่อง
- ประวัติ: เดิมใช้ diffusers + torch-directml แต่พังบนเครื่องนี้
  (fp32 512px OOM / fp16 ค้าง) เลยย้ายมา sd.cpp ตามที่ user เสนอให้ดูโมเดล Amuse
