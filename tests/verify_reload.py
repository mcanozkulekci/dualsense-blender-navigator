from pathlib import Path
import bpy
import json
import sys
root = Path(__file__).resolve().parent.parent
expected_config = (root/'.test-profile'/'config').resolve()
assert Path(bpy.utils.user_resource('CONFIG')).resolve() == expected_config
result = {'blender': bpy.app.version_string, 'isolated_config': True}
result['enabled_after_restart'] = 'bl_ext.dualsense_test.dualsense_navigator' in bpy.context.preferences.addons
result['panel_registered_after_restart'] = hasattr(bpy.types, 'VIEW3D_PT_dualsense')
result['ok'] = result['enabled_after_restart'] and result['panel_registered_after_restart']
(root/'test-output'/'extension_reload_verification.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result, indent=2))
if not result['ok']:
    sys.exit(1)
