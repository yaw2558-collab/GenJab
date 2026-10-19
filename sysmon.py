"""อ่านการใช้งาน CPU/RAM/GPU ของเครื่องผ่าน Windows PDH — ไม่ต้องลงไลบรารีเพิ่ม.

GPU อ่านจาก Performance Counter (ใช้ได้กับการ์ดทุกค่ายรวม AMD):
  \\GPU Engine(*)\\Utilization Percentage (รวมเฉพาะ engtype_3D) +
  \\GPU Adapter Memory(*)\\Dedicated Usage/Limit.
ถ้าอ่าน GPU ไม่ได้ (เช่น ไม่มี counter) ค่าที่เกี่ยวจะเป็น None — โปรแกรมยังรันต่อได้.
นอก Windows ทุกค่าจะเป็น None.
"""
import ctypes
import os
from ctypes import wintypes

SUPPORTED = os.name == "nt"

if SUPPORTED:
    _pdh = ctypes.WinDLL("pdh.dll")
    _kernel32 = ctypes.WinDLL("kernel32.dll")
else:
    _pdh = _kernel32 = None

PDH_FMT_DOUBLE = 0x00000200
PDH_MORE_DATA = 0x800007D2
PERF_DETAIL_WIZARD = 400


class _CounterValue(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("longValue", wintypes.LONG),
                    ("doubleValue", ctypes.c_double),
                    ("largeValue", ctypes.c_int64)]

    _fields_ = [("CStatus", wintypes.DWORD), ("u", _U)]
    _anonymous_ = ("u",)


class _MemoryStatus(ctypes.Structure):
    _fields_ = [("dwLength", wintypes.DWORD),
                ("dwMemoryLoad", wintypes.DWORD),
                ("ullTotalPhys", ctypes.c_uint64),
                ("ullAvailPhys", ctypes.c_uint64),
                ("ullTotalPageFile", ctypes.c_uint64),
                ("ullAvailPageFile", ctypes.c_uint64),
                ("ullTotalVirtual", ctypes.c_uint64),
                ("ullAvailVirtual", ctypes.c_uint64),
                ("ullAvailExtendedVirtual", ctypes.c_uint64)]


if SUPPORTED:
    _pdh.PdhOpenQueryW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD,
                                   ctypes.POINTER(wintypes.HANDLE)]
    _pdh.PdhOpenQueryW.restype = wintypes.DWORD
    _pdh.PdhAddCounterW.argtypes = [wintypes.HANDLE, wintypes.LPCWSTR, wintypes.DWORD,
                                    ctypes.POINTER(wintypes.HANDLE)]
    _pdh.PdhAddCounterW.restype = wintypes.DWORD
    _pdh.PdhCollectQueryData.argtypes = [wintypes.HANDLE]
    _pdh.PdhCollectQueryData.restype = wintypes.DWORD
    _pdh.PdhGetFormattedCounterValue.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                                 ctypes.POINTER(wintypes.DWORD),
                                                 ctypes.POINTER(_CounterValue)]
    _pdh.PdhGetFormattedCounterValue.restype = wintypes.DWORD
    _pdh.PdhEnumObjectItemsW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR,
                                         wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD),
                                         wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD),
                                         wintypes.DWORD, wintypes.DWORD]
    _pdh.PdhEnumObjectItemsW.restype = wintypes.DWORD
    _pdh.PdhCloseQuery.argtypes = [wintypes.HANDLE]
    _pdh.PdhCloseQuery.restype = wintypes.DWORD
    _kernel32.GlobalMemoryStatusEx.argtypes = [ctypes.POINTER(_MemoryStatus)]
    _kernel32.GlobalMemoryStatusEx.restype = wintypes.BOOL


def _check(rc, what):
    if rc != 0:
        raise OSError(f"{what} ล้มเหลว (PDH {rc:#x})")


