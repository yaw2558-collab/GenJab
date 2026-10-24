# บันทึกงาน GenJab (เซสชัน 19 ต.ค. 2026)

## ฟีเจอร์ที่เพิ่ม
- **สัดส่วนรูป**: 1:1 / 3:4 / 9:16 แนวตั้ง / 16:9 แนวนอน (`resolve_size()` ใน `generate.py`
  ปัดด้านสั้นขึ้นให้ลงตัวกับ 64 ตรงกับที่ sd-cli ปัดให้) — CLI `--ratio`, GUI ปุ่มสัดส่วน
- **โมเดล SDXL-Turbo**: ขึ้นเมนูแล้ว ไฟล์ `models/sd_xl_turbo_1.0_fp16.safetensors` (6.9GB)
  โหลดไว้แล้ว เจนจริงผ่าน (steps 4 / CFG 1.0)
- **LoRA**: เลือกใน GUI + แถบความแรง, CLI `--lora/--lora-strength` ใช้แท็ก
  `<lora:ชื่อ:แรง>` + `--lora-model-dir` — **ต้องตรงสถาปัตยกรรมโมเดล** (เช่น `anima-*`)
  ในเครื่องมี 5 ตัว (rl, turbo-lora, rutkowski-style, highres-aesthetic-boost, CyberpunkZ)
- **แถบ CPU/GPU/RAM** (`sysmon.py`, ไม่ต้องลงไลบรารีเพิ่ม): อ่านผ่าน Windows PDH +
  ขนาด VRAM จาก DXGI (เจอ RX 9060 XT 16GB) อัปเดตทุก 2 วิ — อยู่แผงซ้ายใต้ปุ่มเจนรูป
  แผงซ้ายเป็นแบบเลื่อนได้แล้ว
- **รูปใหญ่เต็มจอ**: `display()` ย่อตามขนาดจอจริง (เลิกกล่อง 560px) + ปรับตามเมื่อย่อ/ขยายหน้าต่าง
- **ที่เก็บรูป**: กลับไป `out/`; พิมพ์/วาง path เองได้ช่อง "ใช้" (เลี่ยงหน้าต่างเลือกโฟลเดอร์ที่ช้า)
  — หน้าต่างเลือกโฟลเดอร์ผูก `parent` ไว้ไม่หล่นไปข้างหลังแล้ว
- **แก้ค้าง**: โหลดแกลเลอรี (สูงสุด 40 รูป) ย้ายไป worker thread ทั้งหมด เธรดห้ามเรียก Tk
  โดยตรง (เคยพัง `main thread is not in main loop`) ใช้ poller ฝั่งเธรดหลักเก็บผลไปวาด

## ผลสืบสวน (ยังทำไม่ได้ / ตัดสินใจแล้ว)
- `lens_turbo` (Microsoft Lens) กับ `ernie-image-turbo` (ตระกูล Wan) เป็นฟอร์แมตเฉพาะ Amuse —
  `sd-cli.exe` ที่ยืมมาอ่านไม่ออก (ลองรันจริงแล้ว) ต้องเจนในแอป Amuse โดยตรง ไม่ใส่เมนูหลอก
- เจน 4 ได้ไฟล์ครบ 4 ไฟล์เสมอ (ตรวจใน `out/` แล้ว) — ที่เห็นรูปเดียวเพราะจอใหญ่โชว์ทีละรูป
  อีกรูปอยู่ในแถบแกลเลอรี

## NAS (192.168.1.51, user `weerayuth`)
- Shares: `Backup`, `personal_folder` — รูปเจนใหม่ชี้ไป `\\192.168.1.51\personal_folder\genjab`
- ย้ายของเก่า: `robocopy C:\Users\yaw25\GenJab\out \\192.168.1.51\personal_folder\genjab /E`

