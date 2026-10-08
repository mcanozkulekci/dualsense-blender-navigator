"""Blender properties, sidebar and modal controller integration."""
import ctypes as C
from ctypes import wintypes as W
import math
import os
import time

import bpy
from bpy.app.handlers import persistent
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty, FloatProperty,
                       FloatVectorProperty, IntProperty, PointerProperty, StringProperty)

from . import PadState, WindowsHID, radial_deadzone
from .motion import Motion, Pose, orientation, sample_path
from .cinema import (apply_view, bake_camera, capture_view, path_samples, read_pose,
                     store_pose, validate_path)

_active = None

BUTTONS = [('NONE', 'Unassigned', '')] + [(s.upper(), label, '') for s, label in (
    ('cross', 'Cross (X)'), ('circle', 'Circle'), ('square', 'Square'), ('triangle', 'Triangle'),
    ('l1', 'L1'), ('r1', 'R1'), ('l3', 'L3'), ('r3', 'R3'), ('up', 'D-pad Up'),
    ('down', 'D-pad Down'), ('left', 'D-pad Left'), ('right', 'D-pad Right'),
    ('options', 'Options'), ('create', 'Create'), ('touchpad', 'Touchpad click'),
    ('mute', 'Mute'), ('ps', 'PS'))]

# One button per action; duplicate assignments are rejected before navigation.
ACTIONS = {
    'stop': ('Stop navigation', 'OPTIONS', 'MUTE'),
    'cancel': ('Restore view and stop', 'CIRCLE', 'NONE'),
    'pause': ('Pause navigation', 'CROSS', 'L3'),
    'walk': ('Toggle walk / fly', 'TRIANGLE', 'NONE'),
    'speed_up': ('Increase speed', 'UP', 'NONE'),
    'speed_down': ('Decrease speed', 'DOWN', 'NONE'),
    'slow': ('Precision (hold)', 'L1', 'SQUARE'),
    'fast': ('Fast (hold)', 'R1', 'TRIANGLE'),
    'zoom_in': ('Narrow FOV (hold)', 'NONE', 'UP'),
    'zoom_out': ('Widen FOV (hold)', 'NONE', 'DOWN'),
    'roll_left': ('Roll left (hold)', 'LEFT', 'LEFT'),
    'roll_right': ('Roll right (hold)', 'RIGHT', 'RIGHT'),
    'reset_lens': ('Reset FOV', 'NONE', 'CIRCLE'),
    'reset_horizon': ('Level horizon', 'R3', 'R3'),
    'add_bookmark': ('Save camera position', 'SQUARE', 'CROSS'),
    'previous': ('Previous position', 'NONE', 'L1'),
    'next': ('Next position', 'NONE', 'R1'),
    'play': ('Play / pause camera path', 'NONE', 'OPTIONS'),
    'stop_play': ('Stop camera path', 'CREATE', 'CREATE'),
    'record': ('Start / stop recording', 'TOUCHPAD', 'TOUCHPAD'),
}


def apply_profile(settings, context=None):
    cinematic = settings.profile == 'CINEMATIC'
    for action, (_, navigation, cinema) in ACTIONS.items():
        setattr(settings, 'bind_'+action, cinema if cinematic else navigation)
    settings.move_smoothing = settings.look_smoothing = settings.zoom_smoothing = 8.0 if cinematic else 0.0
    settings.walk = not cinematic
    settings.speed = 1.0 if cinematic else 3.0
    settings.look_speed = 40.0 if cinematic else 100.0
    settings.fast_multiplier = 4.0
    settings.slow_multiplier = 0.2
    if _active:
        _active._motion.clear_velocity()


def binding_conflicts(settings):
    seen, conflicts = {}, []
    for action, (label, _, _) in ACTIONS.items():
        button = getattr(settings, 'bind_'+action)
        if button == 'NONE':
            continue
        if button in seen:
            conflicts.append(f"{button}: {seen[button]} / {label}")
        else:
            seen[button] = label
    return conflicts


