"""Read Blender's loaded addon origins and saved script-directory preferences."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import bpy
import addon_utils


def sha(path):
    result=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):result.update(block)
    return result.hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    enabled=[]
    for item in bpy.context.preferences.addons:
        module=sys.modules.get(item.module)
        file=getattr(module,'__file__',None)
        enabled.append({'module':item.module,'enabledAndLoaded':addon_utils.check(item.module),
                        'actuallyLoaded':module is not None,'loadedFile':file,
                        'loadedFileSha256':sha(file) if file and Path(file).is_file() else None,
                        'blInfo':getattr(module,'bl_info',None)})
    directories=[]
    for item in getattr(bpy.context.preferences.filepaths,'script_directories',[]):
        directories.append({'name':item.name,'directory':item.directory})
    active=[{'module':name,'loadedFile':getattr(module,'__file__',None)}
            for name,module in sys.modules.items() if name=='neverblender' or name.startswith('neverblender.')]
    report={'schemaVersion':1,'kind':'blender-actual-addon-path-inspection',
            'blenderVersion':bpy.app.version_string,'blenderBinary':bpy.app.binary_path,
            'blenderBinarySha256':sha(bpy.app.binary_path),
            'background':bpy.app.background,'loadedCurrentUserPreferences':True,
            'configDirectory':bpy.utils.user_resource('CONFIG'),
            'legacyScriptDirectory':getattr(bpy.context.preferences.filepaths,'script_directory',None),
            'scriptDirectories':directories,'actualAddonSearchPaths':addon_utils.paths(),
            'enabledAddons':enabled,'loadedNeverblenderModules':active,
            'sysPath':list(sys.path),'helper':str(Path(__file__).resolve()),'helperSha256':sha(__file__),
            'preferencesChanged':False,'gameClientTesting':False}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    if args.output.exists():raise RuntimeError('Fresh addon path inspection required')
    args.output.write_text(json.dumps(report,indent=2,default=str)+'\n',encoding='utf-8')
    print(json.dumps({'receipt':str(args.output),'sha256':sha(args.output),
                     'enabledAddons':enabled,'scriptDirectories':directories}),flush=True)


if __name__=='__main__':main()
