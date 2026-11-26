# MUSE-HANDOFF — งานต่อที่เครื่องบ้าน (RX 9060 XT)

> เขียนที่เครื่อง 8060S วันที่ 23 พ.ย. 2026 — ให้ Muse ที่บ้านอ่านไฟล์นี้แล้วทำต่อ

## 1. สิ่งที่ทำเสร็จแล้วที่เครื่อง 8060S (ต้องซิงก์มาก่อน)

ต่อ **dual-engine sd-cli** เข้า GenJab แล้ว — เลือก engine ได้แทนวิธีสลับ env เดิม:

- `generate.py`: `resolve_sd_cli_alt()` (env `TEXT2IMAGE_SDCLI_ALT` → `sdcli-1106/` →
  `sdcli-new/`) + `sd_cli_for(engine, model)` + CLI `--engine amuse|alt`
  + การ์ด preset `minimax-h3-image` (engine เก่าไม่มีจะ error บอกให้สลับตัวก่อนเจน)
- `app.py` / `appcore.py`: เมนู "Engine (sd-cli)" ใต้เมนูโมเดล + จำค่าใน `settings.json`
  (คีย์ใหม่ `engine`) + ฝังลง PNG
- เทสใหม่ 5 ตัว (ดู `NOTES.md` หัวข้อ 23 พ.ย. 2026)

**ไฟล์ที่เปลี่ยน (ยังไม่ commit):** `generate.py`, `app.py`, `appcore.py`,
`test_generate.py`, `test_app.py`, `README.md`, `NOTES.md`
(เบส commit `d289fca`) — ซิงก์ด้วยวิธีใดวิธีหนึ่ง:

1. ที่เครื่อง 8060S: `git add` + `commit` + `push` แล้วที่บ้าน `git pull`, หรือ
2. **ใช้ของบน USB นี้ได้เลย (ก๊อปไว้แล้ว):** โค้ด 7 ไฟล์ที่ `GenJab-code/`
   (ทับลงโฟลเดอร์ GenJab ที่บ้าน) + รันไทม์ `sdcli-1106/` (ใหม่สุด 15 พ.ย.
   ที่บ้านยังไม่มี — วางข้างโปรเจกต์ให้ engine สำรองหยิบใช้) + ไฟล์นี้

ซิงก์แล้วรัน gate ให้เขียวก่อนเริ่มงาน: (ใน `.venv`)

```
python test_app.py                # ต้องจบ app logic OK
python test_generate.py --fast    # ต้องจบ fast OK
python test_cloud.py              # ต้อง 24 tests OK
```

## 2. สภาพเครื่องบ้าน (จาก NOTES.md — ทวนก่อนทำ)

- GPU: RX 9060 XT 16GB (`gfx1200`, RDNA4) — Windows
- `models/` เป็น junction → `I:\ai-models\GenJab-models` (อย่าเขียนทับ junction)
- มี `sdcli-new/` (1079) + `sdcli-1088/` แล้ว, env `TEXT2IMAGE_SDCLI` ชี้ 1088
- เข้า NAS `\\192.168.1.51\personal_folder\genjab` ได้ (มีผลกับเทส out_dir)
- มี WSL (ใช้เทรน LoRA) + Python `.venv` ของโปรเจกต์

## 3. งานที่ 1 (หลัก): ComfyUI + ROCm บน Windows

เป้าหมาย: ตั้ง ComfyUI ให้รันบนการ์ดจอด้วย ROCm ทางการของ AMD (ไม่ใช้ DirectML/ZLUDA)

