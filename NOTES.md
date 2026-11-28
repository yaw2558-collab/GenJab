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

## เทรน LoRA Anima ชุด bolly (5 พ.ย. 2026 เครื่องบ้าน, WSL)
- **dataset**: `~/dataset/dataset-anime` 56 PNG (รูปเจน AI) + แท็ก WD14 — เติม trigger `bolly, `
  หน้า caption ทุกไฟล์แล้ว (สำรองของเดิมไว้ `~/dataset/dataset-anime-captions-backup/`)
- **สคริปต์** ใน `~/flux-lora-train/kohya/` (ก๊อปจากชุด ganjad): `dataset-bolly-anima.toml` (repeats 4),
  `train_anima_bolly.sh test|full` (full = 10 epochs = 2240 steps), `convert_anima_bolly.sh`
- **ดูความคืบหน้า** (รันใน WSL ไม่ต้องมี `wsl` นำหน้า): `bash kohya/anima_progress.sh [test]` (สรุป)
  / `bash kohya/anima_watch.sh [test]` (สดทุก step, Ctrl+C ออกไม่หยุดเทรน)
- **ผล**: เทส 100 steps ผ่าน (3.22 วิ/step loss 0.075) → full 2240 steps ใน 1:56 ชม. (3.12 วิ/step)
  avr_loss 0.076 ไม่มี NaN → แปลงเข้า `loras\anima-bolly-anima{,-000002,-4,-6,-8}.safetensors`
  `lora_family()` = anima ครบ 5 ตัว
- **เจนจริงผ่าน** (anima-base 3:4 1024 20 steps CFG 6 seed 42, prompt ขึ้นต้น `bolly,` แรง 0.8):
  `out/bolly-lora-test/` no-lora (ลายเส้นวาดมือ) เทียบ epoch 6 / ตัวจบ — LoRA เปลี่ยนเป็นแนว
  เซลฟี่มือถือผิวเนียนกึ่งสมจริงชัด หน้า/ทรงผมคงที่ ตัวจบติดแรงกว่า epoch 6

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

## sd-cli a3c49b1 ใช้กับ GenJab ได้ (10 พ.ย. 2026)
- upstream ออก `master-1079-a3c49b1` (9 พ.ย.) มี `sd-master-a3c49b1-bin-win-vulkan-x64.zip`
  (~30MB); ของ Amuse ในเครื่องยังเป็น `0518b34` (20 ต.ค.)
- โหลดมาไว้ `sdcli-new/bin/` (local only ไม่ commit) ชี้ `TEXT2IMAGE_SDCLI` ไปตัวใหม่แล้วเทส
- แฟล็กที่ GenJab ใช้อยู่ครบทั้ง 20 ตัว (`--diffusion-model`, `--llm`, `--llm_vision`,
  `--vae`, `--clip_l/g`, `--t5xxl`, `--audio-vae`, `--lora-model-dir`, `--offload-to-cpu`,
  `--ip-adapter*`, `--upscale-*`, `--video-frames`, `--flow-shift`, `--sampling-method`,
  `--mask`, `--strength`, `-M vid_gen/upscale`)
- เทสผ่าน: `test_app.py` OK, `test_cloud.py` 24 tests OK, `test_generate.py --fast` OK
- เจนจริงผ่าน: sd-turbo 256px 2 steps seed 42 ~20 วิ ได้รูปปกติไม่ดำ → `out/sdcli-new-test.png`

## ติดตั้ง Z-Image-Turbo + sd-cli a3c49b1 ที่เครื่องบ้าน (11 พ.ย. 2026, RX 9060 XT)
- ก๊อปจาก USB ตาม `CLAUDE-HANDOFF.md`: `sdcli-new/bin/` (23 ไฟล์), 2 gguf ของ zimage-turbo
  (ลง `models/` ซึ่งเป็น junction ไป `I:\ai-models\GenJab-models`), FLUX.1 VAE ลง Amuse `AutoEncoder/Flux1/`
  ขนาดไบต์ตรงทุกไฟล์; ตั้ง user env `TEXT2IMAGE_SDCLI` → `sdcli-new\bin\sd-cli.exe` (`--version` = a3c49b1)
- เทสผ่าน: `test_generate.py --fast` OK, `test_app.py` OK, `test_cloud.py` 24 tests OK
  (แก้ test_app ให้จำลอง NAS เข้าได้/ไม่ได้ เพราะที่บ้านเข้า NAS ได้ เทสเดิมเลยล้ม)
- เจนจริง: zimage-turbo 512px 8 steps CFG 1.0 seed 42 ~25 วิ (รวมโหลด) รูปปกติ → `out/zimage-home-test.png`
- LoRA ganjad 4 ตัว (`anima-ganjad-style-anima{,-000002,-000004,-000006}`) อยู่ครบ `lora_family()` = anima

## LoRA bolly-r5: ตัดแท็กสไตล์ออกจากแคปชัน (11 พ.ย. 2026, เครื่องบ้าน)
- r4 สไตล์ติดน้อย (แรง 1.0 ได้ครึ่งอนิเมะ ต้อง 1.5 ถึงเป็นรูปถ่าย) เพราะแคปชันมี `realistic` (85/101),
  `photorealistic`, `photo background` → สไตล์ไปผูกกับแท็กพวกนี้แทน `bolly`
- r5 = dataset เดิม ลบ 4 แท็กนั้น (170 แท็ก) → `~/dataset/dataset-anime-r5`, ค่าเทรนเหมือน r4 ทุกอย่าง
  (dim 32, lr 1e-4, repeats 3, 8 epochs, 2424 steps ~2 ชม. 12 นาที, loss สุดท้าย 0.124)
- ผล (anima-turbo seed 42): r5 แรง 1.0 เป็นรูปถ่ายเต็มตัว, 0.8 ก็ยังติด → `out/bolly-cmp/r5-grid.png`
- บทเรียน: LoRA สไตล์ อย่าใส่แท็กที่บรรยายสไตล์ในแคปชัน ให้คำ trigger รับสไตล์ไปคำเดียว
- `anima_lora.sh full` ตายตอน `wsl -e` จบ session → ต้องรันแบบมี session ค้าง (เช่น `_run` ใน wsl ที่เปิดอยู่)

## LoRA silvra-fighter: ตัวละครออริจินัลท่าต่อสู้ (27 พ.ย. 2026, เครื่องบ้าน)
- ตัวละคร AI ออกแบบใหม่ (ผมเงินหางม้า ตาแดง ผ้าพันคอแดง ชุดแทคติคอลดำ) — trigger `silvra`
- dataset: เจนด้วย anima-turbo 80 รูป (20 ท่า x 4) คัดเหลือ 68 → `~/dataset/fighter-silver`
  WD14 แท็ก แล้วลบแท็กตัวตน (ผม/ตา/ผ้าพันคอ/ชุด) ให้ trigger รับไป คงแท็กท่า/ฉากไว้
  สคริปต์/ภาพรวม: `out/fighter-silver/` (gen_candidates.ps1, prep_dataset.sh, sheet1-4.png)
- เทรน `anima_lora.sh` ค่าเริ่ม (dim 32, repeats 3, 8 epochs = 1632 steps, 3.3 วิ/step ~90 นาที)
  avr_loss ~0.078 ไม่มี NaN → `loras\anima-silvra-fighter{,-000002,-4,-6}.safetensors`
- Amuse ย้ายไป E: แล้ว → `anima_lora.sh` หา anima-base ที่ `/mnt/e/Amuse/...` ก่อน C: (สำรอง `.bak-20261127`)
- รอบแรกค้าง step 0 (CPU 94% ไม่ขยับ 10 นาที) → kill + `wsl --shutdown` + รันใหม่ผ่าน
- ผล (`out/fighter-silver/test/compare.png`, seed 77, แรง 0.9, prompt มีแค่ trigger+ท่า):
  ตัวจบดีสุด ได้ผมเงิน/ตาแดง/ผ้าพันคอ/ชุดดำครบ; epoch 4 ยังไม่ติด
  ฉากที่มีชุดของตัวเอง (dojo) ยังดึงไปเป็นชุดคาราเต้ → เติม `silver hair, red scarf, black bodysuit` ช่วย

