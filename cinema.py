"""Scene storage and explicit, non-destructive camera animation baking."""
import math
import bpy
from mathutils import Quaternion, Vector
from .motion import Pose, sample_path


def read_pose(item):
    return Pose(Vector(item.eye), Quaternion(item.rotation).normalized(), item.lens)


def store_pose(collection, pose, seconds=0.0, name="View"):
    item = collection.add()
    item.name = name
    item.eye, item.rotation, item.lens, item.seconds = pose.eye, pose.rotation, pose.lens, seconds
    return item


def capture_view(space):
    rv = space.region_3d
    scene_camera = space.camera or bpy.context.scene.camera
    if rv.view_perspective == 'CAMERA' and scene_camera:
        camera = scene_camera.evaluated_get(bpy.context.evaluated_depsgraph_get())
        if camera.data.type != 'PERSP':
            raise ValueError("Use a perspective camera or leave Camera View first")
        return Pose(camera.matrix_world.translation.copy(), camera.matrix_world.to_quaternion(), camera.data.lens)
    q = rv.view_rotation.copy()
    return Pose(rv.view_location + q @ Vector((0, 0, rv.view_distance)), q, space.lens)


def apply_view(space, pose, distance):
    rv = space.region_3d
    rv.view_perspective = 'PERSP'
    rv.view_rotation = pose.rotation
    rv.view_distance = distance
    rv.view_location = pose.eye - pose.rotation @ Vector((0, 0, distance))
    space.lens = pose.lens


def path_samples(project):
    if project.source == 'RECORDING':
        return [(p.seconds, read_pose(p)) for p in project.recording]
    seconds, samples = 0.0, []
    for index, item in enumerate(project.bookmarks):
        if index:
            seconds += item.seconds
        samples.append((seconds, read_pose(item)))
    return samples


def validate_path(samples):
    if len(samples) < 2:
        raise ValueError("At least two camera positions are required")
    if any(b[0] <= a[0] for a, b in zip(samples, samples[1:])):
        raise ValueError("Camera sample times must increase")


def bake_camera(scene, project):
    samples = path_samples(project)
    validate_path(samples)
    fps = scene.render.fps / scene.render.fps_base
    duration = samples[-1][0]
    frames = max(1, math.ceil(duration*fps))
    if frames > 36000:
        raise ValueError("Path exceeds the 36,000 frame bake limit; reduce the duration")
    if project.start_frame+frames > 1048574:
        raise ValueError("Path exceeds Blender's maximum frame number")
    times = [p[0] for p in samples]
    data = bpy.data.cameras.new("DualSense Camera")
    camera = bpy.data.objects.new("DualSense Camera", data)
    scene.collection.objects.link(camera)
    camera.rotation_mode = 'QUATERNION'
    data.sensor_width = 32.0
    data.sensor_fit = 'HORIZONTAL'
    # Create a new object/action on every bake. Never clear an existing action.
    try:
        previous = None
        for offset in range(frames+1):
            pose = sample_path(samples, min(offset/fps, duration),
                               project.source == 'BOOKMARKS' and project.smooth_path, times)
            q = pose.rotation
            if previous is not None and previous.dot(q) < 0:
                q.negate()
            previous = q.copy()
            camera.location, camera.rotation_quaternion, data.lens = pose.eye, q, pose.lens
            frame = project.start_frame + offset
            camera.keyframe_insert(data_path="location", frame=frame, group="DualSense")
            camera.keyframe_insert(data_path="rotation_quaternion", frame=frame, group="DualSense")
            data.keyframe_insert(data_path="lens", frame=frame, group="DualSense")
        # Sampled curves use linear interpolation rather than Bezier overshoot.
        for owner in (camera, data):
            animation = owner.animation_data
            action = animation.action
            if hasattr(action, 'fcurves'):
                curves = action.fcurves
            else:
                curves = action.layers[0].strips[0].channelbag(animation.action_slot).fcurves
            for curve in curves:
                for point in curve.keyframe_points:
                    point.interpolation = 'LINEAR'
        project.baked_camera = camera
        # Evaluate at the user's current frame without moving the timeline.
        scene.frame_set(scene.frame_current, subframe=scene.frame_subframe)
        return camera, project.start_frame+frames
    except Exception:
        bpy.data.objects.remove(camera, do_unlink=True)
        bpy.data.cameras.remove(data)
        raise