def mapped_actions(settings, buttons):
    return {action for action in ACTIONS if getattr(settings, 'bind_'+action).lower() in buttons}


class DualSenseSettings(bpy.types.PropertyGroup):
    profile: EnumProperty(name="Control preset", description="Switching preset resets bindings, speed and smoothing",
                          items=[('NAVIGATION', 'Navigation', ''), ('CINEMATIC', 'Cinematic', '')],
                          default='NAVIGATION', update=apply_profile)
    speed: FloatProperty(name="Speed (units/s)", default=3.0, min=.01, max=1000)
    look_speed: FloatProperty(name="Look speed (degrees/s)", default=100, min=5, max=360)
    roll_speed: FloatProperty(name="Roll speed (degrees/s)", default=35, min=1, max=180)
    zoom_speed: FloatProperty(name="Zoom speed (mm/s)", default=30, min=1, max=200)
    move_smoothing: FloatProperty(name="Movement response", default=0, min=0, max=60,
                                  description="Exponential response per second; lower is smoother, zero is instant")
    look_smoothing: FloatProperty(name="Look / roll response", default=0, min=0, max=60)
    zoom_smoothing: FloatProperty(name="Zoom response", default=0, min=0, max=60)
    fast_multiplier: FloatProperty(name="Fast multiplier", default=4, min=1, max=40)
    slow_multiplier: FloatProperty(name="Precision multiplier", default=.2, min=.01, max=1)
    deadzone: FloatProperty(name="Deadzone", default=.15, min=.02, max=.8)
    invert_y: BoolProperty(name="Invert vertical look", default=False)
    invert_triggers: BoolProperty(name="Swap up / down triggers", default=False)
    walk: BoolProperty(name="Horizontal movement (walk)", default=True,
                       description="Horizontal movement; disable to fly. No gravity or collisions")
    reset_lens: FloatProperty(name="Reset lens (mm)", default=50, min=10, max=200)
    status: StringProperty(default="Ready")


for _action, (_label, _navigation, _cinematic) in ACTIONS.items():
    DualSenseSettings.__annotations__['bind_'+_action] = EnumProperty(name=_label, items=BUTTONS, default=_navigation)


class DualSensePosition(bpy.types.PropertyGroup):
    eye: FloatVectorProperty(size=3)
    rotation: FloatVectorProperty(size=4, default=(1, 0, 0, 0))
    lens: FloatProperty(name="Lens (mm)", default=50, min=10, max=200)
    seconds: FloatProperty(name="Travel time (s)", default=3, min=0)


class DualSenseProject(bpy.types.PropertyGroup):
    bookmarks: CollectionProperty(type=DualSensePosition)
    recording: CollectionProperty(type=DualSensePosition)
    index: IntProperty(default=0, min=0)
    source: EnumProperty(name="Path source", items=[('BOOKMARKS', 'Saved positions', ''), ('RECORDING', 'Live recording', '')])
    smooth_path: BoolProperty(name="Ease between saved positions", default=True,
                             description="Smoothstep easing stops at each saved position; live recordings use linear interpolation")
    start_frame: IntProperty(name="First keyframe", default=1, min=-1048574, max=1048574)
    baked_camera: PointerProperty(type=bpy.types.Object)


