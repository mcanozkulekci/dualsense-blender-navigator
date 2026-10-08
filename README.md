# DualSense Blender Navigator

A Windows extension for exploring Blender's 3D viewport and planning camera shots
with a PS5 DualSense controller. Reads USB and Bluetooth HID input directly, with
no additional Python packages or drivers.

Version **1.1.0** adds movement/look/zoom smoothing, FOV and roll controls,
customizable button bindings, a cinematic preset, saved camera positions,
path playback, live recording, and camera transform/lens keyframe baking.

## Installation

1. Download [dualsense_navigator-1.1.0.zip](packages/dualsense_navigator-1.1.0.zip?raw=1).
2. In Blender, open **Edit > Preferences > Add-ons > menu > Install from Disk**.
3. Select the ZIP and enable **DualSense Navigator**. Use the same extension
   repository when updating an older installation.
4. If automatic preference saving is disabled, click **Save Preferences**.
5. In the 3D viewport, open **N > DualSense > Start Navigation**.

Keep the pointer inside the viewport's main drawing region. Navigation and recording
pause when Blender loses focus, the pointer moves into the sidebar/outside the
viewport, or controller input becomes stale. Enabling the extension does not start
navigation. **Esc always stops**, regardless of custom bindings.

## Control presets

Left stick moves and strafes; right stick looks around. L2 moves down and R2 moves
up in both presets; **Swap up / down triggers** reverses them.

| Control | Navigation | Cinematic |
|---|---|---|
| L1 / R1 | Precision / fast movement (hold) | Previous / next saved position (press) |
| Square / Triangle | Save position / toggle walk-flight (press) | Precision / fast movement (hold) |
| D-pad up / down | Increase / decrease speed (press) | Narrow / widen FOV (hold) |
| D-pad left / right | Roll left / right (hold) | Roll left / right (hold) |
| Cross (X) | Pause / resume navigation | Save camera position |
| Circle | Restore starting view and stop | Reset FOV |
| R3 | Level horizon | Level horizon |
| L3 | Unassigned | Pause / resume navigation |
| Options | Stop navigation | Play / pause selected camera path |
| Create | Stop camera path | Stop camera path |
| Touchpad click | Start / stop a new recording | Start / stop a new recording |
| Mute | Unassigned | Stop navigation |
| Esc | Stop navigation | Stop navigation |

**Control preset** resets bindings, movement/look speed, walk-flight mode and
smoothing when switched. Navigation starts with instant response; Cinematic starts
with slower flight and smoothing. Open **Button Bindings** to customize individual
actions or leave them unassigned. Duplicate assignments prevent navigation until
resolved. Sticks and trigger axes retain their fixed roles.

## Smoothing, FOV and roll

Open **Smoothing, FOV and Roll** to set independent movement, look/roll and zoom
responses. **0 disables smoothing**; a positive lower value gives a longer settling
time. Velocity smoothing uses elapsed time and an analytic integral rather than
a fixed blend per frame. Focus loss, pause and stale input clear pending velocity.

Zoom changes the viewport lens between **10 and 200 mm**: a longer lens narrows
FOV. You can also edit **Current lens**, use **Reset FOV**, set the reset lens value,
or **Level Horizon** without moving the camera position. Roll does not alter the
viewing direction. Fast and precision multipliers affect translation only.

## Saved positions and camera paths

1. Choose **Cinematic**, start navigation, and move to your first shot.
2. Press **Cross** or **Save** to store position, rotation and lens. Repeat at the
   next shot; L1/R1 recalls previous/next saved positions.
3. In **Camera Positions and Recording**, rename, replace, delete or reorder views.
   Each view after the first has a **Travel time (s)** from the preceding view.
4. Set **Path source > Saved positions**. Use **Play / Pause** or Options to preview.
   **Ease between saved positions** gives smooth starts/stops at each view.
5. Set **First keyframe**, then **Bake to New Camera**. This creates a new camera
   with position, quaternion rotation and lens keys at the scene's FPS.
6. Optionally click **Use Baked Camera** to make that camera the scene camera.

Playback requires navigation to be running. Manual stick, trigger, roll or zoom
input interrupts playback. Create/Stop Path leaves the view at its current position.
The path interpolates straight segments with shortest-arc rotations; easing stops
at nodes. It does not provide spline curves or constant world-space speed.

## Live recording

Start navigation, then click **Record New Take** or press the touchpad. Move freely,
then press it again to stop. **Starting a new take replaces the previous live take**;
saved positions remain available. Select **Path source > Live recording** to replay
or bake the take. Recording and playback cannot run at the same time.

Recording samples position, rotation and lens at the scene FPS, interpolating between
navigation ticks and retaining the final sample. The clock counts active navigation
time; focus loss, navigation pause, stale input and long timer stalls do not add
jumps to the path. Live recordings use linear interpolation. Recordings are limited
to 18,000 samples; camera bakes are limited to 36,000 frames.

Settings, custom bindings, saved positions and live recordings belong to the scene.
**Save the `.blend` file to keep them.** Loading a file, changing scenes, undoing,
disabling the extension or stopping navigation closes the controller/timer. Viewport
navigation and previews leave scene cameras untouched. Baking creates fresh animation
each time and preserves existing cameras, actions, active camera and timeline range.
Output framing also depends on the render aspect ratio; inspect the baked Camera View.

## Compatibility and validation

- Target: Windows x64 and Blender 4.2 or later.
- Tested: Blender 5.2.2 LTS with a standard DualSense over enhanced Bluetooth HID.
- Automated checks cover HID parsing, motion, smoothing, bindings, camera path
  playback, live sampling, baking and `.blend` persistence.
- Installation, disable/enable, saved-profile reload and separate GUI modal tests
  are described in [testing notes](docs/testing.md).
- Physical USB, DualSense Edge, every physical button and other Blender versions
  have not been tested. Control feel still needs hands-on validation.
- With multiple controllers, the first accessible device is used. Quad View,
  gravity and collision detection are unsupported. Leave an orthographic Camera
  View before starting navigation.
- If Steam Input or HidHide hides the device, allow the extension to access it.

## Development

HID input: `__init__.py`; motion/path math: `motion.py`; camera storage/baking:
`cinema.py`; Blender properties/operators/sidebar: `ui.py`.

```powershell
.\scripts\build.ps1 -BlenderExe 'C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe'
.\scripts\test.ps1 -BlenderExe 'C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe'
.\scripts\test-gui.ps1 -BlenderExe 'C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe'
```

The build script builds and validates the extension ZIP and copies it to `packages/`.
Tests use pre-created `.test-profile` directories and refuse to save preferences if
Blender resolves the normal configuration directory. GUI tests leave a separate test
scene open with navigation stopped. Evidence and the demo `.blend` go to `test-output/`.

## License and references

GPL-3.0-or-later; see [LICENSE](LICENSE).

- [DualSense HID report map](https://github.com/nondebug/dualsense/blob/main/README.md)
- [PlayStation HID driver](https://github.com/torvalds/linux/blob/master/drivers/hid/hid-playstation.c)
- [Microsoft HID input documentation](https://learn.microsoft.com/en-us/windows-hardware/drivers/hid/obtaining-hid-reports)
