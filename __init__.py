"""Windows DualSense viewport navigation. No pip packages or driver changes.

Install this extension ZIP from Blender Preferences > Add-ons > Install from Disk.
HID layout references are listed in README.md. Only input reports are read.
"""


import ctypes as C
from ctypes import wintypes as W
from dataclasses import dataclass, field
import math
import sys
import time
import zlib


@dataclass
class PadState:
    lx: float = 0.0
    ly: float = 0.0
    rx: float = 0.0
    ry: float = 0.0
    l2: float = 0.0
    r2: float = 0.0
    buttons: set = field(default_factory=set)
    transport: str = ""


def decode_report(data, bluetooth=False):
    """Return state for USB 01, basic Bluetooth 01, or enhanced Bluetooth 31."""
    if not data:
        return None
    if data[0] == 0x31:
        if len(data) != 78:
            return None
        if zlib.crc32(b"\xa1" + data[:-4]) != int.from_bytes(data[-4:], "little"):
            return None
        base, basic, transport = 2, False, "Bluetooth (enhanced)"
    elif data[0] == 0x01:
        basic = bluetooth or len(data) == 10
        if len(data) < (10 if basic else 64):
            return None
        base, transport = 1, "Bluetooth" if basic else "USB"
    else:
        return None
    lx, ly, rx, ry = ((data[base + i] - 127.5) / 127.5 for i in range(4))
    if basic:
        b0, b1, b2 = data[5:8]
        l2, r2 = data[8] / 255, data[9] / 255
    else:
        b0, b1, b2 = data[base + 7:base + 10]
        l2, r2 = data[base + 4] / 255, data[base + 5] / 255
    buttons = set()
    for bit, name in enumerate(("square", "cross", "circle", "triangle")):
        if b0 & (0x10 << bit):
            buttons.add(name)
    for bit, name in enumerate(("l1", "r1", "l2", "r2", "create", "options", "l3", "r3")):
        if b1 & (1 << bit):
            buttons.add(name)
    for bit, name in enumerate(("ps", "touchpad", "mute")):
        if b2 & (1 << bit):
            buttons.add(name)
    hat = b0 & 15
    for name, positions in (("up", (7, 0, 1)), ("right", (1, 2, 3)),
                            ("down", (3, 4, 5)), ("left", (5, 6, 7))):
        if hat in positions:
            buttons.add(name)
    return PadState(lx, ly, rx, ry, l2, r2, buttons, transport)


def radial_deadzone(x, y, threshold):
    magnitude = math.hypot(x, y)
    if magnitude <= threshold:
        return 0.0, 0.0
    scale = (min(magnitude, 1.0) - threshold) / ((1.0 - threshold) * magnitude)
    return x * scale, y * scale


class GUID(C.Structure):
    _fields_ = [("Data1", W.DWORD), ("Data2", W.WORD), ("Data3", W.WORD), ("Data4", W.BYTE * 8)]


class InterfaceData(C.Structure):
    _fields_ = [("cbSize", W.DWORD), ("guid", GUID), ("flags", W.DWORD), ("reserved", C.c_size_t)]


class Attributes(C.Structure):
    _fields_ = [("size", W.ULONG), ("vendor", W.USHORT), ("product", W.USHORT), ("version", W.USHORT)]


class Caps(C.Structure):
    _fields_ = [("usage", W.USHORT), ("page", W.USHORT), ("input_size", W.USHORT),
                ("output_size", W.USHORT), ("feature_size", W.USHORT),
                ("reserved", W.USHORT * 17), ("counts", W.USHORT * 10)]


class Overlapped(C.Structure):
    _fields_ = [("internal", C.c_size_t), ("internal_high", C.c_size_t),
                ("offset", W.DWORD), ("offset_high", W.DWORD), ("event", W.HANDLE)]


