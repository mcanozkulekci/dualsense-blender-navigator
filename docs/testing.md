# Tested scope

Test environment: Windows x64, Blender 5.2.2 LTS, standard DualSense; 2026-10-09.

- 24 runtime checks cover USB/basic Bluetooth/enhanced Bluetooth parsing, CRC,
  deadzone, stale input/reconnect protection and actual RegionView3D motion geometry.
- Live enhanced Bluetooth input reports were read successfully.
- Modal start, stop and restart passed in a separate GUI session.
- The extension package passed Blender's build and validation tools.
- Install from Disk, disable/enable and reload from a saved isolated profile passed.
  The normal preference file's SHA256 remained unchanged during the corrected test run.

A USB parser test does not establish physical USB compatibility. The DualSense Edge
device ID is recognized, but no physical Edge controller was tested. Other Blender
versions and every physical controller button have not been validated end to end.

`scripts/test.ps1` creates the configuration and extension directories before launching
Blender. `tests/verify_install.py` checks the resolved configuration path and refuses
to save preferences outside the test profile. Setting `BLENDER_USER_CONFIG` to a
nonexistent directory must not be assumed to provide isolation.