## ทำต่อจาก HANDOFF-AMUSE4 ที่เครื่องบ้าน (28 พ.ย. 2026, RX 9060 XT)
- ซิงก์: stash NOTES (silvra) → `git pull --ff-only` ได้ `91d63d7` → pop; gate เขียว 5 ชุด
- Amuse ที่บ้านเป็น 4.0 แล้ว, โฟลเดอร์โมเดล `I:\Amuse\Models`; Qwen3-4B มีอยู่แล้ว,
  ก๊อป ControlNet ProMax + stable-audio ลง `models\controlnet\`, `models\audio\` (cmp ตรง)
- `join_llada.py` ต้องรันด้วย `python -I -X utf8` (`-I` ไม่สน `PYTHONIOENCODING` → print ไทยพังใน cp1252) — ต่อครบ sha256 ตรง
- USB เสียบพอร์ตช้า ~9MB/s รวม ระหว่างก๊อป ดิสก์ I: แย่งกัน → sd-server โหลด sd-turbo รอบแรก 584 วิ, แปลไทยรอบแรก 72 วิ
- sd-turbo: server = sd-cli ทุกพิกเซล; ภาพระหว่างเจน (ไม่ใช้ server) ได้ 4 ภาพ
  วัดซ้ำตอนดิสก์ว่าง: server warm **0.9 วิ** (amuse/alt — ที่บ้านชี้ `sdcli-1106` ทั้งคู่), rocm 1.4 วิ;
  sd-cli 4.1 / rocm 5.8 วิ; server cold 152 วิ (อ่านโมเดลครั้งแรก) แล้วตัวถัดไป ~4-7 วิ
  → GUI ตั้ง engine `rocm` อยู่ ช้ากว่า Vulkan ~50%
- แปลไทย: "ผมเงิน" → "blonde-haired" (ผิด), "หางม้า" → "horse tail" → แก้ `SYSTEM_PROMPT` (cloud_translate.py ใช้ร่วม
  cloud/local) ใส่ศัพท์สีผม/สีตา/ponytail/twintails ตายตัว → ได้ silver hair / ponytail / pink twintails ถูกหมด
  (แปลรอบแรก ~73 วิ แม้ดิสก์ว่าง = โหลด Qwen3-4B จาก I: — ที่ 8060S ~7 วิ; รอบต่อไป 0.2 วิ)
- **โมเดลใหม่จาก Amuse 2 ตัว**:
  - Anima Light Lavender (`anima-light-lavender.safetensors`, Base cfg 4 / 25 steps ตาม Amuse) —
    tensor เป็น `net.*` แบบ anima-base, sd-cli 4.0 อ่านตรงไม่ได้ → `convert_anima_base.py` รับ id ได้แล้ว
    (`ANIMA_CONVERTED` ใน generate.py) รัน `python convert_anima_base.py anima-lavender` ครั้งเดียว
    → เมนู "Anima Light Lavender" (id `anima-lavender`) 1024px 25 steps 86 วิ ผลดี
  - Animagine XL 4.0 Opt = SDXL → hard link เข้า `models\sdxl\` (I: เดียวกัน ไม่เปลืองที่)
    ขึ้นเมนูเป็น `animagine-xl-4.0-opt (SDXL)` เอง; 1024 28 steps cfg 5 = 274 วิ (รอบแรก โหลดจากดิสก์)
  - **clip skip 2 (ที่ Animagine แนะนำ) = ค่าเริ่มของ sd.cpp กับ SDXL อยู่แล้ว** — engine Amuse 4.0 768/20 steps:
    ไม่ใส่ flag กับ `--clip-skip 2` ตรงกันทุกพิกเซล, `--clip-skip 1` ต่างมาก (diff 72) → ไม่ต้องใส่อะไร
    (ลองใส่โค้ดแล้วถอยออก). sd-server ก็ได้ค่าเดียวกัน (ฟิลด์ `clip_skip` ใน body / แท็ก `sd_cpp_extra_args` ไม่มีผล)
  - กับดักตอนเทส: **sd-cli ไม่นิ่งข้ามรอบ** — 1106 ได้รูปสลับ 2 แบบรอบเว้นรอบ (diff ~9-30),
    Amuse 4.0 ที่ 768 ก็ต่าง ~11 ระหว่างรอบ (เครื่องบ้านมี RX 9060 XT 2 ใบ อาจเกี่ยว) → เทียบ "ตรงทุกพิกเซล"
    ต้องรันซ้ำหลายรอบ ไม่ใช่รอบเดียว; อย่าเทส SDXL ไม่ใช่ turbo ที่ 4 steps (ได้แต่ noise)
- **LLaDA Image Turbo เจนได้ที่บ้าน** (RAM 64GB): สูตรใน NOTES + `--offload-to-cpu`, 1024 4 steps —
  อ่าน TE 25 วิ x หลายรอบ, diffusion โหลด 188 วิ (ดิสก์ I:), VAE decode 41 วิ; รูปดี (`out/amuse4-home/llada.png`)
  → เพิ่มเป็นเมนู "LLaDA Image Turbo" (id `llada-turbo`, 4 steps cfg 1; ผ่าน GenJab 1024px 467 วิ): `model_files()` ใช้ `amuse_path` + หมวดใหม่
  `components` (ไม่ใส่ `Components` ตัวใหญ่ — ซ้อนบน Windows), `EXTRA_FLAGS` เพิ่ม `--embeddings-connectors`,
  `MODEL_EXTRA_ARGS` ใส่ `--offload-to-cpu` (เลยไม่ผ่าน sd-server), เทส `test_model_files_llada_turbo`

- **ControlNet ProMax ที่บ้าน**: SDXL-Turbo 512 4 steps + รูปอ้างอิง canny/scribble ผ่านทั้ง engine หลักและ alt
  (~8 วิ, รอบแรก 289 วิ = โหลดจากดิสก์) — คงท่า/องค์ประกอบ เปลี่ยนฉากตาม prompt (`out/amuse4-home/cn_grid.png`)
- **ใส่เพลงกับคลิป Wan จริง**: wan22-5b 704x400 49 เฟรม 20 steps = 729 วิ → `add_music_to_clip` 75 วิ
  ได้ webm vp8 + opus stereo ยาว 3.01 วิ (คลิป 3.00) เสียงค่อนข้างเบา (mean -36.5 dB, max -20.6 dB) —
  ถ้าเบาไปลองปรับ volume; audio.cpp เห็น RX 9060 XT 2 ใบ

## ก๊อป LoRA จาก USB มาเครื่อง 8060S (12 พ.ย. 2026)
- ก๊อป `G:\GenJab-home\loras\` 36 ไฟล์ (~4.64GB) → `loras\` (โฟลเดอร์ใหม่ อยู่บน C: ไม่ใช่ junction) ขนาดตรงทุกไฟล์
- `lora_family()`: anima 25 / flux1 8 / None 3 (sdxl ganjad) ตรงกับเครื่องบ้าน; รวมกับของ Amuse เดิม 4 ตัว = เห็น 40 ตัว
- โมเดลบน USB (`z_image_turbo-Q4_K.gguf`, `Qwen3-4B-Instruct-2507-Q4_K_M.gguf`, FLUX.1 VAE) และ sd-cli a3c49b1 มีที่เครื่องนี้อยู่แล้ว ไม่ต้องก๊อป
- เทส `anima-turbo` 768px 8 steps CFG 1.0 seed 42 + `anima-bolly-r5` แรง 1.0 → `out\bolly-r5-test.png` ได้รูปถ่ายสมจริง ~63 วิ (รวมโหลดโมเดล; เครื่องบ้าน ~13 วิ)
- เครื่องนี้ยังไม่มี: `flux1-dev` (LoRA flux 8 ตัวจึงยังใช้ไม่ได้) และ `anima-base` (ต้องรัน `convert_anima_base.py` ก่อน)

## sd-cli 32d516c (master-1088) ใช้กับ GenJab ได้ (12 พ.ย. 2026, เครื่องบ้าน)
- ใหม่กว่า a3c49b1 9 commit (10 พ.ย.): เพิ่ม MiniMax-H3-Image + Sol-H3-VAE, preset `--sigmas minimax-h3-image`,
  CUDA perf, รื้อ runner/weight residency (#2321) และ upscaler (ย้ายไป `pipeline/image_upscale`)
- แฟล็ก CLI ไม่มีตัวไหนถูกลบ/เปลี่ยนชื่อ (diff `examples/common/common.cpp` มีแค่ preset sigma ใหม่)
- โหลด `sd-master-32d516c-bin-win-vulkan-x64.zip` (sha256 ตรงกับ digest ของ release) → `sdcli-1088/bin/` (local only)
- เทสผ่าน: `test_generate.py --fast` OK, `test_app.py` OK, `test_cloud.py` 24 tests OK
- เจนจริงผ่าน (seed 42 → `out/sdcli1088/`): sd-turbo 256px, zimage-turbo 512px 8 steps,
  anima-base + LoRA ganjad แรง 0.8, upscale ESRGAN 256→1024
- รอบแรกช้ามาก (~130–180 วิ/รูป) เพราะ Vulkan คอมไพล์ shader ของ exe ใหม่ครั้งแรก รอบต่อไปเท่าตัวเดิม:
  512px sd-turbo 4.3–4.8 วิ / zimage-turbo 9.5–9.7 วิ (a3c49b1: 4.5 / 10.1 วิ)
- มี build `win-rocm-10.1.0-x64` (~266MB) ด้วย ยังไม่ได้ลองเทียบกับ Vulkan
- สลับแล้ว: user env `TEXT2IMAGE_SDCLI` → `sdcli-1088\bin\sd-cli.exe` (ถอยกลับ = ชี้ไป `sdcli-new\bin\sd-cli.exe`)

## sd-cli 532d2c1 (master-1106) ใช้กับ GenJab ได้ (17 พ.ย. 2026, เครื่อง 8060S)
- ใหม่กว่า a3c49b1 ที่เครื่องนี้ใช้อยู่ 27 commit (10–16 พ.ย.): ตัวเด่นคือ MiniMax-H3-Image
  (ใช้ P-H3-Image TE ได้ + รวมวิธีเลือก TE ทุกตัวแปร H3 + preset sigma p-h3-image/minimax-h3-image),
  interleaved image prompts สำหรับ vision LLM, ตัดเสียง MiniMax-H3 ให้เท่าคลิป, sync ggml 1.0.0,
  รื้อ C API (opaque options/tensors/results — ไม่กระทบ CLI), เร่ง CUDA/HIP, จัด docs ใหม่
- แฟล็ก CLI ไม่มีตัวไหนถูกลบ (เช็ก 36 ตัวที่ GenJab ใช้ อยู่ครบ) — มีเพิ่ม 5 ตัวฝั่งวิดีโอ/อัปสเกล
  (`--control-type`, `--input-frames`, `--upscale-factor`, `--vsr-temporal-chunk-size`, `--vsr-window-size`)
- โหลด `sd-master-532d2c1-bin-win-vulkan-x64.zip` (sha256 ตรงกับ digest ของ release)
  → `sdcli-1106/bin/` (local only, เพิ่มใน .gitignore แล้ว) + อัปเดต `sdcli-help.txt` เป็นของตัวใหม่
- เทสผ่าน: `test_generate.py --fast` OK, `test_app.py` OK, `test_cloud.py` 24 tests OK
- เจนจริงผ่าน (seed 42 → `out/sdcli1106/`): sd-turbo 256px 2 steps ~20 วิ (รวมคอมไพล์ shader รอบแรก),
  zimage-turbo 512px 8 steps — รูปปกติไม่ดำทั้งคู่ (mean ~100)
- สลับแล้ว: user env `TEXT2IMAGE_SDCLI` → `sdcli-1106\bin\sd-cli.exe`
  (ถอยกลับ = ชี้ไป `sdcli-new\bin\sd-cli.exe`)

## sd-cli 532d2c1 (master-1106) ใช้กับ GenJab ได้ (22 พ.ย. 2026)
- `--version`: `sdcli-1106\bin\sd-cli.exe` = 532d2c1, `sdcli-1088\bin\sd-cli.exe` = 32d516c
- สลับแล้ว: `setx TEXT2IMAGE_SDCLI "C:\Users\yaw25\GenJab\sdcli-1106\bin\sd-cli.exe"`
  ขึ้น SUCCESS ตรวจจาก registry 2 ทาง (`HKCU:\Environment` ตรง ๆ กับ
  `[Environment]::GetEnvironmentVariable(...,'User')`) ตรงกันว่าชี้ไป 1106
  (ถอยกลับ = ชี้ไป `sdcli-1088\bin\sd-cli.exe`) — เปิดเทอร์มินัลใหม่จะได้ค่านี้เลย
- เทสผ่าน: `test_app.py` OK, `test_cloud.py` 24 tests OK, `test_generate.py --fast`
  ผ่าน 59/60 — ตัวเดียวที่ล้มคือ `test_resolve_ffmpeg_env_and_missing` ซึ่งเป็นบั๊ก
  ของเทสเอง (มีมาก่อน ไม่เกี่ยวกับ sd-cli): `shutil.which("ffmpeg")` บน Windows
  เจอ `.\ffmpeg.exe` ใน cwd เสมอ เลยไม่ raise ตามที่เทสคาด รันจากโฟลเดอร์ว่าง
  แล้วเทสนี้ผ่าน — งาน MOSS ที่ค้างใน working tree (generate.py/test_generate.py)
  ไม่ได้แตะ แยกไว้ต่างหาก
- เจนจริงผ่าน: sd-turbo 256px 2 steps seed 42 → `out/sdcli1106/sd-turbo-256.png`
  (256x256 RGB สมบูรณ์ ไม่ดำ) — รอบนี้เร็วเลย ไม่มีช่วงคอมไพล์ shader 2–3 นาที
  แบบตอนขึ้น 1088 (ใน `out/sdcli1106/` มีไฟล์เก่าจาก 17 พ.ย. แคช Vulkan น่าจะอุ่นอยู่แล้ว)

## โมเดลใหม่ 3 ตัว: Anima v1.1, Iris Turbo, FLUX.2 dev (22 พ.ย. 2026)
- **Anima v1.1**: ใช้ไฟล์ทางการ `circlestone-labs/Anima`
  `split_files/diffusion_models/anima-turbo-v1.1.safetensors` (~3.9GB, โหลดเข้า
  `models/`) — `anima-turbo` ใน GenJab เลือก v1.1 เองถ้ามี (Amuse ก่อน แล้ว models/)
  ถอยไป v1.0 อัตโนมัติถ้าเครื่องเก่า; aesthetic มี v1.1 อยู่แล้วไม่ต้องทำอะไร
- **Iris Turbo** (`iris-turbo`): `turbo/model.safetensors` (~6GB) จาก
  `speridlabs/iris-3b` วางเป็น `models/iris-3b-turbo.safetensors` + Qwen3VL-4B
  ชุดเดียวกับ base ไม่ใช้ VAE; steps 4 / CFG 1.0 (distill ไม่ใช้ CFG)
- **FLUX.2 dev** (`flux2-dev`): diffusion GGUF Q4_K_M (~20GB, unsloth) +
  Mistral Small 3.2 24B GGUF Q4_K_M (~14GB) + flux2-vae เดิม รวม ~34GB ใน models/;
  ใส่ `--offload-to-cpu` ให้อัตโนมัติทุกครั้ง (32B ยัด VRAM 16GB ไม่หมด)
- โค้ด: `model_files()` + CLI `--model` + เมนู GUI (`MODEL_IDS/SIZES/DEFAULTS`)
  + เทสใหม่ 5 ตัว (`model_files` 3 + argv 2 รวมเช็ก offload) — เทสเก่าไม่แตก
  (label เมนูเดิมไม่เปลี่ยนเพราะ `test_restore_settings_applies` ผูกชื่อไว้)
- เทส: `test_app.py` OK, `test_cloud.py` 24 OK, `test_generate.py --fast` ผ่านหมด
  ยกเว้น `test_resolve_ffmpeg_env_and_missing` ตัวเดียว (บั๊กเก่าของเทสเอง
  เจอ `ffmpeg.exe` ใน cwd — ไม่เกี่ยวกับงานนี้)
- เจนจริงผ่าน (seed 42 → `out/newmodels/`): anima-turbo-v11 256px 8 steps ~6 วิ,
  iris-turbo 256px 4 steps ~15 วิ, flux2-dev 512px 4 steps ~10.5 นาที
  (รอบแรก: โหลดน้ำหนัก 34GB + คอมไพล์ shader; รอบต่อไปควรเร็วกว่านี้)
  ทั้งสามรูปสมบูรณ์ RGB ไม่ดำ
- ไฟล์โหลดด้วย `urllib` ตรง (resume ได้) เพราะ `curl.exe` ในเครื่องนี้พังที่
  schannel (`SEC_E_NO_CREDENTIALS`); โหลดเข้า `models/` (junction → I:) ต้องยกระดับสิทธิ์

## ComfyUI + ROCm ทางการ (23 พ.ย. 2026 — ยังไม่เริ่ม เป็นงานใหญ่)
- ComfyUI มีเอกสาร ROCm ทางการแล้ว ใช้แพ็กเกจ ROCm ของ AMD (TheRock)
  รองรับทั้ง gfx1151 (เครื่องนี้ 8060S) และ gfx1200 (เครื่องบ้าน RX 9060 XT)
- ได้ ecosystem เต็ม: LoRA / ControlNet / custom nodes
- แต่ GenJab ต้องเขียน backend เรียก ComfyUI ผ่าน API ใหม่ (prompt queue +
  websocket ดูรูป) — งานใหญ่ ยังไม่เริ่ม

## Backend ComfyUI เฟส 1 เสร็จ (23 พ.ย. 2026 — ตกลงเริ่มแบบออกแบบก่อนแล้ว go)
- **server มีอยู่แล้วใน WSL** (`~/ComfyUI`, รันด้วย `./start-comfy.sh`, torch
  2.14.0+rocm7.2, ComfyUI 0.41.0) — สังเกต: รายงานตัวเองเป็น gfx1200 RX 9060 XT
  VRAM 16GB (ไม่ใช่ gfx1151 อย่างที่เข้าใจตอนแรก) — เปิดเองใน WSL session แยก
  จาก GenJab, GenJab คุยผ่าน `http://127.0.0.1:8188`
