"""Run with isolated installed preferences; leave a separate test scene ready.

This checks real modal lifecycle/timers and sidebar operators. Deterministic camera
actions supplement live HID input; they do not establish physical button coverage.
"""
import importlib
import json
from pathlib import Path
import traceback
from types import SimpleNamespace

import bpy
from mathutils import Vector

root = Path(__file__).resolve().parent.parent
assert Path(bpy.utils.user_resource('CONFIG')).resolve() == (root/'.test-profile/config').resolve()
nav = importlib.import_module('bl_ext.dualsense_test.dualsense_navigator')
ui = nav.ui
motion = importlib.import_module(nav.__package__+'.motion')
cinema = importlib.import_module(nav.__package__+'.cinema')
result = {'blender': bpy.app.version_string, 'checks': [], 'errors': []}


def check(name, condition):
    assert condition, name
    result['checks'].append(name)


def context_parts():
    window = bpy.context.window_manager.windows[0]
    area = next(a for a in window.screen.areas if a.type == 'VIEW_3D')
    region = next(r for r in area.regions if r.type == 'WINDOW')
    return window, area, region


def finish():
    if ui._active:
        ui._active.finish()
    result['finished'] = True
    result['ok'] = not result['errors']
    (root/'test-output/gui_verification.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print('DUALSENSE_GUI_CHECK', json.dumps(result), flush=True)


def start():
    try:
        window, area, region = context_parts()
        area.spaces.active.show_region_ui = True
        bpy.context.scene.dualsense_nav.profile = 'CINEMATIC'
        with bpy.context.temp_override(window=window, area=area, region=region):
            outcome = bpy.ops.view3d.dualsense_navigate('INVOKE_DEFAULT')
        check('Installed extension starts a real GUI modal', outcome == {'RUNNING_MODAL'} and ui._active is not None)
        bpy.app.timers.register(exercise, first_interval=1)
    except Exception:
        result['errors'].append(traceback.format_exc())
        finish()


def exercise():
    try:
        window, area, region = context_parts()
        active = ui._active
        check('Modal remains alive after real timer events', active is not None and not active._finished)
        result['live_controller_status'] = active._pad.status
        check('Live controller reaches GUI modal', bool(active._pad.state.transport))
        with bpy.context.temp_override(window=window, area=area, region=region):
            project = window.scene.dualsense_project
            original_camera = window.scene.camera
            active.toggle_recording()
            active.step(nav.PadState(ly=-1), .1)
            clock = active._record_time
            pose = active._motion.pose.copy()
            outside = SimpleNamespace(type='TIMER', value='', mouse_x=-10000, mouse_y=-10000)
            active.modal(bpy.context, outside)
            check('Pointer exit freezes recording and clears smoothed motion', active._record_time == clock and active._motion.velocity.length == 0 and (active._motion.pose.eye-pose.eye).length < 1e-6)
            active._motion.velocity = Vector((1, 2, 3))
            inside = SimpleNamespace(type='TIMER', value='', mouse_x=region.x+region.width//2, mouse_y=region.y+region.height//2)
            active.modal(SimpleNamespace(window=None), inside)
            check('Window focus guard freezes recording and clears motion', active._record_time == clock and active._motion.velocity.length == 0)
            active.toggle_recording()
            project.bookmarks.clear()
            active._motion.reset(motion.Pose(Vector((4,-4,3)), motion.orientation(2.4,-.15), 45))
            check('GUI save first position', bpy.ops.view3d.dualsense_camera(action='ADD') == {'FINISHED'})
            active._motion.reset(motion.Pose(Vector((1,-5,2)), motion.orientation(2.0,0,.2), 70))
            check('GUI save second position', bpy.ops.view3d.dualsense_camera(action='ADD') == {'FINISHED'})
            project.bookmarks[1].seconds = 2
            project.source = 'BOOKMARKS'
            check('GUI playback starts', bpy.ops.view3d.dualsense_camera(action='PLAY') == {'FINISHED'} and active._playing)
            active.step(nav.PadState(), 1)
            check('GUI playback moves actual viewport', (active._motion.pose.eye-Vector((2.5,-4.5,2.5))).length < 1e-4)
            check('GUI path pause', bpy.ops.view3d.dualsense_camera(action='PLAY') == {'FINISHED'} and active._play_paused)
            bpy.ops.view3d.dualsense_camera(action='STOP_PLAY')
            check('GUI live recording starts', bpy.ops.view3d.dualsense_camera(action='RECORD') == {'FINISHED'} and active._recording)
            for _ in range(30):
                active.step(nav.PadState(ly=-.5, rx=.3), 1/30)
            check('GUI live recording stops', bpy.ops.view3d.dualsense_camera(action='RECORD') == {'FINISHED'} and not active._recording and len(project.recording) > 20)
            check('GUI bake operator creates animation', bpy.ops.view3d.dualsense_camera(action='BAKE') == {'FINISHED'} and project.baked_camera.animation_data is not None)
            check('GUI bake preserves scene camera', window.scene.camera == original_camera)
            bpy.ops.view3d.dualsense_stop()
            check('GUI stop releases timer and HID handles', ui._active is None and active._timer is None and active._pad is None)
            check('GUI restart succeeds', bpy.ops.view3d.dualsense_navigate('INVOKE_DEFAULT') == {'RUNNING_MODAL'})
            active = ui._active
            original = active._original
            active.step(nav.PadState(rx=.7, r2=.5, buttons={'up', 'right'}), .5)
            active.finish(restore=True)
            rv = area.spaces.active.region_3d
            check('Cancel restores position rotation lens and perspective', (rv.view_location-original[0]).length < 1e-4 and abs(rv.view_rotation.dot(original[1])) > .9999 and abs(area.spaces.active.lens-original[4]) < 1e-4 and rv.view_perspective == original[3])
            check('GUI can restart after cancel', bpy.ops.view3d.dualsense_navigate('INVOKE_DEFAULT') == {'RUNNING_MODAL'})
            ui._active.modal(bpy.context, SimpleNamespace(type='ESC', value='PRESS'))
            check('Esc stops independently of controller bindings', ui._active is None)
            bpy.ops.view3d.dualsense_navigate('INVOKE_DEFAULT')
            ui.stop_before_data_change()
            check('Data-change handler safely stops modal', ui._active is None)
            # Demo positions/recording remain; playback starts from saved views.
            project.source = 'BOOKMARKS'
            cinema.apply_view(area.spaces.active, cinema.read_pose(project.bookmarks[0]), 10)
            settings = window.scene.dualsense_nav
            settings.status = 'Ready - Cinematic test scene'
            bpy.ops.wm.save_as_mainfile(filepath=str(root/'test-output/DualSense_Cinematic_Test.blend'))
            area.tag_redraw()
        # Allow all expanded panels to draw before recording the result.
        bpy.app.timers.register(finish, first_interval=1)
    except Exception:
        result['errors'].append(traceback.format_exc())
        finish()


bpy.app.timers.register(start, first_interval=2)
