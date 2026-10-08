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
settings = bpy.context.scene.dualsense_nav

# Motion integration and scene workflows are checked against actual Blender data.
from dualsense_navigator import ui, cinema
from dualsense_navigator.motion import Motion, Pose, orientation, sample_path
from types import SimpleNamespace
settings = bpy.context.scene.dualsense_nav
project = bpy.context.scene.dualsense_project
space = area.spaces.active
scene = bpy.context.scene

class Harness:
    step = ui.VIEW3D_OT_dualsense_navigate.step
    toggle_recording = ui.VIEW3D_OT_dualsense_navigate.toggle_recording
    record_sample = ui.VIEW3D_OT_dualsense_navigate.record_sample
    save_position = ui.VIEW3D_OT_dualsense_navigate.save_position
    recall_position = ui.VIEW3D_OT_dualsense_navigate.recall_position
    toggle_playback = ui.VIEW3D_OT_dualsense_navigate.toggle_playback
    handle_actions = ui.VIEW3D_OT_dualsense_navigate.handle_actions

def harness():
    h = Harness()
    h._settings, h._project, h._scene, h._space = settings, project, scene, space
    h._motion = Motion(Pose(Vector((0, 0, 2)), orientation(0, 0), 50))
    h._distance = 10
    h._recording = h._playing = h._play_paused = h._paused = False
    cinema.apply_view(space, h._motion.pose, 10)
    return h

check('Navigation preset has no duplicate bindings', not ui.binding_conflicts(settings))
settings.profile = 'CINEMATIC'
check('Cinematic preset applies fly mode and smoothing', not settings.walk and settings.move_smoothing == 8)
check('Cinematic bindings have no conflicts', not ui.binding_conflicts(settings) and settings.bind_add_bookmark == 'CROSS')
settings.bind_fast = 'CROSS'
check('Duplicate binding detected', bool(ui.binding_conflicts(settings)))
settings.bind_fast = 'TRIANGLE'
check('Custom binding dispatch', ui.mapped_actions(settings, {'cross', 'triangle'}) == {'add_bookmark', 'fast'})
settings.profile = 'NAVIGATION'
h = harness()
h.step(nav.PadState(ly=-1), 1)
check('Forward is +X at yaw zero', (h._motion.pose.eye-Vector((3,0,2))).length < 1e-5)
h.step(nav.PadState(lx=1), 1)
check('Strafe is perpendicular', (h._motion.pose.eye-Vector((3,-3,2))).length < 1e-5)
h.step(nav.PadState(r2=1), 1)
check('R2 ascends in world Z', abs(h._motion.pose.eye.z-5) < 1e-5)
h.step(nav.PadState(l2=1), 1)
check('L2 descends in world Z', abs(h._motion.pose.eye.z-2) < 1e-5)
settings.invert_triggers = True
h.step(nav.PadState(l2=1), 1)
check('Trigger directions can be swapped', abs(h._motion.pose.eye.z-5) < 1e-5)
settings.invert_triggers = False
before = h._motion.pose.eye.copy()
h.step(nav.PadState(ly=-1, buttons={'r1'}), 1)
check('Fast speed multiplier', abs((h._motion.pose.eye-before).length-12) < 1e-5)
before = h._motion.pose.eye.copy()
h.step(nav.PadState(ly=-1, buttons={'l1'}), 1)
check('Precision multiplier', abs((h._motion.pose.eye-before).length-.6) < 1e-5)
h.step(nav.PadState(rx=1), .1)
check('Right stick turns right', (h._motion.pose.rotation @ Vector((0,0,-1))).y < 0)
h.step(nav.PadState(ry=-1), .1)
check('Right stick up looks up', (h._motion.pose.rotation @ Vector((0,0,-1))).z > 0)
for _ in range(20):
    h.step(nav.PadState(ry=-1), 1)