- **ตัดสินใจ**: poll `GET /history` ด้วย urllib ล้วน (ไม่เพิ่ม websocket-client —
  ตรงธรรมเนียม cloud ที่ใช้ stdlib อย่างเดียว), template JSON API format เช็กอิน
  repo, server ให้ user รันเอง (`GENJAB_COMFY_URL`), เฟสแรกเฉพาะ checkpoint
  (CheckpointLoaderSimple + KSampler) — DiT/GGUF ไว้เฟสถัดไป
- **ไฟล์ใหม่**: `comfy_client.py` (queue/wait/fetch/interrupt + builder +
  `COMFY_CKPTS`), `comfy_workflows/sdxl_t2i.json`, `test_comfy.py` (22 tests mock)
- **ต่อ generate.py**: `comfy_txt2img()` + CLI `--backend comfy --comfy-ckpt`
  `--comfy-server` — โมเดลบน server: Juggernaut-XL / Illustrious v0.1+v1.0 /
  NoobAI-XL-Vpred / sd3.5_large / sd1.5; LoRA มี `lcm-lora-sdxl` + ganjad-sdxl 3 ตัว
- **GUI**: ไม่ได้ทำสวิตช์ engine แยก — ใส่โมเดล `(ComfyUI)` 5 ตัวท้ายเมนูเดิมเลย
  (backend เลือกตาม id `comfy-*`, settings เดิมรับได้ไม่ต้อง migrate) +
  `work_comfy` reuse จอแสดงผล/แกลเลอรีเดิม; convert/LoRA ฝั่ง comfy โดนกันด้วย
  warning (เฟสแรก txt2img อย่างเดียว)