class VIEW3D_OT_dualsense_navigate(bpy.types.Operator):
    bl_idname = "view3d.dualsense_navigate"
    bl_label = "Start Navigation"
    bl_description = "Navigate with DualSense; Esc always stops"
    _timer = None
    _pad = None
    _finished = False

    def invoke(self, context, event):
        global _active
        if _active:
            self.report({'WARNING'}, "Navigation is already running")
            return {'CANCELLED'}
        if not context.area or context.area.type != 'VIEW_3D' or context.space_data.region_quadviews:
            self.report({'ERROR'}, "Start from a 3D View outside Quad View")
            return {'CANCELLED'}
        settings = context.scene.dualsense_nav
        conflicts = binding_conflicts(settings)
        if conflicts:
            self.report({'ERROR'}, "Duplicate binding: " + conflicts[0])
            return {'CANCELLED'}
        self._area, self._window = context.area, context.window
        self._space, self._rv = context.space_data, context.space_data.region_3d
        self._wm, self._settings = context.window_manager, settings
        self._scene, self._project = context.scene, context.scene.dualsense_project
        self._original = (self._rv.view_location.copy(), self._rv.view_rotation.copy(),
                          self._rv.view_distance, self._rv.view_perspective, self._space.lens)
        self._finished = False
        self._paused, self._previous = False, set()
        self._playing, self._play_paused, self._recording = False, False, False
        try:
            self._motion = Motion(capture_view(self._space))
            self._distance = max(.1, self._rv.view_distance)
            self._pad = WindowsHID()
            self._timer = self._wm.event_timer_add(1/60, window=self._window)
            self._wm.modal_handler_add(self)
            apply_view(self._space, self._motion.pose, self._distance)
        except Exception as exc:
            self.finish(restore=True)
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        self._last = time.monotonic()
        _active = self
        settings.status = "Waiting for controller"
        return {'RUNNING_MODAL'}

    def toggle_recording(self):
        if self._recording:
            self.record_sample(force=True)
            self._recording = False
            return
        if self._playing:
            raise ValueError("Stop path playback before recording")
        self._project.recording.clear()
        self._record_time, self._sample_time = 0.0, 0.0
        self._record_previous = (0.0, self._motion.pose.copy())
        store_pose(self._project.recording, self._motion.pose, 0, "Sample")
        self._recording = True
        self._project.source = 'RECORDING'

    def record_sample(self, force=False):
        if not self._recording:
            return
        fps = self._scene.render.fps/self._scene.render.fps_base
        # Preserve the sampling clock even when timer ticks do not divide FPS.
        # Interpolate between adjacent ticks rather than dropping scheduled frames.
        while self._sample_time+1/fps <= self._record_time+1e-8 and len(self._project.recording) < 18000:
            self._sample_time += 1/fps
            sample = sample_path([self._record_previous, (self._record_time, self._motion.pose)], self._sample_time)
            store_pose(self._project.recording, sample, self._sample_time, "Sample")
        if force and self._record_time > self._project.recording[-1].seconds+1e-6 and len(self._project.recording) < 18000:
            store_pose(self._project.recording, self._motion.pose, self._record_time, "Sample")
        self._record_previous = (self._record_time, self._motion.pose.copy())
        if len(self._project.recording) >= 18000:
            self._recording = False
            self._settings.status = "Recording stopped at 18,000 samples"

    def save_position(self):
        item = store_pose(self._project.bookmarks, self._motion.pose, 3,
                          f"View {len(self._project.bookmarks)+1:02d}")
        self._project.index = len(self._project.bookmarks)-1
        return item

    def recall_position(self, index):
        if not self._project.bookmarks:
            raise ValueError("Save a camera position first")
        self._project.index = index % len(self._project.bookmarks)
        self._playing = False
        self._motion.reset(read_pose(self._project.bookmarks[self._project.index]))
        apply_view(self._space, self._motion.pose, self._distance)

    def toggle_playback(self):
        if self._recording:
            raise ValueError("Stop recording before path playback")
        if self._playing:
            self._play_paused = not self._play_paused
            return
        self._samples = path_samples(self._project)
        validate_path(self._samples)
        self._sample_times = [p[0] for p in self._samples]
        self._smooth_path = self._project.source == 'BOOKMARKS' and self._project.smooth_path
        self._play_time, self._playing, self._play_paused = 0.0, True, False
        self._motion.reset(self._samples[0][1])
        apply_view(self._space, self._motion.pose, self._distance)

    def handle_actions(self, pressed):
        settings = self._settings
        if 'stop' in pressed or 'cancel' in pressed:
            self.finish(restore='cancel' in pressed)
            return
        if 'pause' in pressed:
            self._paused = not self._paused
            self._motion.clear_velocity()
        if 'walk' in pressed:
            settings.walk = not settings.walk
            self._motion.clear_velocity()
        if 'speed_up' in pressed:
            settings.speed *= 1.25
        if 'speed_down' in pressed:
            settings.speed /= 1.25
        if 'reset_lens' in pressed:
            self._motion.pose.lens = settings.reset_lens
            self._motion.zoom_velocity = 0
        if 'reset_horizon' in pressed:
            self._motion.reset_horizon()
        if 'add_bookmark' in pressed:
            self.save_position()
        if 'previous' in pressed:
            self.recall_position(self._project.index-1)
        if 'next' in pressed:
            self.recall_position(self._project.index+1)
        if 'stop_play' in pressed:
            self._playing = False
            self._motion.clear_velocity()
        if 'play' in pressed:
            self.toggle_playback()
        if 'record' in pressed:
            self.toggle_recording()

    def step(self, state, dt):
        settings = self._settings
        lx, ly = radial_deadzone(state.lx, state.ly, settings.deadzone)
        rx, ry = radial_deadzone(state.rx, state.ry, settings.deadzone)
        vertical = (state.r2 if state.r2 > .05 else 0)-(state.l2 if state.l2 > .05 else 0)
        if settings.invert_triggers:
            vertical = -vertical
        held = mapped_actions(settings, state.buttons)
        manual = any(abs(x) > 1e-6 for x in (lx, ly, rx, ry, vertical)) or bool(held & {'zoom_in', 'zoom_out', 'roll_left', 'roll_right'})
        if self._playing and manual:
            self._playing = False
            self._motion.clear_velocity()
        if self._playing:
            if not self._play_paused:
                self._play_time = min(self._samples[-1][0], self._play_time+dt)
                self._motion.reset(sample_path(self._samples, self._play_time, self._smooth_path, self._sample_times))
                if self._play_time >= self._samples[-1][0]:
                    self._playing = False
        else:
            self._motion.step((lx, ly, rx, ry, vertical), held, settings, dt)
        apply_view(self._space, self._motion.pose, self._distance)
        if self._recording:
            self._record_time += dt
            self.record_sample()

    def modal(self, context, event):
        if self._finished:
            return {'FINISHED'}
        if event.type == 'ESC' and event.value == 'PRESS':
            self.finish()
            return {'FINISHED'}
        if event.type != 'TIMER':
            return {'PASS_THROUGH'}
        try:
            if (self._area not in self._window.screen.areas[:] or self._area.type != 'VIEW_3D'
                    or self._area.spaces.active != self._space or self._window.scene != self._scene):
                self.finish()
                return {'FINISHED'}
            now = time.monotonic()
            dt, self._last = min(now-self._last, .05), now
            state = self._pad.poll()
            foreground = C.windll.user32.GetForegroundWindow
            foreground.restype = W.HWND
            process_id = W.DWORD()
            C.windll.user32.GetWindowThreadProcessId.argtypes = [W.HWND, C.POINTER(W.DWORD)]
            C.windll.user32.GetWindowThreadProcessId(foreground(), C.byref(process_id))
            focused = process_id.value == os.getpid() and context.window == self._window
            under_mouse = any(r.type == 'WINDOW' and r.x <= event.mouse_x < r.x+r.width
                              and r.y <= event.mouse_y < r.y+r.height for r in self._area.regions)
            if not focused or not under_mouse or not state.transport:
                self._previous = state.buttons.copy()
                self._motion.clear_velocity()
                self._settings.status = self._pad.status if not state.transport else "Paused - move the pointer into the 3D View"
                self._area.tag_redraw()
                return {'PASS_THROUGH'}
            conflicts = binding_conflicts(self._settings)
            if conflicts:
                self._motion.clear_velocity()
                self._settings.status = "Duplicate binding: " + conflicts[0]
                return {'PASS_THROUGH'}
            pressed = mapped_actions(self._settings, state.buttons-self._previous)
            self._previous = state.buttons.copy()
            if abs(self._space.lens-self._motion.pose.lens) > 1e-4:
                self._motion.pose.lens = self._space.lens
                self._motion.zoom_velocity = 0.0
            try:
                self.handle_actions(pressed)
            except ValueError as exc:
                self.report({'WARNING'}, str(exc))
            if self._finished:
                return {'FINISHED'}
            if not self._paused:
                self.step(state, dt)
            else:
                apply_view(self._space, self._motion.pose, self._distance)
            suffix = " | Paused" if self._paused else " | Recording" if self._recording else " | Path paused" if self._playing and self._play_paused else " | Playing" if self._playing else ""
            self._settings.status = self._pad.status + suffix
            self._area.header_text_set(f"DualSense | {self._settings.profile.title()} | {self._motion.pose.lens:.1f} mm | Esc: stop" + suffix)
            self._area.tag_redraw()
            return {'PASS_THROUGH'}
        except Exception as exc:
            self.finish()
            self.report({'ERROR'}, "DualSense: " + str(exc))
            return {'CANCELLED'}

    def finish(self, restore=False):
        global _active
        if self._finished:
            return
        self._finished = True
        if getattr(self, '_recording', False):
            self.record_sample(force=True)
            self._recording = False
        if self._pad:
            self._pad.close()
            self._pad = None
        if self._timer:
            self._wm.event_timer_remove(self._timer)
            self._timer = None
        try:
            if restore:
                self._rv.view_location, self._rv.view_rotation, self._rv.view_distance, self._rv.view_perspective, self._space.lens = self._original
            self._area.header_text_set(None)
            self._area.tag_redraw()
            self._settings.status = "Stopped"
        except (ReferenceError, AttributeError):
            pass
        _active = None

    def cancel(self, context):
        self.finish()