check('Pitch clamped', abs(h._motion.pitch-math.radians(89)) < 1e-6)
eye_from_view = rv.view_location+rv.view_rotation @ Vector((0,0,rv.view_distance))
check('Viewport eye position preserved', (eye_from_view-h._motion.pose.eye).length < 1e-4)

settings.profile = 'CINEMATIC'
settings.walk = True

def run_motion(fps):
    obj = harness()
    for _ in range(fps):
        obj.step(nav.PadState(ly=-1, rx=0, buttons={'up', 'right'}), 1/fps)
    return obj

low, high = run_motion(30), run_motion(120)
check('Smoothed movement is frame-rate independent', (low._motion.pose.eye-high._motion.pose.eye).length < 2e-5)
check('Smoothed roll and zoom are frame-rate independent', abs(low._motion.roll-high._motion.roll) < 2e-5 and abs(low._motion.pose.lens-high._motion.pose.lens) < 2e-5)
def look_only(fps):
    obj = harness()
    for _ in range(fps):
        obj.step(nav.PadState(rx=.4, ry=-.2), 1/fps)
    return obj._motion
look_low, look_high = look_only(30), look_only(120)
check('Smoothed yaw and pitch are frame-rate independent', abs(look_low.yaw-look_high.yaw) < 2e-5 and abs(look_low.pitch-look_high.pitch) < 2e-5)
check('Smoothing ramps movement rather than jumping', 0 < low._motion.pose.eye.x < settings.speed)
before = low._motion.pose.eye.copy()
low.step(nav.PadState(), .05)
check('Smoothing decelerates on stick release', (low._motion.pose.eye-before).length > 0)
low._motion.clear_velocity()
before = low._motion.pose.copy()
low.step(nav.PadState(), .05)
check('Cleared velocity prevents focus or stale-input drift', (before.eye-low._motion.pose.eye).length < 1e-6 and abs(before.lens-low._motion.pose.lens) < 1e-6)
h = harness()
h.step(nav.PadState(buttons={'right', 'up'}), .5)
check('Roll changes without changing forward direction', h._motion.roll > 0 and (h._motion.pose.rotation @ Vector((0,0,-1))-Vector((1,0,0))).length < 1e-5)
check('Narrow FOV increases focal length', h._motion.pose.lens > 50)
h.handle_actions({'reset_horizon', 'reset_lens'})
h.step(nav.PadState(), .05)
check('Horizon and FOV reset remove residual drift', abs(h._motion.roll) < 1e-6 and abs(h._motion.pose.lens-50) < 1e-5)
for _ in range(10):
    h.step(nav.PadState(buttons={'up'}), 1)
check('Lens upper clamp', h._motion.pose.lens == 200)
for _ in range(20):
    h.step(nav.PadState(buttons={'down'}), 1)
check('Lens lower clamp', h._motion.pose.lens == 10)
settings.invert_y = True
h = harness()
h.step(nav.PadState(ry=-1), .1)
check('Vertical look inversion', h._motion.pitch < 0)
settings.invert_y = False