def _enum_instances(obj):
    """ชื่อ instance ทั้งหมดของ counter object (เช่น GPU Engine)."""
    n_c, n_i = wintypes.DWORD(0), wintypes.DWORD(0)
    rc = _pdh.PdhEnumObjectItemsW(None, None, obj, None, ctypes.byref(n_c),
                                  None, ctypes.byref(n_i), PERF_DETAIL_WIZARD, 0)
    if rc not in (0, PDH_MORE_DATA):
        _check(rc, f"ลิสต์ {obj}")
    cbuf = (wintypes.WCHAR * max(n_c.value, 1))()
    ibuf = (wintypes.WCHAR * max(n_i.value, 1))()
    _check(_pdh.PdhEnumObjectItemsW(None, None, obj, cbuf, ctypes.byref(n_c),
                                    ibuf, ctypes.byref(n_i),
                                    PERF_DETAIL_WIZARD, 0), f"ลิสต์ {obj}")
    return [s for s in "".join(ibuf).split("\x00") if s]


class _Counter:
    def __init__(self, query, path):
        self.h = wintypes.HANDLE()
        _check(_pdh.PdhAddCounterW(query, path, 0, ctypes.byref(self.h)),
               f"เพิ่ม counter {path}")
        self.path = path

    def read(self):
        v, t = _CounterValue(), wintypes.DWORD()
        _check(_pdh.PdhGetFormattedCounterValue(self.h, PDH_FMT_DOUBLE,
                                                ctypes.byref(t), ctypes.byref(v)),
               f"อ่าน {self.path}")
        return v.doubleValue


def _try_add(query, path):
    """เพิ่ม counter — ไม่มี/เสียหายคืน None แทนที่จะพังทั้ง query."""
    try:
        return _Counter(query, path)
    except OSError:
        return None


class _GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD), ("Data4", wintypes.BYTE * 8)]


class _AdapterDesc(ctypes.Structure):
    _fields_ = [("Description", wintypes.WCHAR * 128),
                ("VendorId", wintypes.UINT), ("DeviceId", wintypes.UINT),
                ("SubSysId", wintypes.UINT), ("Revision", wintypes.UINT),
                ("DedicatedVideoMemory", ctypes.c_size_t),
                ("DedicatedSystemMemory", ctypes.c_size_t),
                ("SharedSystemMemory", ctypes.c_size_t),
                ("AdapterLuidLow", wintypes.DWORD),
                ("AdapterLuidHigh", wintypes.LONG)]


