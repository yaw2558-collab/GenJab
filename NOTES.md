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

## เทรน LoRA Anima (2 พ.ย. 2026 — สำรวจแล้ว ไปทำต่อเครื่องบ้าน RX 9060 XT)
- **ฟอร์แมตที่ GenJab/sd-cli อ่านได้**: LoRA anima 4 ตัวใน Amuse `LoraAdapter` ใช้ชื่อ tensor
  แบบ ComfyUI `diffusion_model.blocks.N.<layer>.lora_A/lora_B.weight` (metadata `format: pt`)
  — `lora_family()` ใน `generate.py` จับคำ `adaln_modulation_cross_attn`/`llm_adapter` เป็น anima
  ไฟล์ที่เทรนเสร็จต้องแปลงให้เป็นแบบนี้ แล้ววางใน `GenJab\loras\` (ยังไม่มีโฟลเดอร์ ต้องสร้าง)
- **เครื่องมือ**: kohya sd-scripts >= v0.10.1 — `anima_train_network.py` +
  `--network_module networks.lora_anima` มีสคริปต์แปลงเป็น ComfyUI มาด้วย
  (diffusion-pipe ตัวหลักยังไม่รองรับ มีแต่ fork `bluvoll/diffusion-pipe`)
- **ข้อขัดกัน**: เรื่อง LLM adapter — บางที่บอกต้อง `train_llm_adapter=True`
  บางที่บอก `--llm_adapter_lr 0` เพื่อแช่ไว้ → เช็กเอกสาร sd-scripts ล่าสุดก่อนตั้งค่า
- **AMD**: AMD PyTorch on Windows 7.2 (ROCm 7.2, ม.ค. 2026) รองรับ RX 9060 XT บน Win11
  แต่ AMD เตือนเรื่องค้าง/driver timeout — ถ้าไม่นิ่งใช้ WSL2 + ROCm แทน; transformers >= 4.55.5
- **แผน**: (1) เช็กไดรเวอร์ + ติดตั้ง PyTorch ROCm แล้ว `torch.cuda.is_available()`
  (2) dataset 20–50 รูป + caption `.txt` แท็กสไตล์ booru
  (3) ลองเทรนสั้น ~100 steps ดูว่าไม่ล่ม แล้วค่อยจริง ~1500–3000 steps
  (rank 16–32, 1024px, bf16 + gradient checkpointing น่าจะพอ VRAM 16GB)
  (4) แปลงเป็น ComfyUI → ตรวจชื่อ tensor ให้ตรงกับ 4 ตัวเดิม → วาง `loras/` → ลองใน GenJab แรง 0.6–1.0
- ยังไม่ได้ตัดสินใจว่าจะเทรนอะไร (ตัวละคร/หน้าคน/สไตล์)

### ความคืบหน้า (2 พ.ย. 2026 เครื่องบ้าน)
- **ข้อ (1) ผ่านแล้ว** — ใช้ env WSL เดิม `~/flux-lora-train/.venv` (torch 2.14.0+rocm10.1,
  `cuda_available: True` RX 9060 XT) ไม่ต้องลง PyTorch บน Windows; sd-scripts ใน WSL เป็น
  **v0.12.0** มี `anima_train_network.py` + `networks/lora_anima.py` + `convert_anima_lora_to_comfy.py`
- **ข้อขัดกันเรื่อง LLM adapter — จบ**: เอกสาร v0.12.0 บอก LoRA ไม่แตะ adapter เป็นค่าเริ่ม
  (`train_llm_adapter=False`); เปิดด้วย `--network_args "train_llm_adapter=True"` ได้ (แนะนำ lr
  adapter ต่ำ ~5e-5) ส่วน `--llm_adapter_lr` ใช้กับ full fine-tune เท่านั้น
- **ไฟล์โมเดล**: DiT `Amuse\Models\Diffusion\anima-base-v1.0.safetensors` ใช้ตรงได้ (prefix `net.`
  รองรับ, 28 blocks, bf16, มี `llm_adapter.*` ในตัว ไม่ต้องแยก) · VAE ใช้
  `~/ComfyUI/models/vae/qwen_image_vae.safetensors` · **ขาด Qwen3-0.6B แบบ safetensors**
  (Amuse มีแต่ GGUF ใช้เทรนไม่ได้) → โหลด `split_files/text_encoders/qwen_3_06b_base.safetensors`
  จาก HF `circlestone-labs/Anima` ไปไว้ `~/flux-lora-train/models/`
- **dataset**: ใช้ชุด ganjad เดิม `~/dataset/mychar` (110 รูป + แท็ก WD14 แบบ booru เข้ากับ Anima)
- **สคริปต์ใหม่** ใน WSL `~/flux-lora-train/kohya/`: `dataset-ganjad-anima.toml` (repeats 3, bucket
  512–1536), `train_anima_ganjad.sh test|full` (dim 32, adafactor lr 1e-4, sigmoid, bf16,
  `--qwen_image_vae_2d`, cache latents+TE ลงดิสก์; full = 8 epochs = 2640 steps),
  `convert_anima_ganjad.sh` (แปลงเป็น ComfyUI แล้วก๊อปเข้า `GenJab\loras\anima-*.safetensors`)
  — `GenJab\loras\` มีอยู่แล้ว (มี LoRA flux/sdxl)
- โหลด `qwen_3_06b_base.safetensors` (1.19GB) ไว้ `~/flux-lora-train/models/` แล้ว
- **เทสรอบแรกล่มก่อน step 1**: cache latents + TE ครบ 110/110 แล้ว (`*_anima.npz`,
  `*_anima_te.npz`) แต่ torch เรียก Triton (`bmm_outer_product`) แล้ว gcc คอมไพล์ `hip_utils.c`
  ไม่ผ่าน — `fatal error: Python.h` → ต้อง `sudo apt install -y python3.14-dev` ใน WSL
  (venv เป็น Python 3.14) log อยู่ `kohya/train-anima-test.log`
  — แก้แล้ว: `sudo apt update && sudo apt install -y python3.14-dev` (ไม่ update ก่อนจะ 404 ที่ zlib1g-dev)
- **เทส 100 steps ผ่าน**: 3.43 วิ/step, avr_loss ~0.077 ไม่มี NaN, ได้ไฟล์ 88MB
  `~/flux-lora-train/output-anima-test/ganjad-style-anima.safetensors`
- **แปลง ComfyUI ตรวจแล้ว**: ชื่อ tensor แบบเดียวกับของ Amuse (`diffusion_model.blocks.N.<layer>.lora_A/B`
  + `.alpha`) แต่ไม่มีชั้น `adaln_modulation_*` (sd-scripts ไม่เทรนเป็นค่าเริ่ม) →
  `lora_family()` เดิมจับไม่ได้ (คืน None) — เพิ่มให้จับ `mlp.layer1` ด้วยแล้ว + เทสใน `test_generate.py`
  (ganjad SDXL ยังคืน None เพราะเทรน UNet อย่างเดียว ไม่มี `lora_te2_` — เรื่องเดิม)
- **เทรนจริงเริ่มแล้ว** (2 พ.ย. ~13:30): `nohup ... train_anima_ganjad.sh full` 2640 steps ≈ 2.5 ชม.
  log `~/flux-lora-train/kohya/train-anima-ganjad.log` ผล `~/flux-lora-train/output-anima-ganjad/`
  (epoch 2/4/6 + ตัวจบ)
- **เทรนจบแล้ว** (15:52): 2640 steps ใน 2:22 ชม. (3.23 วิ/step), avr_loss 0.077 ไม่มี NaN
- **แปลงเข้า GenJab แล้ว**: `loras\anima-ganjad-style-anima{,-000002,-000004,-000006}.safetensors`
  `lora_family()` = anima ทั้ง 4 ตัว (ใช้กับ anima-* ได้ / SDXL ถูกกัน)
- **เจนจริงผ่าน** (CLI, anima-base 1024px 20 steps CFG 6 seed 42, ~1 นาที 10 วิ/รูป):
  `out/anima-lora-test/no-lora.png` เทียบ `lora-final-0.8.png` — LoRA ออกผลชัด
  (เงาแบบ cel แบนลง เส้นหนาขึ้น โทนผิวเปลี่ยน มีของจาก dataset เช่นสายรัดข้อมือ)
- **ถัดไป (ถ้าจะปรับ)**: เทียบ epoch 2/4/6/ตัวจบ และแรง 0.6–1.0 ว่าตัวไหนสไตล์ติดดีสุดโดยไม่ overfit
  ต้องเปิด GenJab ใหม่ dropdown ถึงจะเห็น LoRA ใหม่ → ถ้า loss ไม่ NaN รัน full
  → convert → ลองใน GenJab โมเดล anima-base แรง 0.6–1.0 prompt ขึ้นต้น `ganjad style,`

## Z-Image-Turbo in GenJab (9 พ.ย. 2026, เครื่อง 8060S)
- sd-cli ของ Amuse (commit 0518b34, 20 ต.ค. 2026) รองรับ Z-Image อยู่แล้ว ไม่ต้องอัปเกรด
- ไฟล์: `models/z_image_turbo-Q4_K.gguf` (~4GB, leejet/Z-Image-Turbo-GGUF) +
  `models/Qwen3-4B-Instruct-2507-Q4_K_M.gguf` (~2.4GB, unsloth) + VAE ยืมของ Amuse
  `AutoEncoder/Flux1/diffusion_pytorch_model.safetensors` (FLUX.1 VAE 160MB)
  (ของ Amuse เองเป็น bf16 sharded ~23GB ใช้บนเครื่องนี้ไม่ได้)
- ต่อเข้า GenJab เป็นโมเดล `zimage-turbo` (steps 8 / 1024px / CFG 1.0):
  วัดจริง 512px 8 steps ~21 วิ (TE 4 + sampling 15 + VAE 1.5) ใช้ VRAM ~6.2GB
- เทสใหม่: test_model_files_zimage_turbo, test_txt2img_zimage_argv (CI --fast),
  test_txt2img_zimage_turbo (backend เจนจริง); gate เขียวทั้ง 3 ไฟล์
