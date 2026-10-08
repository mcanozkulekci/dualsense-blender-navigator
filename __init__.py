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
        self.status = "Controller bekleniyor"
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
                self.status = "DualSense acilamadi: Steam Input / HidHide ayarini kontrol et"
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
            self.status = "DualSense baglandi, veri bekleniyor"
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
                self.status = "Veri yok - hareket duraklatildi"
                if now - self.last_received > 3.0:
                    self.close()
                return PadState()
            return self.state
        except OSError:
            self.close()
            self.status = "Baglanti kesildi - yeniden baglaniliyor"
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
    from bpy.props import BoolProperty, FloatProperty, PointerProperty, StringProperty
    from mathutils import Matrix, Quaternion, Vector
except ImportError:
    bpy = None


if bpy:
    _active = None

    def orientation(yaw, pitch):
        # Local camera -Z = forward, +Y = up. Keep the horizon level.
        forward = Vector((math.cos(pitch) * math.cos(yaw), math.cos(pitch) * math.sin(yaw), math.sin(pitch)))
        right = Vector((math.sin(yaw), -math.cos(yaw), 0))
        up = right.cross(forward)
        return Matrix((right, up, -forward)).transposed().to_quaternion()

    class DualSenseSettings(bpy.types.PropertyGroup):
        speed: FloatProperty(name="Hiz (birim/sn)", default=3.0, min=0.01, max=1000)
        look_speed: FloatProperty(name="Bakis (derece/sn)", default=100.0, min=5, max=360)
        deadzone: FloatProperty(name="Deadzone", default=0.15, min=0.02, max=0.8)
        invert_y: BoolProperty(name="Dikey bakisi ters cevir", default=False)
        walk: BoolProperty(name="Yatay hareket (yuruyus)", default=True,
                           description="Sol cubukla duzlemde hareket; kapaliyken bakis yonunde ucus. Yercekimi/carpisma yok")
        status: StringProperty(default="Hazir")

    class VIEW3D_OT_dualsense_navigate(bpy.types.Operator):
        bl_idname = "view3d.dualsense_navigate"
        bl_label = "DualSense ile gezin"
        bl_description = "DualSense gezinmesini baslat; Options veya Esc ile durdur"
        _timer = None
        _pad = None
        _finished = False

        def invoke(self, context, event):
            global _active
            if _active is not None:
                self.report({'WARNING'}, "DualSense zaten calisiyor")
                return {'CANCELLED'}
            if context.area.type != 'VIEW_3D' or not context.space_data.region_3d:
                self.report({'ERROR'}, "Bir 3D View icinde baslat")
                return {'CANCELLED'}
            if context.space_data.region_quadviews:
                self.report({'ERROR'}, "Once Quad View modundan cik (Ctrl+Alt+Q)")
                return {'CANCELLED'}
            self._area, self._window = context.area, context.window
            self._space, self._rv = context.space_data, context.space_data.region_3d
            self._wm, self._settings = context.window_manager, context.window_manager.dualsense_nav
            self._original = (self._rv.view_location.copy(), self._rv.view_rotation.copy(),
                              self._rv.view_distance, self._rv.view_perspective)
            self._q = self._rv.view_rotation.copy()
            self._eye = self._rv.view_location + self._q @ Vector((0, 0, self._rv.view_distance))
            forward = self._q @ Vector((0, 0, -1))
            self._yaw = math.atan2(forward.y, forward.x)
            self._pitch = math.asin(max(-0.999, min(0.999, forward.z)))
            self._q = orientation(self._yaw, self._pitch)
            self._rv.view_perspective = 'PERSP'
            self._distance = max(0.1, self._rv.view_distance)
            self._paused, self._previous = False, set()
            self._finished = False
            try:
                self._pad = WindowsHID()
                self._timer = self._wm.event_timer_add(1 / 60, window=self._window)
                self._wm.modal_handler_add(self)
            except Exception as exc:
                self.finish(restore=True)
                self.report({'ERROR'}, str(exc))
                return {'CANCELLED'}
            self._last = time.monotonic()
            _active = self
            self._settings.status = "Controller bekleniyor"
            return {'RUNNING_MODAL'}

        def modal(self, context, event):
            if self._finished:
                return {'FINISHED'}
            if event.type == 'ESC' and event.value == 'PRESS':
                self.finish()
                return {'FINISHED'}
            # Blender's Event RNA has no .timer property. Other timer events
            # are harmless because integration uses measured elapsed time.
            if event.type != 'TIMER':
                return {'PASS_THROUGH'}
            try:
                if self._area not in self._window.screen.areas[:] or self._area.type != 'VIEW_3D' or self._area.spaces.active != self._space:
                    self.finish()
                    return {'FINISHED'}
                now = time.monotonic()
                dt, self._last = min(now - self._last, 0.05), now
                state = self._pad.poll()
                # Never navigate while Blender loses foreground focus or opens a dialog.
                foreground = C.windll.user32.GetForegroundWindow
                foreground.restype = W.HWND
                process_id = W.DWORD()
                C.windll.user32.GetWindowThreadProcessId.argtypes = [W.HWND, C.POINTER(W.DWORD)]
                C.windll.user32.GetWindowThreadProcessId(foreground(), C.byref(process_id))
                import os
                focused = process_id.value == os.getpid() and context.window == self._window
                under_mouse = self._area.x <= event.mouse_x < self._area.x + self._area.width and self._area.y <= event.mouse_y < self._area.y + self._area.height
                if not focused or not under_mouse or self._area.regions[:] == []:
                    self._previous = state.buttons
                    self._settings.status = "Duraklatildi - fareyi 3D View'e getir"
                    self._area.tag_redraw()
                    return {'PASS_THROUGH'}
                pressed = state.buttons - self._previous
                self._previous = state.buttons
                if "options" in pressed:
                    self.finish()
                    return {'FINISHED'}
                if "cross" in pressed:
                    self._paused = not self._paused
                if "triangle" in pressed:
                    self._settings.walk = not self._settings.walk
                if "up" in pressed:
                    self._settings.speed = min(1000, self._settings.speed * 1.25)
                if "down" in pressed:
                    self._settings.speed = max(0.01, self._settings.speed / 1.25)
                if "circle" in pressed:
                    self.finish(restore=True)
                    return {'FINISHED'}
                self._settings.status = self._pad.status + (" | Beklemede (X)" if self._paused else "")
                if not self._paused:
                    self.step(state, dt)
                self._area.header_text_set("DualSense | Sol: hareket | Sag: bakis | L2/R2: yukseklik | X: duraklat | Options/Esc: bitir")
                self._area.tag_redraw()
                return {'PASS_THROUGH'}
            except Exception as exc:
                self.finish()
                self.report({'ERROR'}, "DualSense: " + str(exc))
                return {'CANCELLED'}

        def step(self, state, dt):
            settings = self._settings
            lx, ly = radial_deadzone(state.lx, state.ly, settings.deadzone)
            rx, ry = radial_deadzone(state.rx, state.ry, settings.deadzone)
            self._yaw -= rx * math.radians(settings.look_speed) * dt
            self._pitch += ry * (1 if settings.invert_y else -1) * math.radians(settings.look_speed) * dt
            self._pitch = max(math.radians(-89), min(math.radians(89), self._pitch))
            self._q = orientation(self._yaw, self._pitch)
            forward = self._q @ Vector((0, 0, -1))
            right = self._q @ Vector((1, 0, 0))
            if settings.walk:
                forward = Vector((math.cos(self._yaw), math.sin(self._yaw), 0))
            vertical = (state.r2 if state.r2 > 0.05 else 0) - (state.l2 if state.l2 > 0.05 else 0)
            direction = right * lx - forward * ly + Vector((0, 0, vertical))
            if direction.length > 1:
                direction.normalize()
            multiplier = 0.2 if "l1" in state.buttons else (4 if "r1" in state.buttons else 1)
            self._eye += direction * settings.speed * multiplier * dt
            self._rv.view_rotation = self._q
            self._rv.view_distance = self._distance
            self._rv.view_location = self._eye - self._q @ Vector((0, 0, self._distance))

        def finish(self, restore=False):
            global _active
            if self._finished:
                return
            self._finished = True
            if self._pad:
                self._pad.close()
                self._pad = None
            if self._timer:
                self._wm.event_timer_remove(self._timer)
                self._timer = None
            try:
                if restore:
                    self._rv.view_location, self._rv.view_rotation, self._rv.view_distance, self._rv.view_perspective = self._original
                self._area.header_text_set(None)
                self._area.tag_redraw()
                self._settings.status = "Durduruldu"
            except (ReferenceError, AttributeError):
                pass
            _active = None

        def cancel(self, context):
            self.finish()

    class VIEW3D_OT_dualsense_stop(bpy.types.Operator):
        bl_idname = "view3d.dualsense_stop"
        bl_label = "Gezinmeyi durdur"

        def execute(self, context):
            if _active:
                _active.finish()
            return {'FINISHED'}

    class VIEW3D_PT_dualsense(bpy.types.Panel):
        bl_label = "DualSense Navigator"
        bl_idname = "VIEW3D_PT_dualsense"
        bl_space_type = 'VIEW_3D'
        bl_region_type = 'UI'
        bl_category = "DualSense"

        def draw(self, context):
            layout = self.layout
            settings = context.window_manager.dualsense_nav
            if _active:
                layout.operator("view3d.dualsense_stop", icon='PAUSE')
            else:
                layout.operator("view3d.dualsense_navigate", icon='PLAY')
            layout.label(text=settings.status)
            for name in ("speed", "look_speed", "deadzone", "walk", "invert_y"):
                layout.prop(settings, name)
            box = layout.box()
            for line in ("Sol cubuk: ileri/geri, saga/sola", "Sag cubuk: etrafa bak", "L2 / R2: alcal / yuksel",
                         "L1: hassas | R1: hizli", "D-pad yukari/asagi: hiz +/-", "X: duraklat | Ucgen: yuru/uc",
                         "Options / Esc: bitir", "Daire: baslangica don ve bitir", "Fare 3D View icindeyken aktif", "Yercekimi ve carpisma yok"):
                box.label(text=line)

    CLASSES = (DualSenseSettings, VIEW3D_OT_dualsense_navigate, VIEW3D_OT_dualsense_stop, VIEW3D_PT_dualsense)

    def register():
        # Permit Text Editor reruns without leaving the old modal/handles alive.
        previous = bpy.app.driver_namespace.get("dualsense_navigator_unregister")
        if previous and previous is not unregister:
            previous()
        for cls in CLASSES:
            bpy.utils.register_class(cls)
        bpy.types.WindowManager.dualsense_nav = PointerProperty(type=DualSenseSettings)
        bpy.app.driver_namespace["dualsense_navigator_unregister"] = unregister

    def unregister():
        if _active:
            _active.finish()
        if hasattr(bpy.types.WindowManager, "dualsense_nav"):
            del bpy.types.WindowManager.dualsense_nav
        for cls in reversed(CLASSES):
            if hasattr(cls, "bl_rna"):
                bpy.utils.unregister_class(cls)
        bpy.app.driver_namespace.pop("dualsense_navigator_unregister", None)

    if __name__ == "__main__":
        register()