- **เทส**: `test_comfy.py` 22 OK, `test_app.py` OK (+2 เทสเมนู comfy),
  `test_cloud.py` 24 OK, `test_generate.py --fast` fast OK (รันจากโฟลเดอร์ว่าง
  เลี่ยงบั๊ก ffmpeg-cwd เก่า)
- **เจนจริง**: Juggernaut-XL 512px 8 steps seed 42 ~29 วิรอบแรก (รวมโหลดโมเดล),
  `out/comfy-smoke.png` 512x512 RGB ผ่านทั้ง spike และ `generate.py --backend comfy`

## ComfyUI LoRA เฟส 2 เสร็จ (23 พ.ย. 2026)
- **mapping**: `COMFY_LORAS` (ganjad-style-sdxl x3 local → ไฟล์ชื่อเดียวกันบน server)
  + `COMFY_LORA_SERVER_ONLY` (`lcm-lora-sdxl`) + รับชื่อไฟล์ `.safetensors` ตรง ๆ —
  นอกนั้น (anima-*/flux-*/ชื่อไม่รู้จัก) `resolve_comfy_lora()` คืน None ให้ปฏิเสธ
- **`generate.comfy_txt2img`**: มี LoRA → resolve + `check_lora_on_server()` ยืนยันไฟล์
  บน server ก่อนคิว (ไม่มี raise พร้อมรายชื่อ SDXL ที่มี) — error ไทยทั้งหมด
- **GUI**: เลิกกัน LoRA เฉพาะตัวใช้ไม่ได้ (anima/flux โดน strip พร้อมโน้ต,
  ganjad คงอยู่) + กันซ้ำตอนกดเจน + `work_comfy` ส่ง lora/แรงเข้า server
- **เทส**: `test_comfy` 26 OK, `test_app` OK (+2), `test_cloud` 24 OK,
  `test_generate --fast` fast OK
- **เจนจริง**: ganjad-style-sdxl-000002 แรง 0.8 + Juggernaut-XL 512px 8 steps seed 42
  ได้รูป 512x512 RGB ใน ~40 วิ (`out/comfy-lora-smoke.png` — ยิง workflow เดียวกับ
  builder จากใน WSL เพราะ sandbox บล็อก socket ตรง; เทส mock ครอบฝั่ง client แล้ว)
- **แก้จริงระหว่างงาน**: เจอ `HTTP_PROXY` ดัก localhost แล้ว `/prompt` ค้าง —
  `comfy_client` เปิดผ่าน opener ที่ bypass proxy ถาวร (ถูกบนเครื่อง user ด้วย)

## ComfyUI แปลงรูป (img2img + inpaint) เสร็จ (23 พ.ย. 2026)
- **`comfy_client.upload_image()`** (multipart เอง ไม่เพิ่ม dep) + **`build_img2img()`**
  (LoadImage + VAEEncode/VAEEncodeForInpaint + KSampler denoise=strength) +
  **`generate.comfy_img2img()`** (ย่อรูป/มาสก์ฝั่ง client ให้เท่าผลลัพธ์ก่อนอัปโหลด)
- **แก้กราฟหลัง smoke ล้ม**: `VAEEncodeForInpaint` ของ ComfyUI 0.41 ต้องการ mask
  ชนิด MASK (ผ่าน `ImageToMask` channel red) + `grow_mask_by` (ใช้ 6) —
  ส่ง IMAGE ตรง ๆ โดน 400 `return_type_mismatch`
- **CLI**: `--backend comfy --init-img` (+ `--mask`, กัน `--keep-face/--face-ref`
  เพราะไฟล์ IP-Adapter ไม่มีบน server) — **GUI**: โหมดแปลงรูปใช้กับ comfy ได้แล้ว
  (คงหน้าเดิมยังถูกกันด้วย warning เดิมของ sd-cli)
- **เทส**: `test_comfy` 32 OK, `test_app` OK (+wiring), `test_cloud` 24 OK,
  `test_generate --fast` fast OK
- **เจนจริง**: i2i 512px strength 0.6 diff จากต้นฉบับ 23.5 (เปลี่ยนชัด);
  inpaint ครึ่งซ้ายคงเดิม diff 4.3 (แค่ noise จาก VAE) ครึ่งขวาเจนใหม่ diff 34.4 —
  มาสก์ขาว = เจนใหม่ตรงตาม sd-cli
  (`out/comfy-i2i-smoke.png`, `out/comfy-inpaint-smoke.png`)
- **วิดีโอ**: ประเมินแล้วทำได้ — มี `WanImageToVideo` + `UNETLoader`/`CLIPLoader`/
  `VAELoader` ครบ, ไฟล์ครบ (`wan2.1_i2v_480p_14B_fp8` + umt5 + wan vae +
  clip_vision_h), รวมคลิปด้วย `VHS_VideoCombine` — แต่ workflow ยาว + เจนนาน
  (โมเดล 14B) ไว้รอบหน้า ไม่รวมในรอบนี้
- **NoobAI เบลอ (23 พ.ย.)**: ค่า default ชุดเดียวกับ Juggernaut (8 steps/CFG 2.0)
  ไม่พอสำหรับโมเดล V-pred — เทสเทียบ seed เดียวกัน: CFG 2.0/8 steps ค่าความคม 252,
  CFG 4.5/24 steps ได้ 834 (sgm_uniform ได้แค่ 625) → เปลี่ยน default
  `comfy-noobai-xl` เป็น steps 24 / CFG 4.5 / 512px

## ComfyUI autostart ใน WSL (23 พ.ย. 2026)
- **`comfy_client.ensure_server()`**: ก่อนคิวงานเช็ก `/system_stats` —
  server หลัก (127.0.0.1:8188) ไม่ติด → `wsl -e bash -lc "cd ~/ComfyUI &&
  ./start-comfy.sh"` แบบ detached แล้วรอจนตอบ (timeout 300 วิ ยกเลิกได้)
- ขอบเขต: สตาร์ทเฉพาะ URL หลัก (`GENJAB_COMFY_URL` ค่าอื่น = แค่ error บอกให้เปิดเอง),
  ไม่มี wsl = error บอกให้เปิดเอง, เปิดซ้ำไม่เป็นไร (ตัวหลังชน port แล้วออกเอง)
- server ที่สตาร์ทแบบ detached รันค้างต่อแม้ปิด GenJab (กิน VRAM ค้างไว้ —
  จะหยุดต้องปิดใน WSL เอง)