- อ้างอิง: หน้า AMD ใน [เอกสาร ComfyUI](https://github.com/Comfy-Org/docs/blob/main/snippets/amd-install.mdx)
  ใช้แพ็กเกจ PyTorch + ROCm multi-arch ของ [AMD TheRock](https://github.com/ROCm/TheRock)
  (`gfx1200` อยู่ในตารางรองรับแล้ว) และมีตัวอย่างสคริปต์ที่
  [ComfyUI-ROCm-Windows-Native](https://github.com/pedrodenovo/ComfyUI-ROCm-Windows-Native)
- ติดตั้งแยกจาก `.venv` ของ GenJab (เช่น โฟลเดอร์ `comfyui/` ข้างโปรเจกต์ + venv ของตัวเอง)
- อย่า commit โมเดล/venv ลง git (เช็ก `.gitignore` ก่อน)
- เกณฑ์ผ่าน: เปิด ComfyUI ได้, `torch.cuda.is_available()` เป็น True บน `gfx1200`,
  เจน txt2img SD1.5/SDXL 512px สำเร็จ 1 รูป, จดคำสั่งติดตั้ง + เวลาที่ใช้ไว้ใน `NOTES.md`
- ถ้า ROCm ติดปัญหา: แผนสำรองคือ ZLUDA v6 (รับรองแค่ RX 9060 XT พอดี)
  ดู [ComfyUI-Zluda](https://github.com/patientx/ComfyUI-Zluda) — แต่เป็นทางรองเท่านั้น

## 4. งานที่ 2 (รอง): ต่อ ComfyUI backend เข้า GenJab

ทำ**หลังงานที่ 1 ผ่านเท่านั้น** (ต้องมี ComfyUI ให้ยิงเทส):

- เพิ่ม backend ที่สองคุยกับ ComfyUI ผ่าน API (`/prompt` + websocket + `/history`)
  เริ่มจาก txt2img อย่างเดียวก่อน (img2img/upscale/video เป็นขั้นต่อไป)
- แนวออกแบบให้เข้ากับของเดิม: ฟังก์ชันเจนรับ `backend="sdcli"|"comfyui"`
  (ต่อจาก `engine=` ที่มีอยู่), เก็บ workflow JSON เป็นเทมเพลตในโฟลเดอร์ใหม่
  (เช่น `comfyui_workflows/`), GUI เพิ่มเมนู backend (จำค่าแบบเดียวกับ engine),
  ComfyUI ต้องเปิดเองก่อนใช้ (GenJab ไม่สั่งเปิดให้ — แค่เช็กว่าเซิร์ฟเวอร์ตอบไหม
  แล้วบอก user ถ้าไม่ตอบ)
- เกณฑ์ผ่าน: เทส mock API (ไม่ต้องเปิด ComfyUI จริง) + เจนจริงผ่าน ComfyUI 1 รูป
  + gate 3 ชุดเดิมยังเขียว + อัปเดต `README.md`/`NOTES.md`

## 5. งานที่ 3 (ถ้ามีเวลา): เทียบบิลด์ win-rocm ของ sd.cpp

- upstream sd.cpp มีบิลด์ `win-rocm-10.1.0-x64` ในหน้า release (NOTES 12 พ.ย.
  เคยเห็นแต่ยังไม่ลอง) — โหลดมาแตกไว้ `sdcli-rocm/` (local only, อย่า commit)
  แล้วเทียบความเร็วกับบิลด์ Vulkan ตัวปัจจุบัน (sd-turbo 512px 4 steps 3 รอบ)
- ถ้าเร็วกว่าชัดเจน + เสถียร: ต่อเป็น engine ที่ 3 (`--engine rocm` + เพิ่มในเมนู GUI)
  ถ้าไม่ดีกว่า: จดผลไว้ใน `NOTES.md` อย่างเดียว ไม่ต้องต่อเข้าโค้ด

## 6. กติกาเดิมของโปรเจกต์ (ห้ามลืม)

- LoRA ใช้ข้ามตระกูลโมเดลไม่ได้ (`lora_family()` มีอยู่แล้ว)
- `models/` / `loras/` / `sdcli-*/` / `*.zip` / venv ห้าม commit (ดู `.gitignore`)
- แก้ settings ต้องอัปเดต `FULL_SETTINGS` + เทส collect/restore ใน `test_app.py`
- ทุกงานจบต้องอัปเดต `NOTES.md` เป็นหัวข้อวันที่แบบเดิม