def _dxgi_vram_total_mb():
    """ขนาด VRAM ของการ์ดแยก (ตัวที่เยอะสุด) ผ่าน DXGI — เอาไว้หาร % แถบ VRAM."""
    if not SUPPORTED:
        return None
    try:
        ole32 = ctypes.WinDLL("ole32.dll")
        ole32.CoInitializeEx(None, 0)
        dxgi = ctypes.WinDLL("dxgi.dll")
        iid = _GUID(0x7B7166EC, 0x21C7, 0x44AE,
                    (wintypes.BYTE * 8)(0xB2, 0x1A, 0xC9, 0xAE, 0x32, 0x1A, 0xE3, 0x69))
        dxgi.CreateDXGIFactory.argtypes = [ctypes.POINTER(_GUID),
                                           ctypes.POINTER(ctypes.c_void_p)]
        dxgi.CreateDXGIFactory.restype = wintypes.LONG
        factory = ctypes.c_void_p()
        if dxgi.CreateDXGIFactory(ctypes.byref(iid), ctypes.byref(factory)):
            return None
        vtbl = ctypes.cast(factory, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        EnumAdapters = ctypes.WINFUNCTYPE(wintypes.LONG, ctypes.c_void_p, wintypes.UINT,
                                          ctypes.POINTER(ctypes.c_void_p))(vtbl[7])
        best = None
        i = 0
        while True:
            adapter = ctypes.c_void_p()
            if EnumAdapters(factory, i, ctypes.byref(adapter)):
                break
            try:
                avt = ctypes.cast(adapter, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
                GetDescF = ctypes.WINFUNCTYPE(wintypes.LONG, ctypes.c_void_p,
                                              ctypes.POINTER(_AdapterDesc))(avt[8])
                desc = _AdapterDesc()
                if not GetDescF(adapter, ctypes.byref(desc)):
                    total = desc.DedicatedVideoMemory / (1024 * 1024)
                    if best is None or total > best[0]:
                        best = (total, "".join(desc.Description).split("\x00")[0])
            finally:
                Release = ctypes.WINFUNCTYPE(wintypes.ULONG, ctypes.c_void_p)(avt[2])
                Release(adapter)
            i += 1
        ReleaseF = ctypes.WINFUNCTYPE(wintypes.ULONG, ctypes.c_void_p)(vtbl[2])
        ReleaseF(factory)
        return best[0] if best else None
    except (OSError, ValueError):
        return None

    def read(self):
        v, t = _CounterValue(), wintypes.DWORD()
        _check(_pdh.PdhGetFormattedCounterValue(self.h, PDH_FMT_DOUBLE,
                                                ctypes.byref(t), ctypes.byref(v)),
               f"อ่าน {self.path}")
        return v.doubleValue


def _ram():
    """(percent, used_mb, total_mb) ของแรม — นอก Windows คืน None ทั้งหมด."""
    if not SUPPORTED:
        return None, None, None
    st = _MemoryStatus()
    st.dwLength = ctypes.sizeof(st)
    if not _kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
        return None, None, None
    total_mb = st.ullTotalPhys / (1024 * 1024)
    used_mb = (st.ullTotalPhys - st.ullAvailPhys) / (1024 * 1024)
    return float(st.dwMemoryLoad), used_mb, total_mb


class SysMon:
    """เปิด query ครั้งเดียวแล้ว sample() ได้เรื่อย ๆ — ใช้กับ after() ของ Tk."""

    def __init__(self):
        self._q = None
        self._cpu = None
        self._engines = []
        self._vram = []  # [(usage_counter|None, limit_counter|None)]
        self.vram_total_mb = _dxgi_vram_total_mb()
        if not SUPPORTED:
            return
        try:
            q = wintypes.HANDLE()
            _check(_pdh.PdhOpenQueryW(None, 0, ctypes.byref(q)), "เปิด PDH query")
            self._q = q
        except OSError:
            return
        self._cpu = _try_add(q, r"\Processor(_Total)\% Processor Time")
        try:
            engines = _enum_instances("GPU Engine")
        except OSError:
            engines = []
        for inst in engines:
            if "engtype_3d" in inst.lower():
                c = _try_add(q, f"\\GPU Engine({inst})\\Utilization Percentage")
                if c is not None:
                    self._engines.append(c)
        try:
            mems = _enum_instances("GPU Adapter Memory")
        except OSError:
            mems = []
        for inst in mems:
            u = _try_add(q, f"\\GPU Adapter Memory({inst})\\Dedicated Usage")
            lim = _try_add(q, f"\\GPU Adapter Memory({inst})\\Dedicated Limit")
            if u is not None or lim is not None:
                self._vram.append((u, lim))
        try:
            _pdh.PdhCollectQueryData(q)  # เก็บครั้งแรก (counter แบบ rate ต้องมี 2 จุด)
        except OSError:
            pass

    def sample(self):
        """dict: cpu/ram/gpu (0–100 หรือ None) + vram/ram เป็น MB (หรือ None)."""
        keys = ("cpu", "ram", "gpu", "ram_used_mb", "ram_total_mb",
                "vram_used_mb", "vram_total_mb")
        blank = dict.fromkeys(keys)
        ram = _ram()
        blank["ram"], blank["ram_used_mb"], blank["ram_total_mb"] = ram
        if self._q is None:
            return blank
        try:
            _check(_pdh.PdhCollectQueryData(self._q), "เก็บค่า PDH")
            if self._cpu is not None:
                blank["cpu"] = min(100.0, max(0.0, self._cpu.read()))
            if self._engines:
                blank["gpu"] = min(100.0, max(0.0, sum(c.read() for c in self._engines)))
            best_u, best_lim = None, 0.0
            for usage, limit in self._vram:
                u = usage.read() if usage is not None else 0.0
                lim = limit.read() if limit is not None else 0.0
                if best_u is None or u > best_u:
                    best_u, best_lim = u, lim
            if best_u is not None:
                blank["vram_used_mb"] = best_u / (1024 * 1024)
                lim_mb = best_lim / (1024 * 1024) if best_lim > 0 else None
                blank["vram_total_mb"] = lim_mb or self.vram_total_mb
        except OSError:
            pass
        return blank

    def close(self):
        q, self._q = self._q, None
        self._cpu, self._engines, self._vram = None, [], []
        if q is not None and SUPPORTED:
            try:
                _pdh.PdhCloseQuery(q)
            except OSError:
                pass


if __name__ == "__main__":
    import time
    m = SysMon()
    try:
        m.sample()
        time.sleep(2)
        print(m.sample())
    finally:
        m.close()