project.bookmarks.clear()
h = harness()
h.save_position()
h._motion.reset(Pose(Vector((6,4,3)), orientation(.7,.2,.4), 85))
h.save_position()
project.bookmarks[1].seconds = 2
check('Saved positions contain eye rotation and lens', len(project.bookmarks) == 2 and project.bookmarks[1].lens == 85)
h.recall_position(0)
check('Recall restores full pose', (h._motion.pose.eye-Vector((0,0,2))).length < 1e-5 and h._motion.pose.lens == 50)
h.recall_position(-1)
check('Previous position wraps', project.index == 1)
project.source = 'BOOKMARKS'
h.toggle_playback()
h.step(nav.PadState(), 1)
mid = h._motion.pose.copy()
check('Path playback interpolates position lens and rotation', (mid.eye-Vector((3,2,2.5))).length < 1e-5 and abs(mid.lens-67.5) < 1e-5 and abs(mid.rotation.magnitude-1) < 1e-6)
h.toggle_playback()
h.step(nav.PadState(), .3)
check('Path pause freezes playback time', h._play_time == 1 and (h._motion.pose.eye-mid.eye).length < 1e-5)
h.toggle_playback()
h.step(nav.PadState(ly=-1), .1)
check('Manual stick input interrupts playback', not h._playing)
h.toggle_playback()
h.step(nav.PadState(), 3)
check('Path stops at exact endpoint', not h._playing and (h._motion.pose.eye-Vector((6,4,3))).length < 1e-5)
q = orientation(1, .2, .3)
qneg = q.copy()
qneg.negate()
short = sample_path([(0, Pose(Vector(), q, 50)), (1, Pose(Vector(), qneg, 50))], .5)
check('Quaternion sign change follows shortest arc', abs(short.rotation.dot(q)) > .99999)

h = harness()
scene.render.fps, scene.render.fps_base = 30, 1
h.toggle_recording()
check('Recording starts at zero seconds', project.recording[0].seconds == 0)
for _ in range(60):
    h.step(nav.PadState(ly=-1), 1/60)
h.toggle_recording()
check('Live recording samples at scene FPS and includes final pose', 30 <= len(project.recording) <= 32 and abs(project.recording[-1].seconds-1) < 1e-5 and (cinema.read_pose(project.recording[-1]).eye-h._motion.pose.eye).length < 1e-5)
scene.render.fps = 24
h.toggle_recording()
for _ in range(60):
    h.step(nav.PadState(ly=-1), 1/60)
h.toggle_recording()
check('24 FPS recording keeps its clock on 60 Hz timer ticks', len(project.recording) == 25 and abs(project.recording[1].seconds-1/24) < 1e-6)
scene.render.fps = 30
project.source = 'RECORDING'
h.toggle_playback()
h.step(nav.PadState(), .5)
check('Live recording can be replayed', h._playing and h._motion.pose.eye.x > 0)
h.handle_actions({'stop_play'})
check('Stop path leaves the current view', not h._playing and h._motion.pose.eye.x > 0)

# Bake uses an independent camera and two actions; no existing animation is cleared.
project.source = 'BOOKMARKS'
project.start_frame = 10
scene.frame_set(17)
original_camera = scene.camera
original_camera.location.x = 42
original_camera.keyframe_insert(data_path='location', frame=1)
original_action = original_camera.animation_data.action
original_action_count = len(bpy.data.actions)
original_frame = scene.frame_current
camera, end = cinema.bake_camera(scene, project)
check('Bake creates a new camera and preserves active camera', camera != original_camera and scene.camera == original_camera)
check('Existing animation and timeline frame preserved', original_camera.animation_data.action == original_action and scene.frame_current == original_frame and original_action_count+1 <= len(bpy.data.actions) <= original_action_count+2 and camera.animation_data.action != original_action and camera.data.animation_data.action != original_action)
check('Bake includes full frame range', end == 70)
for frame, location, lens in [(10, Vector((0,0,2)), 50), (40, Vector((3,2,2.5)), 67.5), (70, Vector((6,4,3)), 85)]:
    scene.frame_set(frame)
    evaluated = camera.evaluated_get(bpy.context.evaluated_depsgraph_get())
    expected = sample_path(cinema.path_samples(project), (frame-project.start_frame)/30, True)
    check(f'Baked camera matches position rotation and lens at frame {frame}', (evaluated.location-location).length < 1e-4 and abs(evaluated.data.lens-lens) < 1e-4 and abs(evaluated.rotation_quaternion.dot(expected.rotation)) > .99999)