## Git
- คอมมิต `ab6639a` (สัดส่วน + SDXL-Turbo) push ขึ้น
  [GenJab](https://github.com/yaw2558-collab/GenJab) สาขา `main` แล้ว
- หมายเหตุ: `gh auth login` รอบแรก token ใช้ไม่ได้ (Credential Manager เซฟไม่ติด)
  ต้องล็อกอินแบบ `--insecure-storage`

## Checkpoint Qwen 2.1 (21 ต.ค. 2026 — ค้างไว้ ทำต่อเครื่องบ้าน)
- **ไฟล์ใหม่ใน Amuse** (`%LOCALAPPDATA%\Amuse\Models`, โหลด 21 ต.ค.):
  `Diffusion\qwen_image_2.1_bf16.safetensors` (14.2GB) +
  `AutoEncoder\qwen_image_2.1_vae_bf16.safetensors` (675MB) +
  TE `Qwen3VL-8B-Instruct-Q8_0.gguf` (8.7GB) + `mmproj-...` (752MB);
  Boogu (20.6GB) กับชุด LLaDA (~28GB) โหลดกลับมาด้วย (ยังชนกำแพงแรมเดิม)
- **ผลสืบสวน**: อ่าน safetensors header แล้ว diffusion เป็นฟอร์แมต diffusers ดิบ
  (`transformer_blocks.*`/`img_in`, 265 tensors) ไม่ใช่ชื่อแบบ sd.cpp
  (`model.diffusion_model.*` แบบ anima) — ต่อตรงไม่ได้ ต้องแปลงหรือเอาสูตรจากล็อก Amuse;
  VAE ก็สถาปัตย์ใหม่ (`qwen_image_2.1_vae`); `sd-cli` ที่ยืมมาคือ commit `8cd731e`
  (upstream รองรับ 2.1 ตั้งแต่ 20 ก.ย. — leejet/stable-diffusion.cpp)
- **ผลลองบนเครื่องนี้ (แรม 24GB)**: เจนใน Amuse แล้ว**ค้าง**
  (ตอนลองแรมว่างแค่ 8.2GB) — จบข่าวบนเครื่องนี้
- **ทำต่อที่บ้าน (RX 9060 XT + แรม 64GB + มี Amuse)**:
  1) โหลด Qwen 2.1 ใน Amuse แล้วลองเจน 1 รูปเล็ก
  2) ถ้าผ่าน ก๊อปสูตร `-m/--llm/--vae` จาก `StableDiffusionCpp-*.txt`
     ใน `%LOCALAPPDATA%\Amuse\Logs`
  3) ต่อเข้า GenJab (`model_files()` ใน `generate.py` + `MODEL_IDS`/`MODEL_SIZES`
     ใน `app.py` — อาจต้องมีสคริปต์แปลงคล้าย `convert_anima_base.py`)
- LoRA ไม่มีตัวใหม่ (ยัง 4 ตัวเดิมของ anima)

## Qwen 2.1 in GenJab (21 Oct 2026, home machine)
- Amuse test passed: 1024x1024, 30 steps, Flux scheduler, ~8.5 min.
  Diffusion 13.6GB sits in RAM (64GB machine), VRAM ~9.6GB.
- Formula from StableDiffusionCpp-21-10-2026-50341.txt: diffusion
  qwen_image_2.1_bf16 + --llm Qwen3VL-8B-Instruct-Q8_0.gguf
  + --llm_vision mmproj-...gguf + --vae qwen_image_2.1_vae_bf16.
  No conversion needed (Amuse sd-cli is build 0518b34, supports 2.1).
- Gotcha: pass diffusion via --diffusion-model, NOT -m,
  or sd-cli fails with "get sd version from file failed".
- GenJab: new model id qwen21 (generate.py model_files + --llm_vision
  in txt2img/txt2img_batch, CLI --model, app.py menu/sizes/defaults
  steps=30 size=1024 cfg=4.0). New tests test_model_files_qwen21,
  test_txt2img_qwen21, test_model_menu_consistent all pass.
  Real 256px/2-step gen through GenJab verified OK.
