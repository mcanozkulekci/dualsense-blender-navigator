# Tested scope: 1.1.0

Test environment: Windows x64, Blender 5.2.2 LTS, standard DualSense; 2026-10-09.

- **76 runtime checks** cover USB/basic Bluetooth/enhanced Bluetooth parsing, CRC,
  radial deadzone, stale input/reconnect and real RegionView3D motion geometry.
  Motion checks include 30/120 Hz smoothing consistency, translation, look, roll,
  zoom limits/reset, preset conflicts and trigger reversal.
- Scene workflow checks cover saved positions, path interpolation/pause/manual
  interruption, shortest-arc quaternion rotation, 24 FPS recording on a 60 Hz
  timer, transform/lens baking, preservation of existing animation and scene camera,
  invalid/excessive paths, sidebar operators and `.blend` persistence of custom
  bindings, positions and recordings.
- Live enhanced Bluetooth reports were read successfully in background and GUI tests.
- **20 GUI checks** exercise the installed ZIP in a separate interactive Blender:
  real modal start/timer/stop/restart, pointer/window guards, unconditional Esc,
  saved positions, playback/pause, recording, baking, full cancel restoration and
  data-change cleanup. Scripted camera actions provide repeatable assertions;
  these do not establish hands-on coverage of every physical button.
- Blender's extension build and validation tools passed. Install from Disk,
  disable/enable and reload from saved isolated preferences passed.

A USB parser test does not establish physical USB compatibility. The DualSense Edge
ID is recognized, but no physical Edge controller was tested. Other Blender versions
and every physical button have not been validated end to end. Control feel, desired
smoothing strength and output framing still need user validation. Paths use straight
segments with optional node easing, without constant-speed spline interpolation.

## Reproduce

Run `scripts/build.ps1`, then `scripts/test.ps1`, then `scripts/test-gui.ps1`, each
with `-BlenderExe` pointing to Blender. The GUI test needs a connected controller
and leaves a separate demo window open with navigation stopped. It saves
`test-output/DualSense_Cinematic_Test.blend`, which contains two saved positions,
a live take and a baked camera. Choose **Cinematic > Start Navigation** to try it.

`scripts/test.ps1` creates configuration and extension directories before launching
Blender. `tests/verify_install.py` checks the resolved configuration path and refuses
to save preferences outside the test profile. Setting `BLENDER_USER_CONFIG` to a
nonexistent directory must not be assumed to provide isolation. Tests save no global
preferences. Runtime/install/reload/GUI evidence is written as JSON in `test-output/`;
profiles, scenes, logs and local device details are excluded from Git.