class WindowsHID:
    """Nonblocking overlapped HID input; Blender never waits for the next report."""

    def __init__(self):
        if sys.platform != "win32":
            raise OSError("DualSense Navigator currently supports Windows only")
        self.k = C.WinDLL("kernel32", use_last_error=True)
        self.h = C.WinDLL("hid", use_last_error=True)
        self.s = C.WinDLL("setupapi", use_last_error=True)
        signatures = (
            (self.k, "CreateFileW", W.HANDLE, [W.LPCWSTR, W.DWORD, W.DWORD, C.c_void_p, W.DWORD, W.DWORD, W.HANDLE]),
            (self.k, "CloseHandle", W.BOOL, [W.HANDLE]),
            (self.k, "CreateEventW", W.HANDLE, [C.c_void_p, W.BOOL, W.BOOL, W.LPCWSTR]),
            (self.k, "ResetEvent", W.BOOL, [W.HANDLE]),
            (self.k, "WaitForSingleObject", W.DWORD, [W.HANDLE, W.DWORD]),
            (self.k, "ReadFile", W.BOOL, [W.HANDLE, C.c_void_p, W.DWORD, C.POINTER(W.DWORD), C.POINTER(Overlapped)]),
            (self.k, "GetOverlappedResult", W.BOOL, [W.HANDLE, C.POINTER(Overlapped), C.POINTER(W.DWORD), W.BOOL]),
            (self.k, "CancelIoEx", W.BOOL, [W.HANDLE, C.POINTER(Overlapped)]),
            (self.h, "HidD_GetHidGuid", None, [C.POINTER(GUID)]),
            (self.h, "HidD_GetAttributes", W.BOOLEAN, [W.HANDLE, C.POINTER(Attributes)]),
            (self.h, "HidD_GetPreparsedData", W.BOOLEAN, [W.HANDLE, C.POINTER(C.c_void_p)]),
            (self.h, "HidD_FreePreparsedData", W.BOOLEAN, [C.c_void_p]),
            (self.h, "HidP_GetCaps", W.LONG, [C.c_void_p, C.POINTER(Caps)]),
            (self.s, "SetupDiGetClassDevsW", W.HANDLE, [C.POINTER(GUID), W.LPCWSTR, W.HWND, W.DWORD]),
            (self.s, "SetupDiEnumDeviceInterfaces", W.BOOL, [W.HANDLE, C.c_void_p, C.POINTER(GUID), W.DWORD, C.POINTER(InterfaceData)]),
            (self.s, "SetupDiGetDeviceInterfaceDetailW", W.BOOL, [W.HANDLE, C.POINTER(InterfaceData), C.c_void_p, W.DWORD, C.POINTER(W.DWORD), C.c_void_p]),
            (self.s, "SetupDiDestroyDeviceInfoList", W.BOOL, [W.HANDLE]),
        )
        for dll, name, restype, argtypes in signatures:
            fn = getattr(dll, name)
            fn.restype, fn.argtypes = restype, argtypes
        self.handle = None
        self.event = None
        self.pending = False
        self.bluetooth = False
        self.last_received = 0.0
        self.state = PadState()
        self.status = "Waiting for controller"
        self.next_scan = 0.0

    def devices(self):
        guid = GUID()
        self.h.HidD_GetHidGuid(C.byref(guid))
        info = self.s.SetupDiGetClassDevsW(C.byref(guid), None, None, 0x12)
        if info == C.c_void_p(-1).value:
            raise C.WinError(C.get_last_error())
        found = []
        try:
            index = 0
            while True:
                item = InterfaceData()
                item.cbSize = C.sizeof(item)
                if not self.s.SetupDiEnumDeviceInterfaces(info, None, C.byref(guid), index, C.byref(item)):
                    if C.get_last_error() != 259:
                        raise C.WinError(C.get_last_error())
                    break
                index += 1
                size = W.DWORD()
                self.s.SetupDiGetDeviceInterfaceDetailW(info, C.byref(item), None, 0, C.byref(size), None)
                detail = C.create_string_buffer(size.value)
                C.cast(detail, C.POINTER(W.DWORD))[0] = 8 if C.sizeof(C.c_void_p) == 8 else 6
                if not self.s.SetupDiGetDeviceInterfaceDetailW(info, C.byref(item), detail, size, None, None):
                    continue
                path = C.wstring_at(C.addressof(detail) + 4)
                handle = self.k.CreateFileW(path, 0, 3, None, 3, 0, None)
                if handle == C.c_void_p(-1).value:
                    continue
                try:
                    attr = Attributes()
                    attr.size = C.sizeof(attr)
                    if not self.h.HidD_GetAttributes(handle, C.byref(attr)):
                        continue
                    if attr.vendor != 0x054C or attr.product not in (0x0CE6, 0x0DF2):
                        continue
                    pp = C.c_void_p()
                    if not self.h.HidD_GetPreparsedData(handle, C.byref(pp)):
                        continue
                    try:
                        caps = Caps()
                        if self.h.HidP_GetCaps(pp, C.byref(caps)) != 0x110000:
                            continue
                        if caps.page == 1 and caps.usage in (4, 5) and caps.input_size >= 10:
                            found.append((path, caps.input_size, attr.product))
                    finally:
                        self.h.HidD_FreePreparsedData(pp)
                finally:
                    self.k.CloseHandle(handle)
        finally:
            self.s.SetupDiDestroyDeviceInfoList(info)
        return found

    def connect(self):
        for path, size, product in self.devices():
            handle = self.k.CreateFileW(path, 0x80000000, 3, None, 3, 0x40000000, None)
            if handle == C.c_void_p(-1).value:
                self.status = "Cannot open DualSense: check Steam Input / HidHide"
                continue
            self.handle = handle
            self.event = self.k.CreateEventW(None, True, False, None)
            if not self.event:
                self.k.CloseHandle(handle)
                self.handle = None
                raise C.WinError(C.get_last_error())
            self.ov = Overlapped()
            self.ov.event = self.event
            self.buffer = C.create_string_buffer(size)
            self.bluetooth = size > 64
            self.last_received = time.monotonic()
            self.status = "DualSense connected; waiting for input"
            return True
        return False

    def poll(self):
        now = time.monotonic()
        if not self.handle:
            if now >= self.next_scan:
                self.next_scan = now + 2.0
                self.connect()
            if not self.handle:
                return PadState()
        try:
            # Drain bounded batches so recent packets drive the viewport.
            for _ in range(64):
                count = W.DWORD()
                if self.pending:
                    if self.k.WaitForSingleObject(self.event, 0) != 0:
                        break
                    if not self.k.GetOverlappedResult(self.handle, C.byref(self.ov), C.byref(count), False):
                        raise C.WinError(C.get_last_error())
                    self.pending = False
                else:
                    self.k.ResetEvent(self.event)
                    if not self.k.ReadFile(self.handle, self.buffer, len(self.buffer), C.byref(count), C.byref(self.ov)):
                        if C.get_last_error() == 997:
                            self.pending = True
                            break
                        raise C.WinError(C.get_last_error())
                state = decode_report(self.buffer.raw[:count.value], self.bluetooth)
                if state:
                    self.state = state
                    self.last_received = now
                    self.status = "DualSense - " + state.transport
            if now - self.last_received > 0.5:
                self.status = "No input - navigation paused"
                if now - self.last_received > 3.0:
                    self.close()
                return PadState()
            return self.state
        except OSError:
            self.close()
            self.status = "Disconnected - reconnecting"
            return PadState()

    def close(self):
        if self.handle:
            if self.pending:
                self.k.CancelIoEx(self.handle, C.byref(self.ov))
                count = W.DWORD()
                # Wait for cancellation before releasing the OVERLAPPED buffer.
                self.k.GetOverlappedResult(self.handle, C.byref(self.ov), C.byref(count), True)
            self.k.CloseHandle(self.handle)
        if self.event:
            self.k.CloseHandle(self.event)
        self.handle = self.event = None
        self.pending = False
        self.state = PadState()


try:
    import bpy
except ImportError:
    bpy = None

if bpy:
    from .ui import register, unregister
    if __name__ == "__main__":
        register()