- **เทส**: `test_comfy` 37 OK (mock Popen/_open: ติดแล้วไม่สตาร์ท, ดับแล้วสตาร์ท,
  URL อื่น, ไม่มี wsl, timeout, cancel)

## รวม origin/notes/anima-lora เข้าเครื่องบ้าน (24 พ.ย. 2026)
- local (งาน ComfyUI + โมเดลใหม่) กับ remote (KinoLocal + ตัด flux1-dev/flux2-klein + 1106)
  ชนกัน 4 ไฟล์ — resolve แบบ union: เก็บงาน ComfyUI/iris-turbo/flux2-dev/moss-sft/wan22-14b-comfy
  ไว้ทั้งหมด, รับการตัด flux1-dev/flux2-klein ตาม remote (flux1-dev เคยแฮงก์เครื่อง 2 รอบ)
  + ตัด test/offload ที่อ้างถึงออก, รับปุ่ม KinoLocal
- gate หลังรวม: test_app OK, test_cloud 24 OK, test_comfy 45 OK, test_dual 13 OK,
  test_generate --fast = fast OK (รันจากโฟลเดอร์ว่าง; ในโฟลเดอร์โปรเจกต์ติดบั๊กเก่า
  test_resolve_ffmpeg_env_and_missing ตัวเดียวเหมือนเดิม)

## เลือก engine sd-cli ใน GenJab ได้ (23 พ.ย. 2026, เครื่อง 8060S)
- แทนวิธีสลับ env ด้วยเมนู: `generate.py` มี engine สำรอง (`resolve_sd_cli_alt()`:
  env `TEXT2IMAGE_SDCLI_ALT` → `sdcli-1106/` → `sdcli-new/`) + `sd_cli_for(engine, model)`
  + CLI `--engine amuse|alt`; GUI มีเมนู "Engine (sd-cli)" ใต้เมนูโมเดล (จำค่า + ฝังลงรูปด้วย)
- ป้ายตัวหลักบอกที่มาจริง (`main_engine_label()`: env/bundled/Amuse) — ตอนนี้ env
  ชี้ 1106 อยู่เลยขึ้น "ตัวหลัก (1106)"; ถ้าสอง engine ชี้ไฟล์เดียวกันเมนู Alt จะซ่อนให้เอง
- การ์ด minimax-h3-image: engine ไหนไม่มี sigmas preset (เช่น sdcli-new 1079) จะ error
  บอกให้สลับตัวตั้งแต่ก่อนเจน (probe `--help` ครั้งเดียวแล้ว cache)
- เทสใหม่: test_resolve_sd_cli_alt_order, test_path_tag, test_sd_cli_for_selection,
  test_sd_cli_for_preset_guard, test_engine_labels_roundtrip (แก้ FULL_SETTINGS/collect/restore
  ให้มีคีย์ `engine`); gate เขียว: `test_app.py` OK, `test_generate.py --fast` OK, `test_cloud.py` 24 OK
- เจนจริงผ่านทั้งสอง engine: sd-turbo 256px 1 step (`--engine alt` กับค่าเริ่ม) ได้รูปปกติ
- ยังไม่ทำ: backend ComfyUI (รอฝั่งเครื่องบ้าน), บิลด์ `win-rocm` ของ upstream ยังไม่ได้ลองเทียบ Vulkan

## ชื่อไฟล์ไม่วนกลับ (23 พ.ย. 2026, เครื่อง 8060S)
- ปัญหา user: ย้ายรูปไป NAS แล้วลบต้นฉบับ เจนรอบหลังเลขวนกลับมา `pic001` ใหม่
  ย้ายรอบหลังชื่อซ้ำ — เพราะ `next_paths()` ดูแค่ไฟล์ที่เหลืออยู่ในโฟลเดอร์
- แก้: จำเลขล่าสุดราย prefix ในไฟล์ข้างโปรแกรม (`genjab_seq.json` /
  `cloud_seq.json`, ignore จาก git แล้ว) — จองครั้งถัดไปเริ่มจากเลขที่จำ+1
  เดินหน้าอย่างเดียว ยังข้ามชื่อที่มีคนวางทับไว้ให้เหมือนเดิม
- ครั้งแรก/ไฟล์จำหาย: ตั้งต้นจากเลขมากสุดในไฟล์ที่มีอยู่ (ไม่ทับของเดิม);
  ไฟล์จำพัง: ถอยไปนับจากไฟล์จริง; อยากเริ่มเลขใหม่ลบไฟล์จำทิ้งได้
- ฝั่งคลาวด์ (`cloud_core.next_paths`, `cloudNNN.png`) เป็นเหมือนกันเลยแก้ด้วย
  (แยกไฟล์จำของตัวเอง ไม่ import appcore — cloud exe บิลด์แยก)
- เทส: แก้ 4 เทสเดิมให้รันใน tmp cwd (ตัวนับอยู่ใน cwd) + ปรับ expectation
  ไม่ย้อนใช้เลขเก่า; เพิ่ม test_next_paths_no_reuse_after_delete (เคสย้าย+ลบ),
  test_next_paths_seeds_from_existing, test_next_paths_corrupt_seq;
  เทสคลาวด์เพิ่มเคสย้าย+ลบแล้วได้ cloud005 — gate เขียว 3 ชุดเหมือนเดิม

## HunyuanVideo 1.5 ที่เครื่องบ้าน (24 พ.ย. 2026, เครื่อง 8060S)
- คำถาม user: โมเดล 8.3B (VRAM ขั้นต่ำ ~14GB) รันบนเครื่องบ้าน RX 9060 XT 16GB ได้ไหม
- ตอบ: ได้ แต่ต้องไฟล์ย่อ + offload — FP16 ตัวเต็ม (~21GB) ไม่พอ;
  FP8 (~10–13GB) / GGUF Q8 (~14GB) / Q6_K (~12GB) พอ (เลขเคส offload จาก vramready/willitrunai)
- สูตรทางการ sd.cpp (`docs/models/hunyuan_video.md` เช็ก 24 พ.ย.): `-M vid_gen` ใช้ 4 ไฟล์:
  `--diffusion-model` + `--vae` (hunyuanvideo15_vae) + `--llm` (qwen2.5-vl-7b safetensors/GGUF)
  + `--t5xxl` (byt5_small_glyphxl) + `--offload-to-cpu --vae-tiling`
  (แฟล็กครบใน sd-cli 1106 แล้ว เช็กจาก sdcli-help.txt)
- ชุดลองหลัก set B (รวม 18083293862 bytes ~18.08GB — USB G: ว่าง 19069550592):
  diffusion `hunyuanvideo1.5_720p_t2v-Q6_K.gguf` (7024833760, jayn7/HunyuanVideo-1.5_T2V_720p-GGUF/720p/) +
  `Qwen2.5-VL-7B-Instruct.Q8_0.gguf` (8098524160, mradermacher/Qwen2.5-VL-7B-Instruct-GGUF) +
  `hunyuanvideo15_vae_fp16.safetensors` (2521292758) + `byt5_small_glyphxl_fp16.safetensors` (438643184)
  (สองไฟล์หลังใน Comfy-Org/HunyuanVideo_1.5_repackaged/split_files/)
- ทางเลือกรอง (โหลดที่บ้าน ไม่ลง USB): diffusion Q8_0 (8995313888 ภาพดีสุดที่พอดี 16GB) /
  `hunyuanvideo1.5_480p_t2v_cfg_distilled_fp8_scaled.safetensors` (~8.3GB เร็วสุด ใช้ cfg 1.0)
