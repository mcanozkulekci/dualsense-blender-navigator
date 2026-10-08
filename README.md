# DualSense Blender Navigator

A Windows extension for navigating Blender's 3D viewport with a PS5 DualSense controller.
Reads USB and Bluetooth HID input directly, with no additional Python packages or drivers.

## Installation

1. Download [dualsense_navigator-1.0.1.zip](packages/dualsense_navigator-1.0.1.zip?raw=1).
2. In Blender, open **Edit > Preferences > Add-ons > menu > Install from Disk**.
3. Select the ZIP and enable **DualSense Navigator**.
4. If automatic preference saving is disabled, click **Save Preferences**.
5. In the 3D viewport, open **N > DualSense > Start Navigation**.

Keep the pointer inside the target viewport. Navigation pauses when Blender loses focus
or the pointer leaves the viewport. Enabling the extension does not start navigation.

## Controls

| Control | Action |
|---|---|
| Left stick | Move forward/backward and strafe left/right |
| Right stick | Look around |
| L2 / R2 | Move down / up |
| Hold L1 / R1 | Precision movement (0.2x) / fast movement (4x) |
| D-pad up / down | Increase / decrease movement speed |
| Cross (X) | Pause / resume navigation |
| Triangle | Switch between horizontal movement and flight along the viewing direction |
| Circle | Restore the starting view and stop |
| Options / Esc | Stop at the current viewpoint |

The sidebar provides movement speed, look speed, deadzone, horizontal movement and
vertical look inversion settings. Navigation changes the viewport only; it does not
change scene objects or camera transforms. Gravity, collision detection, roll, FOV
control and camera path recording are not included in version 1.0.1.

## Compatibility and validation

- Target: Windows x64 and Blender 4.2 or later.
- Tested: Blender 5.2.2 LTS with a standard DualSense over enhanced Bluetooth HID.
- 24 runtime checks passed, covering USB/basic Bluetooth/enhanced Bluetooth parsing,
  CRC validation, deadzone, stale input protection and actual RegionView3D motion.
- Modal start, stop and restart passed in a separate GUI session.
- Extension installation, disable/enable and reload from saved test preferences passed.
- Physical USB, DualSense Edge and other Blender versions have not been tested.
- With multiple controllers, the first accessible device is used. Quad View is unsupported.
- If Steam Input or HidHide hides the device, allow the extension to access it.

See [testing notes](https://github.com/mcanozkulekci/dualsense-blender-navigator/blob/main/docs/testing.md) for the validated scope.

## Development

Extension source: `__init__.py`. Package manifest: `blender_manifest.toml`.

```powershell
.\scripts\build.ps1 -BlenderExe 'C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe'
.\scripts\test.ps1 -BlenderExe 'C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe'
```

The build script uses Blender's extension tools to build and validate the ZIP, then
copies it to `packages/`. Tests use a pre-created `.test-profile` directory and refuse
to save preferences if Blender resolves the normal configuration directory instead.
Test output is written to `test-output/`.

## License and references

GPL-3.0-or-later; see [LICENSE](LICENSE).

- [DualSense HID report map](https://github.com/nondebug/dualsense/blob/main/README.md)
- [PlayStation HID driver](https://github.com/torvalds/linux/blob/master/drivers/hid/hid-playstation.c)
- [Microsoft HID input documentation](https://learn.microsoft.com/en-us/windows-hardware/drivers/hid/obtaining-hid-reports)
