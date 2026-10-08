"""Run through scripts/test.ps1; runtime and physical input checks."""
import importlib.util
import json
import math
from pathlib import Path
import sys
import time
import zlib

import bpy
from mathutils import Vector

root = Path(__file__).resolve().parent.parent
output = root/"test-output"
output.mkdir(exist_ok=True)
spec = importlib.util.spec_from_file_location("dualsense_navigator", root / "__init__.py")
nav = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = nav
spec.loader.exec_module(nav)
checks = []

def check(name, condition):
    assert condition, name
    checks.append(name)

# Distinct USB/basic-Bluetooth field ordering; enhanced BT CRC integrity.
usb = bytearray(64)
usb[0] = 1
usb[1:5] = bytes([128, 128, 128, 128])
usb[5:7] = bytes([40, 200])
usb[8:11] = bytes([0x28, 0x22, 2])
s = nav.decode_report(usb)
check("USB button and trigger layout", s.buttons == {"cross", "r1", "options", "touchpad"} and s.r2 == 200/255)
basic = bytes([1, 128, 128, 128, 128, 0x28, 0x22, 2, 40, 200])
s = nav.decode_report(basic)
check("Bluetooth basic layout", s.buttons == {"cross", "r1", "options", "touchpad"} and s.r2 == 200/255)
padded = basic + bytes(68)
check("Bluetooth basic padded report", nav.decode_report(padded, bluetooth=True).r2 == 200/255)
enhanced = bytearray(78)
enhanced[0] = 0x31
enhanced[2:65] = usb[1:64]
enhanced[-4:] = zlib.crc32(b'\xa1' + enhanced[:-4]).to_bytes(4, 'little')
check("Bluetooth enhanced layout", nav.decode_report(enhanced).buttons == s.buttons)
enhanced[3] ^= 1
check("Bluetooth bad CRC rejected", nav.decode_report(enhanced) is None)
check("Malformed report rejected", nav.decode_report(bytes([1, 128])) is None)
check("Deadzone eliminates drift", nav.radial_deadzone(.03, -.02, .15) == (0, 0))
x, y = nav.radial_deadzone(1, 1, .15)
check("Radial diagonal magnitude bounded", abs(math.hypot(x, y) - 1) < 1e-6)

class PendingRead:
    def WaitForSingleObject(self, *args):
        return 258
fake = nav.WindowsHID.__new__(nav.WindowsHID)
fake.handle, fake.event, fake.pending = 1, 1, True
fake.k, fake.state = PendingRead(), nav.PadState(lx=1, buttons={'r1'})
fake.last_received = time.monotonic() - .8
stale = fake.poll()
check("Stale HID input stops motion and clears buttons", stale.lx == 0 and not stale.buttons)
fake.last_received = time.monotonic() - 4
closed = []
def fake_close():
    closed.append(True)
    fake.handle = None
fake.close = fake_close
fake.poll()
check("Stale HID connection is released for reconnect", bool(closed) and fake.handle is None)

nav.register()
check("Blender panel registered", hasattr(bpy.types, 'VIEW3D_PT_dualsense'))
area = next(a for a in bpy.context.screen.areas if a.type == 'VIEW_3D')
rv = area.spaces.active.region_3d
settings = bpy.context.window_manager.dualsense_nav

# Exercise the actual motion function with a small harness, in real RegionView3D.
class Harness:
    pass
h = Harness()
h._settings, h._yaw, h._pitch = settings, 0.0, 0.0
h._eye, h._rv, h._distance = Vector((0,0,2)), rv, 10.0
step = nav.VIEW3D_OT_dualsense_navigate.step
step(h, nav.PadState(ly=-1), 1.0)
check("Forward is +X at yaw zero", (h._eye - Vector((3,0,2))).length < 1e-5)
step(h, nav.PadState(lx=1), 1.0)
check("Strafe is perpendicular", (h._eye - Vector((3,-3,2))).length < 1e-5)
step(h, nav.PadState(r2=1), 1.0)
check("R2 ascends in world Z", abs(h._eye.z - 5) < 1e-5)
step(h, nav.PadState(l2=1), 1.0)
check("L2 descends in world Z", abs(h._eye.z - 2) < 1e-5)
before = h._eye.copy()
step(h, nav.PadState(ly=-1, buttons={'r1'}), 1.0)
check("R1 speed multiplier", abs((h._eye - before).length - 12) < 1e-5)
before = h._eye.copy()
step(h, nav.PadState(ly=-1, buttons={'l1'}), 1.0)
check("L1 precision multiplier", abs((h._eye - before).length - .6) < 1e-5)
step(h, nav.PadState(rx=1), .1)
forward = h._q @ Vector((0,0,-1))
check("Right stick turns right", forward.y < 0)
step(h, nav.PadState(ry=-1), .1)
check("Right stick up looks up", (h._q @ Vector((0,0,-1))).z > 0)
for _ in range(20):
    step(h, nav.PadState(ry=-1), 1)
check("Pitch clamped", abs(h._pitch - math.radians(89)) < 1e-6)
eye_from_view = rv.view_location + rv.view_rotation @ Vector((0,0,rv.view_distance))
check("Viewport eye position preserved", (eye_from_view - h._eye).length < 1e-4)

pad = nav.WindowsHID()
live = {'devices': [], 'valid_samples': 0, 'transports': []}
try:
    live['devices'] = [{'input_bytes': n, 'product': hex(p)} for _,n,p in pad.devices()]
    end = time.monotonic()+2
    transports = set()
    while time.monotonic() < end:
        state = pad.poll()
        if state.transport:
            live['valid_samples'] += 1
            transports.add(state.transport)
        time.sleep(.01)
    live['transports'] = sorted(transports)
finally:
    pad.close()
check("HID cleanup", pad.handle is None and pad.event is None and not pad.pending)
nav.unregister()
check("Blender unregister clean", not hasattr(bpy.types.WindowManager, 'dualsense_nav'))
nav.register()
nav.unregister()
check("Blender re-registration clean", not hasattr(bpy.types, 'VIEW3D_PT_dualsense'))
result = {'blender': bpy.app.version_string, 'passed': len(checks), 'checks': checks, 'live_controller': live,
          'limits': ['USB physical device not tested', 'Control feel requires user validation; GUI lifecycle scope is described in docs/testing.md']}
(output/'verification.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result, indent=2))
