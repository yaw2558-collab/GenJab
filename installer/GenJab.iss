; GenJab installer — ติดตั้งแบบ per-user ไม่ต้อง admin
; ห่อ sd.cpp runtime + โมเดล SD-Turbo มาด้วย ติดตั้งเสร็จใช้ได้ทันที (ออฟไลน์)
#define AppVersion "1.0.0"

[Setup]
AppId={{75079D08-F8DF-41A5-94BD-1489D6A31166}
AppName=GenJab
AppVersion={#AppVersion}
AppPublisher=yaw2558-collab
DefaultDirName={localappdata}\GenJab
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename=GenJab-Setup-{#AppVersion}
Compression=lzma2/fast
SolidCompression=yes
DiskSpanning=yes
ArchitecturesAllowed=x64compatible
WizardStyle=modern
DisableProgramGroupPage=yes

[Files]
Source: "staging\app\*"; DestDir: "{app}"; Flags: recursesubdirs
; น้ำหนักโมเดลบีบอัดไม่ลงอยู่แล้ว ข้ามการบีบอัดให้บิลด์เร็วขึ้นมาก
Source: "staging\models\sd_turbo.safetensors"; DestDir: "{app}\models"; Flags: nocompression

[Dirs]
Name: "{app}\loras"
Name: "{app}\out"

[Tasks]
Name: "desktopicon"; Description: "ไอคอนบนเดสก์ท็อป"; GroupDescription: "ตัวเลือกเพิ่มเติม:"

[Icons]
Name: "{autoprograms}\GenJab"; Filename: "{app}\GenJab.exe"
Name: "{autodesktop}\GenJab"; Filename: "{app}\GenJab.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\GenJab.exe"; Description: "เปิด GenJab หลังติดตั้ง"; Flags: nowait postinstall skipifsilent
