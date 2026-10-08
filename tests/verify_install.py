"""Install test: must run through scripts/test.ps1 in the isolated profile."""
from pathlib import Path
import bpy
import importlib
import json
import sys

root = Path(__file__).resolve().parent.parent
output = root/'test-output'
output.mkdir(exist_ok=True)
expected_config = (root/'.test-profile'/'config').resolve()
actual_config = Path(bpy.utils.user_resource('CONFIG')).resolve()
assert actual_config == expected_config, f'Refusing preference write outside test profile: {actual_config}'
assert expected_config.is_dir()
module_name = 'bl_ext.dualsense_test.dualsense_navigator'
result = {'blender': bpy.app.version_string, 'checks': [], 'isolated_config': True}
try:
    prefs = bpy.context.preferences
    prefs.use_preferences_save = False
    repo_dir = root/'.test-profile'/'repository'
    repo_dir.mkdir(parents=True, exist_ok=True)
    repo = prefs.extensions.repos.new(name='DualSense Package Test', module='dualsense_test',
                                     custom_directory=str(repo_dir))
    assert bpy.ops.extensions.package_install_files(repo=repo.module,
        filepath=str(root/'dist'/'dualsense_navigator-1.0.0.zip'), enable_on_install=True) == {'FINISHED'}
    assert module_name in prefs.addons and hasattr(bpy.types, 'VIEW3D_PT_dualsense')
    result['checks'].append('Extension ZIP installed and enabled')
    module = importlib.import_module(module_name)
    reader = module.WindowsHID()
    try:
        result['detected_devices'] = len(reader.devices())
    finally:
        reader.close()
    bpy.ops.preferences.addon_disable(module=module_name)
    assert not hasattr(bpy.types.WindowManager, 'dualsense_nav')
    result['checks'].append('Disable removes registered properties')
    bpy.ops.preferences.addon_enable(module=module_name)
    assert hasattr(bpy.types, 'VIEW3D_PT_dualsense')
    result['checks'].append('Re-enable restores panel')
    bpy.ops.wm.save_userpref()
    assert (expected_config/'userpref.blend').exists()
    result['checks'].append('Enabled extension saved to isolated preferences')
    result['ok'] = True
except Exception as exc:
    result['ok'], result['error'] = False, repr(exc)
(output/'extension_install_verification.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result, indent=2))
if not result['ok']:
    sys.exit(1)
