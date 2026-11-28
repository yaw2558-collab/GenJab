# Handoff: เทรน Anima LoRA บนเครื่องบ้าน (RX 9060 XT)

วันที่: 2026-11-09 | สถานะ: แผนเสร็จ รอเริ่มข้อ 0 บนเครื่องบ้าน

## สรุป
- เป้าหมาย: เทรน LoRA สถาปัตย์ Anima บนเครื่องบ้าน (RX 9060 XT 16GB + WSL Ubuntu) เอาไปใช้กับ GenJab
- วิธี: kohya sd-scripts `anima_train_network.py` + `--network_module networks.lora_anima`
  (ยืนยันจากโค้ด main ของ kohya-ss/sd-scripts แล้วว่ามีไฟล์ทั้งคู่จริง)
- VRAM: Anima DiT ~4GB — 16GB พอสบาย ไม่ต้องท่า block swap แบบ Qwen-Image ตัวใหญ่
- เกร็ด: เทอร์มินัล user วางบรรทัดยาวแล้วขาด — ให้คำสั่งสั้นๆ ทีละบรรทัดเสมอ

## ของที่ต้องมีบนเครื่องบ้าน (ยังไม่ได้เช็ก — คนละเครื่องกับที่จดโน้ตนี้)
- sd-scripts + venv torch ROCm ที่ `torch.cuda.is_available()` ได้ True
- ไฟล์โมเดล `.safetensors` 3 ตัว: DiT anima + VAE (Qwen-Image) + Qwen3-0.6B
  (ไฟล์ `.gguf` ของ GenJab ใช้เทรนไม่ได้)
- รูป 15-30 ใบ + ไฟล์ `.txt` แคปชันชื่อเดียวกันทุกใบ

## 0. เช็กก่อนเริ่ม (บน WSL เครื่องบ้าน)
```bash
source ~/sd-scripts/venv/bin/activate
python -c "import torch; print(torch.cuda.is_available())"
python -c "import torch; print(torch.cuda.get_device_name(0))"
ls networks/lora_anima.py
ls ~/models/anima
```

## 1. เตรียมรูป
- รูป 15-30 ใบ `.jpg`/`.png` ด้านสั้น >=1024 ไม่มีลายน้ำ
- หน้าคน: หลากมุม/แสง/สีหน้า ครอปหัวไหล่หลัก + เต็มตัว 2-3 ใบ
- trigger word: คำประดิษฐ์ เช่น `ohwx` (ใช้ตอนเจนใน GenJab ด้วย)
- แคปชัน `.txt` ประโยคธรรมชาติ นำหน้าด้วย trigger ทุกใบ:
  `ohwx man, short black hair, smiling, white shirt, outdoor portrait`

```bash
mkdir -p ~/lora-train/data/ohwx
mkdir -p ~/lora-train/output
```

`~/lora-train/dataset.toml`:
```toml
[[datasets]]
resolution = 1024
batch_size = 1

[[datasets.subsets]]
image_dir = "/home/user/lora-train/data/ohwx"
caption_extension = ".txt"
num_repeats = 10
```
(20 รูป x 10 repeats = 200 steps/epoch, รูปน้อยเติม `flip_aug = true` ได้)

## 2. รันเทรน
`~/lora-train/config.toml` (แก้ path 3 บรรทัดแรกให้ตรงเครื่อง):
```toml
pretrained_model_name_or_path = "/home/user/models/anima/dit.safetensors"
vae = "/home/user/models/anima/vae.safetensors"
qwen3 = "/home/user/models/anima/qwen3-0.6b.safetensors"
dataset_config = "/home/user/lora-train/dataset.toml"
output_dir = "/home/user/lora-train/output"
output_name = "ohwx-anima-v1"
network_module = "networks.lora_anima"
network_dim = 16
network_alpha = 16
learning_rate = 1.0e-4
optimizer_type = "AdamW"
lr_scheduler = "cosine"
max_train_epochs = 10
save_every_n_epochs = 2
mixed_precision = "bf16"
cache_latents = true
cache_text_encoder_outputs = true
gradient_checkpointing = true
seed = 1234
sample_prompts = "/home/user/lora-train/sample.txt"
sample_every_n_steps = 500
```
`~/lora-train/sample.txt`:
```
ohwx man, portrait photo --w 768 --h 768 --s 20
```
รัน:
```bash
tmux new -s train
cd ~/sd-scripts
accelerate launch --mixed_precision=bf16 anima_train_network.py --config_file=/home/user/lora-train/config.toml 2>&1 | tee ~/lora-train/train.log
```
พับจอ: `Ctrl-b` แล้ว `d` / กลับมาดู: `tmux attach -t train`

ของห้ามใส่: `fp8_base` (Anima ไม่รองรับ), `AdamW8bit` (ต้องใช้ bitsandbytes
ซึ่งไม่มีบน ROCm), `xformers`/`sageattn` (ไม่มีบน ROCm),
`shuffle_caption`/`caption_tag_dropout` คู่กับ cache TE (assert พัง)

## 3. ดูว่าค้างไหม
```bash
tail -f ~/lora-train/train.log
ps aux | grep anima_train
ls -lt ~/lora-train/output
```
- ปกติ: แถบ cache ตอนแรก (หลายนาทีได้) แล้ว step+loss ไหลเรื่อยๆ หยุดแป๊บตอนเซฟ/sample
- `rocm-smi` ใช้ใน WSL ไม่ได้ — ดูกราฟ GPU/VRAM จาก Task Manager ฝั่ง Windows
- ค้าง = เลยช่วง cache แล้ว log นิ่งเกิน 10 นาที + GPU 0% + ไม่มีไฟล์ใหม่
- `OutOfMemoryError` -> resolution เหลือ 768 | `loss=nan` -> ลด LR ครึ่งนึง

## 4. เอาไปใช้กับ GenJab
```bash
cp ~/lora-train/output/ohwx-anima-v1.safetensors /mnt/c/Users/yaw25/GenJab/loras/
```
ฝั่ง Windows: `python generate.py --model anima-turbo --lora ohwx-anima-v1 --prompt "ohwx man, portrait photo"`
- โผล่ใน dropdown LoRA ไม่มีเตือน incompatible = ใช้ได้
- GenJab จำแนกตระกูล Anima จากชื่อ tensor: adaln_modulation_cross_attn / llm_adapter / .mlp.layer1.

## RESUME
เริ่มที่ข้อ 0 บนเครื่องบ้าน: ยืนยัน torch เห็น GPU + มีไฟล์โมเดล 3 ตัวครบ
ถ้า torch เป็น CPU-only ต้องลง torch ROCm ก่อน (gfx1201)