class VIEW3D_OT_dualsense_stop(bpy.types.Operator):
    bl_idname = "view3d.dualsense_stop"
    bl_label = "Stop Navigation"

    def execute(self, context):
        if _active:
            _active.finish()
        return {'FINISHED'}


class VIEW3D_OT_dualsense_camera(bpy.types.Operator):
    bl_idname = "view3d.dualsense_camera"
    bl_label = "DualSense Camera"
    bl_options = {'REGISTER', 'UNDO'}
    action: EnumProperty(items=[(s, label, '') for s, label in (
        ('ADD', 'Save Position'), ('UPDATE', 'Replace Position'), ('RECALL', 'Recall Position'),
        ('REMOVE', 'Delete Position'), ('UP', 'Move Earlier'), ('DOWN', 'Move Later'),
        ('PLAY', 'Play / Pause Path'), ('STOP_PLAY', 'Stop Path'), ('RECORD', 'Start / Stop Recording'),
        ('CLEAR_RECORD', 'Clear Recording'), ('BAKE', 'Bake to New Camera'), ('USE_CAMERA', 'Use Baked Camera'),
        ('HORIZON', 'Level Horizon'), ('LENS', 'Reset FOV'))])

    @classmethod
    def poll(cls, context):
        return context.area and context.area.type == 'VIEW_3D' and not context.space_data.region_quadviews

    def execute(self, context):
        project, settings, space = context.scene.dualsense_project, context.scene.dualsense_nav, context.space_data
        if _active and (_active._space != space or _active._scene != context.scene):
            self.report({'ERROR'}, "Stop navigation in the other viewport first")
            return {'CANCELLED'}
        try:
            active = _active
            pose = active._motion.pose.copy() if active else capture_view(space)
            index = min(project.index, len(project.bookmarks)-1)
            if self.action in {'UPDATE', 'RECALL', 'REMOVE', 'UP', 'DOWN'} and index < 0:
                raise ValueError("Save a camera position first")
            if self.action == 'ADD':
                store_pose(project.bookmarks, pose, 3, f"View {len(project.bookmarks)+1:02d}")
                project.index = len(project.bookmarks)-1
            elif self.action == 'UPDATE':
                item = project.bookmarks[index]
                item.eye, item.rotation, item.lens = pose.eye, pose.rotation, pose.lens
            elif self.action == 'RECALL':
                if active:
                    active.recall_position(index)
                else:
                    apply_view(space, read_pose(project.bookmarks[index]), max(.1, space.region_3d.view_distance))
            elif self.action == 'REMOVE':
                project.bookmarks.remove(index)
                project.index = max(0, index-1)
            elif self.action in {'UP', 'DOWN'}:
                target = max(0, min(len(project.bookmarks)-1, index+(-1 if self.action == 'UP' else 1)))
                project.bookmarks.move(index, target)
                project.index = target
            elif self.action in {'HORIZON', 'LENS'}:
                motion = active._motion if active else Motion(pose)
                if self.action == 'HORIZON':
                    motion.reset_horizon()
                else:
                    motion.pose.lens, motion.zoom_velocity = settings.reset_lens, 0.0
                apply_view(space, motion.pose, max(.1, space.region_3d.view_distance))
            elif self.action == 'BAKE':
                if active and active._recording:
                    raise ValueError("Stop recording before baking")
                camera, end = bake_camera(context.scene, project)
                self.report({'INFO'}, f"Created {camera.name}: frames {project.start_frame}-{end}")
            elif self.action == 'USE_CAMERA':
                if not project.baked_camera or project.baked_camera.type != 'CAMERA':
                    raise ValueError("Bake a camera first")
                if active:
                    active.finish()
                context.scene.camera = project.baked_camera
                space.camera = project.baked_camera
                space.region_3d.view_perspective = 'CAMERA'
            elif self.action == 'CLEAR_RECORD':
                if active and active._recording:
                    raise ValueError("Stop recording before clearing it")
                project.recording.clear()
            else:
                if not active:
                    raise ValueError("Start Navigation first")
                if self.action == 'PLAY':
                    active.toggle_playback()
                elif self.action == 'STOP_PLAY':
                    active._playing = False
                    active._motion.clear_velocity()
                elif self.action == 'RECORD':
                    active.toggle_recording()
            context.area.tag_redraw()
            return {'FINISHED'}
        except ValueError as exc:
            self.report({'WARNING'}, str(exc))
            return {'CANCELLED'}


