"""Load the pinned shared Neverblender tree in an isolated Blender CLI run."""
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys

import bpy
import addon_utils

sys.path.insert(0,str(Path(__file__).resolve().parent))
from shared_toolchain import load, sha

config=os.environ['SRN_SHARED_TOOLCHAIN']
migration=os.environ.get('SRN_SHARED_TOOL_MIGRATION')
toolchain=load(config,migration,required=['blender'])
root=Path(toolchain['addons']['root']).resolve()
if not bpy.app.background:raise RuntimeError('Shared tool launcher requires a background Blender process')
if any(name=='neverblender' or name.startswith('neverblender.') for name in sys.modules):
    raise RuntimeError('Neverblender was loaded before shared bootstrap; use --factory-startup')
sys.path.insert(0,str(root));importlib.invalidate_caches()
module=addon_utils.enable('neverblender',default_set=True,persistent=False)
if module is None or not addon_utils.check('neverblender')[1]:raise RuntimeError('Shared Neverblender registration failed')
loaded=[]
for name,module in sys.modules.items():
    if name=='neverblender' or name.startswith('neverblender.'):
        file=Path(module.__file__).resolve()
        if not file.is_relative_to(root):raise RuntimeError('Loaded addon escaped shared tree: '+str(file))
        relative=file.relative_to(root).as_posix()
        if sha(file)!=toolchain['addons']['files'][relative]:raise RuntimeError('Loaded addon bytes differ')
        loaded.append({'module':name,'path':str(file),'sha256':sha(file)})
report={'schemaVersion':1,'kind':'shared-blender-addon-bootstrap',
        'toolchain':str(Path(config).resolve()),'toolchainSha256':sha(config),
        'migrationReceipt':migration,'migrationReceiptSha256':sha(migration) if migration else None,
        'blenderVersion':bpy.app.version_string,'neverblenderVersion':list(sys.modules['neverblender'].bl_info['version']),
        'loadedModules':sorted(loaded,key=lambda row:row['module']),
        'factoryStartup':True,'preferencesChanged':False,'savedPreferencesChanged':False,
        'sessionAddonPreferencesCreated':True,'gameClientTesting':False}
path=Path(os.environ['SRN_SHARED_ADDON_BOOTSTRAP_RECEIPT'])
if path.exists():raise RuntimeError('Fresh bootstrap receipt required')
path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'sharedAddonBootstrap':str(path),'loadedModuleCount':len(loaded),
                  'neverblender':str(sys.modules['neverblender'].__file__)}),flush=True)
