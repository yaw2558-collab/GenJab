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
