"""Viewport-independent motion and camera path sampling."""
from dataclasses import dataclass
from bisect import bisect_right
import math
from mathutils import Matrix, Quaternion, Vector


def orientation(yaw, pitch, roll=0.0):
    forward = Vector((math.cos(pitch)*math.cos(yaw), math.cos(pitch)*math.sin(yaw), math.sin(pitch)))
    right = Vector((math.sin(yaw), -math.cos(yaw), 0))
    up = right.cross(forward)
    return Matrix((right, up, -forward)).transposed().to_quaternion() @ Quaternion((0, 0, 1), roll)


def integrate_velocity(previous, target, response, dt):
    """Exact integral of exponential velocity smoothing for a constant target.

    Response is inverse seconds; zero disables smoothing. Unlike lerp-per-frame,
    both velocity and distance are independent of the timer frequency.
    """
    if response <= 0:
        return target, target * dt
    blend = -math.expm1(-response * dt)
    return previous + (target-previous)*blend, target*dt + (previous-target)*(blend/response)


@dataclass
class Pose:
    eye: Vector
    rotation: Quaternion
    lens: float

    def copy(self):
        return Pose(self.eye.copy(), self.rotation.copy(), self.lens)


class Motion:
    def __init__(self, pose):
        self.pose = pose.copy()
        self.reset(pose)

    def clear_velocity(self):
        self.velocity = Vector((0, 0, 0))
        self.look_velocity = Vector((0, 0, 0))
        self.zoom_velocity = 0.0

    def reset(self, pose):
        self.pose = pose.copy()
        forward = pose.rotation @ Vector((0, 0, -1))
        self.yaw = math.atan2(forward.y, forward.x)
        self.pitch = math.asin(max(-1, min(1, forward.z)))
        relative = orientation(self.yaw, self.pitch).inverted() @ pose.rotation
        self.roll = relative.to_euler('XYZ').z
        self.clear_velocity()

    def reset_horizon(self):
        self.roll = 0.0
        self.look_velocity.z = 0.0
        self.pose.rotation = orientation(self.yaw, self.pitch)

    def step(self, axes, held, settings, dt):
        # axes have already passed the radial deadzone; held contains action IDs.
        lx, ly, rx, ry, vertical = axes
        look_target = Vector((-rx, ry*(1 if settings.invert_y else -1),
                              float('roll_right' in held)-float('roll_left' in held)))
        look_target.x *= math.radians(settings.look_speed)
        look_target.y *= math.radians(settings.look_speed)
        look_target.z *= math.radians(settings.roll_speed)
        self.look_velocity, delta = integrate_velocity(self.look_velocity, look_target, settings.look_smoothing, dt)
        self.yaw += delta.x
        self.pitch = max(math.radians(-89), min(math.radians(89), self.pitch + delta.y))
        self.roll = (self.roll + delta.z + math.pi) % (2*math.pi) - math.pi
        self.pose.rotation = orientation(self.yaw, self.pitch, self.roll)
        q = self.pose.rotation
        forward, right = q @ Vector((0, 0, -1)), q @ Vector((1, 0, 0))
        if settings.walk:
            forward = Vector((math.cos(self.yaw), math.sin(self.yaw), 0))
            right = Vector((math.sin(self.yaw), -math.cos(self.yaw), 0))
        direction = right*lx - forward*ly + Vector((0, 0, vertical))
        if direction.length > 1:
            direction.normalize()
        multiplier = settings.slow_multiplier if 'slow' in held else settings.fast_multiplier if 'fast' in held else 1
        target = direction * settings.speed * multiplier
        self.velocity, distance = integrate_velocity(self.velocity, target, settings.move_smoothing, dt)
        self.pose.eye += distance
        zoom_target = (float('zoom_in' in held)-float('zoom_out' in held))*settings.zoom_speed
        self.zoom_velocity, zoom = integrate_velocity(self.zoom_velocity, zoom_target, settings.zoom_smoothing, dt)
        self.pose.lens = max(10.0, min(200.0, self.pose.lens + zoom))
        return self.pose


def sample_path(samples, seconds, smooth=False, times=None):
    """Sample (time, Pose) pairs with shortest-arc quaternion interpolation."""
    if not samples:
        raise ValueError("No camera samples")
    if seconds <= samples[0][0]:
        return samples[0][1].copy()
    if seconds >= samples[-1][0]:
        return samples[-1][1].copy()
    index = bisect_right(times if times is not None else [p[0] for p in samples], seconds)
    ta, a = samples[index-1]
    tb, b = samples[index]
    t = max(0, min(1, (seconds-ta)/max(1e-9, tb-ta)))
    if smooth:
        t = t*t*(3-2*t)
    rotation = b.rotation.copy()
    if a.rotation.dot(rotation) < 0:
        rotation.negate()
    return Pose(a.eye.lerp(b.eye, t), a.rotation.slerp(rotation, t), a.lens+(b.lens-a.lens)*t)