scene.frame_set(40)
check('Baked camera quaternion remains normalized', abs(camera.rotation_quaternion.magnitude-1) < 1e-5)
second, _ = cinema.bake_camera(scene, project)
check('Repeated baking preserves previous generated camera', second != camera and camera.name in bpy.data.objects and camera.animation_data.action is not None)
project.source = 'RECORDING'
record_camera, record_end = cinema.bake_camera(scene, project)
scene.frame_set(record_end)
check('Recorded take bakes to its final sample', (record_camera.location-cinema.read_pose(project.recording[-1]).eye).length < 1e-4)

before_objects = len(bpy.data.objects)
project.source = 'BOOKMARKS'
project.bookmarks[1].seconds = 0
try:
    cinema.bake_camera(scene, project)
    raise AssertionError('Invalid zero-duration segment accepted')
except ValueError:
    check('Invalid path rejected before creating objects', len(bpy.data.objects) == before_objects)
project.bookmarks[1].seconds = 2000
try:
    cinema.bake_camera(scene, project)
    raise AssertionError('Excessive bake accepted')
except ValueError:
    check('Excessive bake rejected before creating objects', len(bpy.data.objects) == before_objects)
project.bookmarks[1].seconds = 2
space.camera = original_camera
rv.view_perspective = 'CAMERA'
captured = cinema.capture_view(space)
check('Camera View captures evaluated camera transform and lens', (captured.eye-original_camera.matrix_world.translation).length < 1e-5 and captured.lens == original_camera.data.lens)
original_camera.data.type = 'ORTHO'
try:
    cinema.capture_view(space)
    raise AssertionError('Orthographic Camera View accepted')
except ValueError:
    check('Orthographic Camera View rejected explicitly', True)
original_camera.data.type = 'PERSP'
rv.view_perspective = 'PERSP'

# Exercise sidebar operators under a real 3D View context, without a controller.
with bpy.context.temp_override(area=area, region=next(r for r in area.regions if r.type == 'WINDOW')):
    before_count = len(project.bookmarks)
    check('Sidebar Save operator', bpy.ops.view3d.dualsense_camera(action='ADD') == {'FINISHED'} and len(project.bookmarks) == before_count+1)
    check('Sidebar Recall operator', bpy.ops.view3d.dualsense_camera(action='RECALL') == {'FINISHED'})
    check('Sidebar Replace operator', bpy.ops.view3d.dualsense_camera(action='UPDATE') == {'FINISHED'})
    check('Sidebar reorder operator', bpy.ops.view3d.dualsense_camera(action='UP') == {'FINISHED'} and project.index == before_count-1)
    check('Sidebar delete operator', bpy.ops.view3d.dualsense_camera(action='REMOVE') == {'FINISHED'} and len(project.bookmarks) == before_count)

settings.bind_zoom_in = 'PS'
expected_eye = list(project.bookmarks[0].eye)
expected_samples = len(project.recording)
scene_path = output/'persistence.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(scene_path))
bpy.ops.wm.open_mainfile(filepath=str(scene_path))
settings, project = bpy.context.scene.dualsense_nav, bpy.context.scene.dualsense_project
check('Bindings and profile survive blend reload', settings.profile == 'CINEMATIC' and settings.bind_zoom_in == 'PS')
check('Positions and recording survive blend reload', list(project.bookmarks[0].eye) == expected_eye and len(project.recording) == expected_samples)
check('Load and undo safety handlers remain registered', ui.stop_before_data_change in bpy.app.handlers.load_pre and ui.stop_before_data_change in bpy.app.handlers.undo_pre)

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
check("Blender unregister clean", not hasattr(bpy.types.Scene, 'dualsense_nav'))
nav.register()
nav.unregister()
check("Blender re-registration clean", not hasattr(bpy.types, 'VIEW3D_PT_dualsense'))
result = {'blender': bpy.app.version_string, 'passed': len(checks), 'checks': checks, 'live_controller': live,
          'limits': ['USB physical device not tested', 'Control feel requires user validation; GUI lifecycle scope is described in docs/testing.md']}
(output/'verification.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result, indent=2))