class VIEW3D_UL_dualsense_positions(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.prop(item, 'name', text='', emboss=False, icon='CAMERA_DATA')


def camera_button(layout, action, label, icon='NONE'):
    layout.operator('view3d.dualsense_camera', text=label, icon=icon).action = action


class VIEW3D_PT_dualsense(bpy.types.Panel):
    bl_label = "DualSense Navigator"
    bl_idname = "VIEW3D_PT_dualsense"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "DualSense"

    def draw(self, context):
        layout, settings = self.layout, context.scene.dualsense_nav
        layout.operator('view3d.dualsense_stop' if _active else 'view3d.dualsense_navigate', icon='PAUSE' if _active else 'PLAY')
        layout.label(text=settings.status)
        layout.prop(settings, 'profile')
        for name in ('speed', 'look_speed', 'deadzone', 'walk', 'invert_y', 'invert_triggers'):
            layout.prop(settings, name)
        layout.label(text="Left: move | Right: look | L2/R2: down/up")
        layout.label(text="Esc always stops | No collisions")


class VIEW3D_PT_dualsense_motion(bpy.types.Panel):
    bl_label = "Smoothing, FOV and Roll"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "DualSense"
    bl_parent_id = 'VIEW3D_PT_dualsense'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout, settings = self.layout, context.scene.dualsense_nav
        for name in ('move_smoothing', 'look_smoothing', 'zoom_smoothing', 'fast_multiplier',
                     'slow_multiplier', 'zoom_speed', 'roll_speed', 'reset_lens'):
            layout.prop(settings, name)
        layout.prop(context.space_data, 'lens', text='Current lens (mm)')
        layout.label(text="Response: 0 instant; lower = smoother")
        row = layout.row(align=True)
        camera_button(row, 'HORIZON', 'Level Horizon')
        camera_button(row, 'LENS', 'Reset FOV')


class VIEW3D_PT_dualsense_bindings(bpy.types.Panel):
    bl_label = "Button Bindings"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "DualSense"
    bl_parent_id = 'VIEW3D_PT_dualsense'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        settings = context.scene.dualsense_nav
        for conflict in binding_conflicts(settings):
            self.layout.label(text=conflict, icon='ERROR')
        for action in ACTIONS:
            self.layout.prop(settings, 'bind_'+action)


class VIEW3D_PT_dualsense_camera(bpy.types.Panel):
    bl_label = "Camera Positions and Recording"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "DualSense"
    bl_parent_id = 'VIEW3D_PT_dualsense'

    def draw(self, context):
        layout, project = self.layout, context.scene.dualsense_project
        layout.template_list('VIEW3D_UL_dualsense_positions', '', project, 'bookmarks', project, 'index', rows=3)
        row = layout.row(align=True)
        camera_button(row, 'ADD', 'Save', 'ADD')
        camera_button(row, 'RECALL', 'Recall')
        camera_button(row, 'REMOVE', '', 'REMOVE')
        row = layout.row(align=True)
        camera_button(row, 'UPDATE', 'Replace')
        camera_button(row, 'UP', '', 'TRIA_UP')
        camera_button(row, 'DOWN', '', 'TRIA_DOWN')
        if project.bookmarks and project.index < len(project.bookmarks):
            layout.prop(project.bookmarks[project.index], 'seconds')
        layout.prop(project, 'source')
        layout.prop(project, 'smooth_path')
        row = layout.row(align=True)
        camera_button(row, 'PLAY', 'Play / Pause', 'PLAY')
        camera_button(row, 'STOP_PLAY', 'Stop', 'PAUSE')
        row = layout.row(align=True)
        camera_button(row, 'RECORD', 'Stop Recording' if _active and _active._recording else 'Record New Take', 'REC')
        camera_button(row, 'CLEAR_RECORD', '', 'TRASH')
        duration = project.recording[-1].seconds if project.recording else 0
        layout.label(text=f"Recording: {len(project.recording)} samples / {duration:.2f} s")
        layout.label(text="Record New Take replaces the previous take")
        layout.prop(project, 'start_frame')
        camera_button(layout, 'BAKE', 'Bake to New Camera', 'CAMERA_DATA')
        if project.baked_camera:
            layout.label(text=project.baked_camera.name)
            camera_button(layout, 'USE_CAMERA', 'Use Baked Camera')
        layout.label(text="Save the .blend to keep positions and recordings")


CLASSES = (DualSenseSettings, DualSensePosition, DualSenseProject,
           VIEW3D_OT_dualsense_navigate, VIEW3D_OT_dualsense_stop, VIEW3D_OT_dualsense_camera,
           VIEW3D_UL_dualsense_positions, VIEW3D_PT_dualsense, VIEW3D_PT_dualsense_motion,
           VIEW3D_PT_dualsense_bindings, VIEW3D_PT_dualsense_camera)


@persistent
def stop_before_data_change(*args):
    if _active:
        _active.finish()


def register():
    previous = bpy.app.driver_namespace.get('dualsense_navigator_unregister')
    if previous and previous is not unregister:
        previous()
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.dualsense_nav = PointerProperty(type=DualSenseSettings)
    bpy.types.Scene.dualsense_project = PointerProperty(type=DualSenseProject)
    bpy.app.driver_namespace['dualsense_navigator_unregister'] = unregister
    bpy.app.handlers.load_pre.append(stop_before_data_change)
    bpy.app.handlers.undo_pre.append(stop_before_data_change)


def unregister():
    if _active:
        _active.finish()
    for handlers in (bpy.app.handlers.load_pre, bpy.app.handlers.undo_pre):
        if stop_before_data_change in handlers:
            handlers.remove(stop_before_data_change)
    for name in ('dualsense_nav', 'dualsense_project'):
        if hasattr(bpy.types.Scene, name):
            delattr(bpy.types.Scene, name)
    for cls in reversed(CLASSES):
        if hasattr(cls, 'bl_rna'):
            bpy.utils.unregister_class(cls)
    bpy.app.driver_namespace.pop('dualsense_navigator_unregister', None)
