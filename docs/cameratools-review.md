# Cyberpunk CameraTools v1.0.44: gamepad review

Reviewed on 2026-10-09 using the local package's `Readme.txt`, `IGCSClientSettings.ini`
and static UI labels from the client executable. No EXE/DLL was executed or injected
into the game, and no CameraTools settings were changed. This review considers
independent implementations in Blender.

## Observed configuration

| Setting | Local value | Relevance to Blender |
|---|---:|---|
| `MovementSpeed` | 0.04 | Game-specific scale; not directly equivalent to Blender units/second |
| `RotationSpeed` | 0.04 | Blender needs a separate degrees/second setting |
| `FastMovementMultiplier` | 20 | The current Blender extension uses 4x; could be configurable |
| `SlowMovementMultiplier` | 0.1 | The current Blender extension uses 0.2x |
| `UpMovementMultiplier` | 0.7 | A separate vertical speed multiplier would be useful |
| `InterpolationFactorMovement` | 8 | Movement smoothing enabled |
| `InterpolationFactorRotation` | 8 | Look smoothing enabled |
| `InterpolationFactorFoV` | 1 | No additional FOV smoothing |
| `FoVZoomSpeed` | 0.4217879 | Separate zoom speed |
| `InvertYLookDirection` | False | Vertical look not inverted |
| Movement / rotation stick selection | 0 / 1 | Left stick moves; right stick rotates |
| Up / down trigger selection | 0 / 1 | Left trigger moves up; right trigger moves down |
| Movement/rotation shake frequency and strength | All 0 | Shake disabled in the observed profile |

The file contains `CameraControlDevice=1`; its numeric enum value was not established
from the INI alone. Documentation describes controller, keyboard/mouse and combined
modes. Interpolation values are not milliseconds; copying them into Blender would
not necessarily produce the same response.

## Gamepad layout

The local action bindings, client button-label order and official control table
indicate the following layout. DualSense equivalents refer to physical button positions;
native DualSense USB/Bluetooth support in CameraTools was not tested at runtime.

| Action | Xbox control | DualSense equivalent |
|---|---|---|
| Fast / slow movement | Y / X | Triangle / Square |
| Narrow / widen FOV | D-pad up / down | Same |
| Reset FOV | B | Circle |
| Roll left / right | D-pad left / right | Same |
| Add camera path node | A | Cross |
| Previous / next node | LB / RB | L1 / R1 |
| Play/pause path | Start | Options |
| Stop path | Back | Create |
| Toggle game speed mode | Left stick press | L3; modifier behavior not tested at runtime |

The Blender extension currently uses the opposite trigger direction: **L2 moves down,
R2 moves up**. A separate CameraTools-style profile would avoid changing existing
controls unexpectedly. Cross pause, Options stop, L1/R1 speed and D-pad speed bindings
currently conflict with the proposed camera path and FOV controls.

The local v1.0.19 changelog states that the fast movement multiplier no longer affects
rotation. The current general control table uses broader wording; this review gives
the installed version's changelog precedence. Slow look and fast movement multipliers
could be designed separately.

## Potential Blender features

| Priority | Feature | Implementation and limits |
|---|---|---|
| 1 | Separate movement/look/FOV smoothing | Frame-rate-independent input filters; clear pending motion immediately on disconnect |
| 1 | Configurable bindings and profiles | Navigation/cinematic modes, left-handed stick swap, trigger direction and conflict checking |
| 1 | FOV zoom and reset | Viewport lens control; changing a scene camera lens should require an explicit mode |
| 1 | Roll and horizon reset | D-pad left/right and R3 reset are possible bindings; replace the current per-frame horizon lock |
| 1 | Configurable fast/slow/vertical speed | Store values such as 20x, 0.1x and 0.7 in profiles; calibrate speeds for Blender units |
| 2 | Three camera bookmarks | Store view position, rotation and lens in Scene properties so they travel with the .blend file |
| 2 | Node-based camera paths | Add/browse/play nodes with the controller; generate transform and lens keyframes on a Camera object |
| 2 | Path easing and constant speed | Resample by path length; evenly spaced keyframes alone do not produce constant world-space speed |
| 3 | Separate movement/rotation shake | Seeded procedural noise; optional and disabled by default |
| 3 | Time control and frame stepping | Blender timeline and animation playback controls, not a direct equivalent of global game timescale |
| 3 | HUD/overlay visibility | Viewport overlays and gizmos; not the entire Blender interface or render resolution |

Recommended first step: **smoothing, FOV, roll and configurable cinematic controls**.
Next: **bookmarks and controller-driven camera path/keyframe recording**.
Manual navigation must not overwrite camera transforms during path playback.

## Features without a direct equivalent

Blender's equivalent of hotsampling is render resolution, not resizing a game window.
Wetness and puddles depend on shaders; time of day depends on a lighting rig;
head/body/eye look-at depends on a character rig. These do not translate into universal
sliders in a viewport navigation extension. The local v1.0.33 changelog says CyberLit
was separated from the main tool; an older feature list calling it integrated does
not establish that it is built into this v1.0.44 package.

## Evidence and references

Local file SHA256 values; vendor files are not distributed here:

- `Readme.txt`: `405893a7cf51c9e7dba2532ae09188c736f88aeb85d1c3a58f581f2f2906b3c7`
- `IGCSClientSettings.ini`: `e1c4385c9f2efbf71cfbf6181d3f68c176b1965700d3f225c550f5a266027ae7`

Official documentation may describe newer versions. Claims about the installed
v1.0.44 package are limited by the local configuration and changelog. The proposed
Blender features are implementation ideas, not transferred CameraTools source code,
and have not been implemented in the extension.

- [General configuration and controls](https://opm.fransbouma.com/generalconfiguration.htm)
- [Camera paths](https://opm.fransbouma.com/camerapaths.htm)
- [Cyberpunk features and CyberLit separation](https://opm.fransbouma.com/Cameras/cyberpunk2077.htm)