- ชุดคิตบน USB `GenJab-home\hunyuan15-trial\`: TRIAL-GUIDE.md (วิธีทำที่บ้าน) +
  download-models.ps1 (โหลด set B ด้วย curl + เช็กขนาดไบต์) + trial-commands.txt (คำสั่ง smoke 2 ขั้น)
- ระวัง: (1) USB G: เป็น FAT32 (เช็กแล้ว 24 พ.ย.) ใส่ไฟล์เกิน 4GB ไม่ได้
  → โมเดล 18GB หิ้วไปด้วย USB ไม่ได้ ต้องรัน download-models.ps1 โหลดที่บ้านเท่านั้น
  (ทางเลือก: ฟอร์แมต USB เป็น exFAT/NTFS ก่อน — ล้างข้อมูลทั้งไดรฟ์ ถาม user ก่อนทำ)
  (2) ที่บ้าน `models/` ชี้ไป I: ไฟล์ 18GB ลง I: เช็กที่ว่างเกิน 20GB ก่อน
  (3) รันครั้งแรก Vulkan คอมไพล์ shader ช้า 2–3 นาที (ประสบการณ์เดิม) อย่าปิด
  (4) ไลเซนส์ Tencent Hunyuan Community — เช็กก่อนใช้เชิงพาณิชย์
- ยังไม่รู้ (ยืนยันที่บ้าน): GGUF diffusion โหลดผ่าน sd-cli 1106 ได้ไหม
  (ถ้าไม่ได้ใช้ fp8 safetensors แทน) / distilled ใช้ steps+cfg เท่าไร / เวลาเจนจริงบน 9060 XT

## รวม dual-engine จาก USB เข้าเครื่องบ้าน (24 พ.ย. 2026)
- เบสตรง `d289fca` จริง ย้ายแบบ 3-way ทีละฟังก์ชัน (ไม่ทับงาน comfy/โมเดลใหม่):
  engine block + `minimax-h3-image` (model_files/เมนู/CLI/EXTRA_ARGS) + ประปา engine
  ใน 7 ฟังก์ชัน sd-cli + เมนู GUI + settings `engine` + เทสใหม่ 6 ตัว + README
- ปรับจากต้นฉบับ 2 จุด: `img2vid_extend` รองรับ worker comfy (engine ใช้เฉพาะสาย sd-cli),
  ตัด flux1-dev/flux2-klein ตามมติ remote (แฮงก์เครื่อง) — เมนู/โค้ด/เทสที่อ้างถึงเอาออกหมด
- gate: test_app OK, test_cloud 24 OK, test_comfy 45 OK, test_dual 13 OK,
  test_generate --fast = fast OK (รันจากโฟลเดอร์ว่าง)

## เทียบ win-rocm vs Vulkan (24 พ.ย. 2026, เครื่องบ้าน) — ค้างที่รันไทม์ไม่ครบ
- บิลด์: `sd-master-532d2c1-bin-win-rocm-10.1.0-x64.zip` (270MB, commit เดียวกับ
  Vulkan 1106 ที่ใช้อยู่ — เทียบ apples-to-apples ได้) แตกไว้ `sdcli-rocm/bin/`
  (local only, เพิ่มใน .gitignore แล้ว)
- เครื่องเปล่าขาด DLL 5 ตัว (`hipblas.dll`, `libhipblaslt.dll`, `rocblas.dll`,
  `rocsolver.dll`, `origami.dll`) — ยืมชั่วคราวจาก `AMDChat\deps\rocm\10.0`
  (ระวัง: ของ 10.0 ปนกับบิลด์ 10.1.0) แล้ว `sd-cli --help` ผ่าน
- ผล: backend เจอการ์ด (`gfx1200 RX 9060 XT 16GB`) โหลดโมเดลลง VRAM ครบ
  (flash-attn HIP MMA on) แล้ว crash ตอนสร้าง context — rocBLAS ของ AMDChat
  ไม่มี Tensile ของ gfx1200 (มีแค่ gfx115x ลงไป) + ไม่มี `Kernels.so-000-gfx1200`
  → `Could not initialize Tensile host` แล้วล้ม
- ลอง `HSA_OVERRIDE_GFX_VERSION=11.5.1` แล้วไม่มีผลกับบิลด์ Windows (ยังเห็น gfx1200)
- เบสไลน์ Vulkan (sd-turbo 512px 4 steps seed 42): warmup 152 วิ (คอมไพล์ shader),
  นิ่งแล้ว 5.3/7.5/5.4 วิ (เวลารวม python+โหลดโมเดล)
- ทางไปต่อ: ลง HIP SDK 7.1 (~2GB, เอกสาร ROCm รับรอง gfx1200) แล้วลองใหม่ —
  รอ user ตัดสินใจก่อน (ยังไม่ต่อเป็น engine ที่ 3)
- 24 พ.ย. 2026: user อนุมัติ → โหลดตัวติดตั้งแล้ว
  `AMD-Software-PRO-Edition-26.Q1-Win11-For-HIP.exe` (1.75GB, ครบ)
  ไว้ที่ `%TEMP%\hipsdk\` — ขั้นต่อไปต้องรัน installer แบบ admin (มี UAC +
  พ่วง PRO driver 25.30) ให้ user กดเอง แล้ว reboot ก่อนเบนช์ต่อ
- 24 พ.ย. 2026 (ต่อ): user ลง HIP SDK + reboot แล้ว (`hipinfo` เจอ gfx1200) —
  เบนช์จบ: sd-turbo 512px 4 steps seed 42 (end-to-end รวม python+โหลดโมเดล)
  Vulkan: warmup 152 วิ / นิ่ง 5.3, 7.5, 5.4 วิ;
  ROCm: warmup 6.3 วิ / นิ่ง 6.6, 8.3, 6.3 วิ; รูปออกตรงกันทั้งคู่ (mean R/G/B เท่ากัน)
- สรุป: **ไม่ต่อเป็น engine ที่ 3** — นิ่งแล้วเร็วพอ ๆ กัน (ROCm ชนะแค่รอบแรก
  ที่ไม่ต้องคอมไพล์ shader) แถม ROCm ต้องพึ่ง HIP SDK + เคล็ด alias
  `hipblas.dll` (ก๊อปจาก `libhipblas.dll` ของ SDK 7.1 เพราะบิลด์หาชื่อเก่าไม่เจอ)
  — เปราะเกินเป็น default; เก็บ `sdcli-rocm/` ไว้ลองต่อ local only
- 24 พ.ย. 2026 (แก้ System Error): ตัว exe หา DLL ไม่เจอถ้า SDK ไม่อยู่ใน PATH —
  ย้ายรันไทม์ที่ต้องใช้มาไว้ข้าง exe แล้ว (`libhipblaslt/rocblas/rocsolver.dll`,
  `rocblas/library/*gfx1200*` ~11MB, `hipblaslt/library` ชุด gfx1200 ~192MB,
  `hipblas.dll` alias) — เจนผ่านโดยไม่พึ่ง PATH แล้ว (GUI ใช้ได้เลย)
- 24 พ.ย. 2026 (seed สุ่มใหม่ทุกครั้ง): แต่ก่อนเจนเสร็จแอปเขียน seed ที่ใช้
  กลับลงช่อง ทำให้กดเจนซ้ำได้รูปเดิม (ต้องกดปุ่ม “สุ่ม” ล้างก่อนทุกครั้ง) —
  เปลี่ยน `show_result`/`show_batch_result`/`show_video_result` ให้ล้างช่อง seed
  แทน ช่องว่าง = สุ่มใหม่ทุกครั้ง (seed ที่ใช้ดูใน status; พิมพ์ seed เองได้
  เป็นครั้ง ๆ ไป) + เทส `test_show_result_clears_seed`; gate เขียวครบ
- 24 พ.ย. 2026 (ต่อ engine ที่ 3 แบบ local): ผู้ใช้สั่งลองต่อ — เพิ่ม `rocm`
  เป็น engine ที่ 3 (`TEXT2IMAGE_SDCLI_ROCM` → `sdcli-rocm/`, โผล่ในเมนู/CLI
  เฉพาะเครื่องที่มีไบนารี, guard preset แบบเดียวกับ alt) + เทส
  `test_sd_cli_for_rocm` + ป้าย `ROCm (...)` ใน GUI; gate เขียวครบ
  (app/cloud 24/comfy 45/dual 13/generate fast OK) และ smoke `--engine rocm`
  จริงผ่าน (sd-turbo 256px 2 steps ~5 วิ รูปปกติ) — ยังไม่ commit รอผู้ใช้สั่ง

## ROCm บนเครื่อง 8060S (26 พ.ย. 2026) — ใช้ได้แล้ว
- บิลด์: `sd-master-532d2c1-bin-win-rocm-10.1.0-x64.zip` (270MB, commit เดียวกับ
  Vulkan 1106 เทียบ apples-to-apples ได้) จาก release `master-1106-532d2c1`
  ของ leejet/stable-diffusion.cpp → แตกไว้ `sdcli-rocm/bin/` (local only,
  อยู่ใน .gitignore แล้ว; รวมรันไทม์ ~3.9GB)
- เจอการ์ดเลย (`gfx1151` 8060S VRAM 17272 MiB, `hipinfo` เห็นอยู่ก่อนแล้ว) —
  โหลดโมเดลลง VRAM หมด + flash-attn HIP MMA on
- DLL ที่เติมข้าง exe: `hipblas/hipblaslt/rocblas/rocsolver.dll` จาก HIP SDK 7.2
  (`C:\Program Files\AMD\ROCm\7.2\bin`) + `libhipblaslt.dll` + `origami.dll`
  จาก pip `_rocm_sdk_libraries` (SDK ไม่มีสองชื่อนี้) — ไม่ต้องทำ alias
  `hipblas.dll` แบบบ้านเพราะ SDK 7.2 มีชื่อนี้อยู่แล้ว
- Tensile data: ต้องก๊อป **ทั้งโฟลเดอร์** `rocblas/library` + `hipblaslt/library`
  จาก SDK (~1GB) — ลองก๊อปเฉพาะ `*gfx1151*` (~35MB) แล้ว crash `0xC0000005`
  ใน rocblas/Tensile ตอนสร้าง context (ต่างจากบ้านที่ glob เฉพาะ arch แล้วผ่าน)
- เบนช์ sd-turbo 512px 4 steps seed 42 (end-to-end รวม python+โหลดโมเดล):
  ROCm 5.7/6.9/8.4/8.3 วิ; Vulkan (1106) 4.7/9.2/7.0/7.5 วิ —
  พอ ๆ กัน สรุปเหมือนบ้าน: **ไม่ตั้งเป็น default**
  (Vulkan ไม่มี warmup ช้าแล้วเพราะ cache shader อุ่นอยู่)
- รูปออกตรงกัน (mean R/G/B ต่างกัน ~0.5, diff เฉลี่ย 3.3/255)
- GenJab: เมนู `ROCm (...)` โผล่อัตโนมัติ + CLI `--engine rocm` ใช้ได้;
  gate เขียวครบ 5 ชุด (app/cloud 24/comfy 45/dual 13/generate fast)

## ลอง ROCm 1141 (e637c7b) บนเครื่อง 8060S (27 พ.ย. 2026) — ใช้ได้ แต่ยังไม่แทน 1106
- บิลด์: `sd-master-e637c7b-bin-win-rocm-10.1.0-x64.zip` (271MB, sha256 ตรง digest)
  จาก release `master-1141-e637c7b` → `sdcli-rocm-1141/bin/` (local only, เพิ่มใน
  .gitignore) — ก๊อปรันไทม์ทั้งชุดจาก `sdcli-rocm/bin` แล้วทับด้วยไฟล์ใน zip
  (`amdhip64_7.dll` ตัวเดียวกันเป๊ะ; zip ยังไม่แถม hipblas/rocblas เหมือนเดิม)
- ใช้ทดสอบผ่าน env `TEXT2IMAGE_SDCLI_ROCM=...\sdcli-rocm-1141\bin\sd-cli.exe`
- sd-turbo 512px 4 steps seed 42: 1106 7.6–7.9 วิ / 1141 7.7–8.1 วิ, รูปตรงกันทุกพิกเซล
- anima-turbo 1024px + LoRA `anima-bolly-r5` 0.8 seed 42 (รันสลับกัน):
  1141 29.3/24.7/24.2 วิ, 1106 30.5/26.1/25.6 วิ — เร็วพอ ๆ กัน
  รูปต่างนิดหน่อย (diff เฉลี่ย 8.2/255, องค์ประกอบเดิม รายละเอียดมือ/ฉากหลังต่าง)
  น่าจะมาจากโหมด LoRA ใหม่ (#2400: merge ทันทีถ้าไม่ quantize) — คุณภาพดีทั้งคู่
- **พัง**: upstream ถอด `--ip-adapter*` ออกจาก CLI (IP-Adapter ใช้ได้แค่ผ่าน DGL
  `-M dgl --script`) → face-ref/keep-face ของ GenJab ใช้กับ 1141 ไม่ได้
- สรุป: ไม่มีอะไรเร็วขึ้นฝั่ง HIP; ได้แค่ fix LoRA — ยังไม่ย้าย `sdcli-rocm/` ไป 1141
  จนกว่าจะพอร์ต face-ref เป็น DGL (หรือให้ face-ref fallback ไป engine อื่น)

## รองรับโฟลเดอร์โมเดล Amuse 4.0 (28 พ.ย. 2026)
- Amuse 4.0 (ออก 27 พ.ย.) เปลี่ยนชื่อโฟลเดอร์โมเดลเป็นแบบ ComfyUI
  (`Diffusion`→`diffusion_models`, `TextEncoder`→`text_encoders`,
  `AutoEncoder`→`vae`, `LoraAdapter`→`loras`) — GenJab หาโมเดลด้วยชื่อเก่าอย่างเดียวจะพังหลังอัป
- `generate.py`: เพิ่ม `AMUSE_SUBDIRS` + `amuse_path()`/`amuse_subdirs()`
  (ลองชื่อใหม่ก่อนแล้วค่อยชื่อเก่า รายไฟล์ — layout ผสมก็รอด) แล้วเปลี่ยน
  `model_files()` ทั้ง 15 โมเดล + `lora_dirs()` + `convert_anima_base.py` +
  `convert_sdxl_base.py` มาใช้; ไม่เจอเลยคืนชื่อใหม่ (layout ปัจจุบัน)
- กับดัก: รายชื่อ tokenizer ตัด `tokenizer` ตัวเล็กออก เหลือ (`tokenizers`, `Tokenizer`)
  — บน Windows ที่ case-insensitive มันซ้อนกับโฟลเดอร์ `Tokenizer` เดิม
  ทำให้คืน path ผิดตัวสะกด (เทส moss เก่าจับได้)
- เทสใหม่ 5 ตัว: `test_amuse_path_layouts`, `test_model_files_qwen21_v4_layout`,
  `test_model_files_moss_sft_mixed_layout` (layout ผสม),
  `test_model_files_anima_turbo_v4_layout`, `test_lora_dirs_v4_layout`
  (ชื่อซ้ำใหม่ชนะ) — gate เขียว 5 ชุด (generate fast/app/cloud 24/comfy 45/dual 13)
- ยังไม่ทำ (ต้องลง Amuse 4.0 ก่อน): เช็คว่า path `sd-cli.exe` ที่ยืมยังอยู่ที่เดิมไหม,
  เช็คว่า `--ip-adapter` ยังอยู่ใน sd.cpp 1132 ไหม (1141 ถอดแล้ว),
  ชื่อโฟลเดอร์ tokenizer ของ 4.0 ตัวจริง (ตอนนี้เดาว่า `tokenizers`)


## ของจาก Amuse 4.0 ที่เอามาใช้กับ GenJab (28 พ.ย. 2026, เครื่อง 8060S)
ตรวจ Amuse 4.0 ที่ลงแล้วในเครื่องนี้: `sd-cli` = sd.cpp `5fa203c` อยู่ path เดิม,
โฟลเดอร์ tokenizer ชื่อ `tokenizers` จริง (ที่เดาไว้ถูก), มี `sd-server.exe`,
`RuntimeLlamaCpp/vulkan` (llama-server ฯลฯ), `RuntimeAudioCpp/vulkan` (มีแต่ dll), `Templates.json` 109 แบบ
- **คงหน้าเดิมสลับ engine เอง**: sd.cpp ของ Amuse 4.0 ไม่มี `--ip-adapter` แล้ว (เหมือน 1141) →
  `face_engine()` ใน `generate.py` ไล่หา engine ที่มีแฟล็กนี้ (alt → rocm → amuse),
  ไม่มีเลยบอกให้วาง 1106; GUI โชว์ใน status ว่าสลับไปตัวไหน + PNG ฝัง engine ที่เจนจริง
  (settings ยังจำตัวที่ผู้ใช้เลือก) — ทดสอบจริงผ่าน: บังคับตัวหลักเป็น Amuse 4.0 แล้วไปใช้ 1106 รูปออกปกติ
- **ภาพระหว่างเจน**: `--preview proj` (latent projection ไม่ต้องมีไฟล์เพิ่ม) เขียน 64x64 ทุก step →
  `_run(..., preview=(path, cb))` เฝ้า mtime แล้วเรียก callback, GUI วาดบนจอใหญ่ (ไม่แตะ current_img/path)
  ใช้กับ txt2img/img2img ตอนไม่ได้ติ๊กโหลดโมเดลค้าง
- **โหลดโมเดลค้างไว้ (`sd_server.py`)**: เปิด `sd-server.exe` (ข้าง sd-cli ตัวที่เลือก) หนึ่งตัวต่อ
  (exe + argv โมเดล + โฟลเดอร์ LoRA) ผ่าน API A1111 `/sdapi/v1/txt2img|img2img`
  - sd-turbo 512px: warm 1.2–1.3 วิ/รูป vs sd-cli 5–7 วิ (โหลดโมเดลใหม่ทุกรูป)
  - **รูปตรงกับ sd-cli ทุกพิกเซล** (txt2img/img2img/inpaint diff 0.0) — batch ต่างนิดเดียว (~2/255)
  - กับดัก 1: server ไม่อ่านแท็ก `<lora:..>` ใน prompt → ส่งฟิลด์ `lora: [{path: "ชื่อ.safetensors", multiplier}]`
  - กับดัก 2: sd-cli ตัดแค่ตัวแท็ก เหลือเว้นวรรคท้าย (`"a girl "`) — ต้องส่ง prompt แบบนั้นเป๊ะ
    ไม่งั้นรูปต่าง (diff ~20/255); ทำใน `sd_server.split_lora()`
  - ไม่ผ่าน server: คงหน้าเดิม (ไม่มี IP-Adapter), ControlNet, โมเดลที่มี argv พิเศษ (minimax-h3-image,
    flux2-dev), วิดีโอ/ขยายรูป — `_run()` ปิด server ก่อนรัน sd-cli ทุกครั้ง (คืน VRAM)
  - ไม่ได้ใช้ 10 นาทีปิดเอง, ยกเลิก = ฆ่า server (1106 ไม่มี /interrupt), ปิดแอปปิดตาม, server พัง = ถอยไป sd-cli
  - GUI: ติ๊ก "โหลดโมเดลค้างไว้" (ค่าเริ่ม = เปิด, คีย์ `keep_model` ไม่ฝัง PNG)
- **ControlNet (SDXL)**: `control_args()` + `txt2img/txt2img_batch(control={image,type,strength,net?})`
  ชนิด canny (sd-cli หาขอบเองด้วย `--image-preprocess target=control,canny=true`; engine ไม่มีใช้ PIL),
  scribble, depth, openpose; ย่อ/ครอปรูปควบคุมเท่าขนาดเจน; หาไฟล์ใน `models/controlnet/` + `controlnet` ของ Amuse
  GUI: แผง "คุมโครงด้วยรูป" ในโหมดเจนรูป
  - เจนจริงแล้ว: xinsir/controlnet-union-sdxl-1.0 `diffusion_pytorch_model_promax.safetensors`
    (2,513,342,408 bytes, ผู้ใช้โหลดเอง) ใน `models/controlnet/` — ไม่ต้องมี config.json
  - sdxl-turbo 512px 4 steps seed 42: ไม่ใช้ ~27 วิ, canny ~33 วิ (ท่า/เสื้อ/สร้อยตามรูปต้นแบบชัด),
    scribble ~34 วิ (ตุ๊กตาหิมะวางตามเส้นวาด)
  - sd-cli Amuse 4.0 (5fa203c) **ไม่มี `--image-preprocess`** → ใช้ PIL FIND_EDGES แทน (~37 วิ)
    ยังคุมโครงได้ดี รูปต่างจาก 1106 (ที่ให้ sd-cli หาขอบเอง) แต่องค์ประกอบเดียวกัน
- **แปลไทย→อังกฤษในเครื่อง (`local_llm.py`)**: `llama-server` ของ Amuse 4.0 +
  `models/Qwen3-4B-Instruct-2507-Q4_K_M.gguf` (มีอยู่แล้ว) ใช้ SYSTEM_PROMPT เดียวกับ cloud_translate
  เปิดครั้งแรก ~7 วิ แปล < 1 วิ ("ตุ๊กตุ๊ก"→tuk-tuk, "วัดอรุณ"→Wat Arun ถูก), จำผลรายข้อความ,
  ปิดเองก่อนเจนรูปทุกครั้ง (คืน VRAM) + idle 5 นาที — GUI ติ๊ก "แปลไทยเป็นอังกฤษในเครื่อง"
  (คีย์ `translate_local`) กดเจนแล้วแปลก่อน ใส่คำแปลแทนในช่อง แล้วเจนต่อเอง
  - `llama-completion.exe` ของ Amuse ล้ม (exit 127 หลังโหลด ไม่มี output) — เลยใช้ server
- **โมเดลใหม่จาก Templates.json — เครื่องนี้ไม่พอ** (RAM 23.6GB ว่าง ~12GB):
  LLaDA Image Turbo สูตรที่โหลดผ่านแล้ว:
  `--diffusion-model diffusion_models/llada-image-turbo-q8_0.gguf --llm text_encoders/llada-image-turbo-text_encoder-q8_0.gguf
  --embeddings-connectors components/llada-image-connectors-edit.safetensors --vae vae/LLADA/diffusion_pytorch_model.safetensors
  --tokenizer tokenizers/llada/tokenizer.json` (steps 4, cfg 1, scheduler `llada_image` อัตโนมัติ, ใช้ sd-cli Amuse 4.0
  — 1106 ก็รู้จัก llada) → ล้ม `ErrorOutOfDeviceMemory`; `--offload-to-cpu` ล้ม `RAM weight capacity exceeded
  (ขอ 16.6GB มี 12GB)` → **ไปลองเครื่องบ้าน (64GB)**; Boogu 20.6GB bf16 ใหญ่กว่า; SD3.5 Large ของ Amuse
  เป็นโฟลเดอร์ diffusers แบ่ง 2 ไฟล์ (sd-cli อ่านตรงไม่ได้) — ไม่ใส่เมนูหลอก
- **เพลงประกอบคลิป (`audio_gen.py`, audio.cpp ของ Amuse 4.0)**: เรียก `audiocpp.dll` ตรงผ่าน ctypes
  (ABI 0.4.0, build 0.9.6, รู้จัก 155 ตระกูล) registry → `model_load` → session(`gen`, `offline`, vulkan)
  → request(text + options) → `result_audio` (PCM float) → เขียน WAV float32 เอง (ไม่ใช้ numpy)
  - โมเดล: Stable Audio 3 Small Music จาก `audio-cpp/audio.cpp-gguf` โฟลเดอร์ `Stable-Audio-3-Small-Music-GGUF`
    มี q8_0 (1.68GB, ตัวที่ Amuse ใช้) กับ f16 (2.36GB) — ไฟล์เดียวจบ ไม่ต้องมีไฟล์เสริม;
    ผู้ใช้โหลด **f16** มาไว้ `models/audio/` (หาไฟล์ `stable-audio-3-small-music*.gguf` ทั้งคู่ได้)
  - option จริงของ `stable_audio` (อ่านจาก `audiocpp_model_option`): `duration_sec` (ค่าตั้งต้น 120),
    `num_inference_steps` (8), `guidance_scale` (1), `seed`, `negative_prompt`, `duration_padding_sec` (6) ฯลฯ
    — `pick_options()` จับชื่อจากที่โมเดลประกาศ
  - กับดัก: `audiocpp_backend_config.threads` ต้อง > 0 (ใส่ 0 ล้ม `threads must be positive`)
  - ผล 8060S (Vulkan): เพลง 8 วิ เจน 12.7 วิ (44.1kHz stereo, rms 0.076 peak 0.86);
    ใส่เพลงคลิป 6 วิ ~10 วิ รวมทั้งหมด
  - รวมเข้าคลิป: ffmpeg (`resolve_ffmpeg()` หา `C:\Program Files\Amuse\ffmpeg.exe` ด้วยแล้ว — 7.1 มี libopus/aac)
    ภาพ copy + เพลง libopus (webm) / aac (mp4), เฟดเข้า 0.5 วิ เฟดออก 1.5 วิ, ตัดยาวเท่าคลิป,
    เซฟ `ชื่อเดิม_music.webm` (ชนเติม _2) — เพลงยาวสุด 120 วิ (คลิปยาวกว่านั้นได้เพลงแค่ 120 วิแรก)
  - GUI: ปุ่ม "ใส่เพลง" บนแถบบน ใช้คลิปล่าสุด (`current_video`) ไม่มีให้เลือกไฟล์, ถามคำบรรยาย
    (ไทยได้ ผ่าน local_llm), ปิด sd-server/ตัวแปลก่อนเจน (คืน VRAM), ปล่อยโมเดลเพลงหลังเจน;
    ยกเลิกกลางคันไม่ได้ (ctypes call เดียว) — ยกเลิกได้ระหว่างรอ
  - ข้อสังเกต: ตัวแปล Qwen3-4B แปล "ระนาด" เป็น "raad" (ควรเป็น ranat) — เพลงยังออก แต่พิมพ์อังกฤษแม่นกว่า
  - ยังไม่ได้ลองกับคลิป Wan จริง (เครื่องนี้ไม่มีคลิปใน out/) ใช้คลิป testsrc แทน
- โมเดลขยายรูป AnimeSharp ของ 4.0 เป็น `.onnx` — `sd-cli -M upscale` ใช้ไม่ได้
- เทสใหม่: `test_face_engine_fallback`, `test_preview_args_and_run_callback`, `test_sd_server_helpers`,
  `test_controlnet_args`, `test_local_llm_helpers`, `test_audio_gen_helpers` + app (keep_model/translate_local/control_frame)
  — gate เขียว 5 ชุด (generate fast/app/cloud 24/comfy 45/dual 13) + GUI เปิดได้/สลับโหมดได้
