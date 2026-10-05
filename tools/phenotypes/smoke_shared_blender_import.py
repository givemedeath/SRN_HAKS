"""Prove actual shared addon registration and a read-only stock ASCII import."""
import argparse
import json
from pathlib import Path
import sys

import bpy
import addon_utils

sys.path.insert(0,str(Path(__file__).resolve().parent))
from shared_toolchain import sha


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--source-sha256',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    source=args.source.resolve()
    if sha(source)!=args.source_sha256:raise RuntimeError('Frozen import source changed')
    module=sys.modules['neverblender'];origin=Path(module.__file__).resolve()
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    before={obj.name for obj in bpy.data.objects}
    result=bpy.ops.scene.nvb_mdlimport(filepath=str(source),anim_import=False,import_geometry=True)
    meshes=[obj for obj in bpy.data.objects if obj.name not in before and obj.type=='MESH']
    if result!={'FINISHED'} or not meshes or not any(len(obj.data.polygons)>0 for obj in meshes):
        raise RuntimeError('Shared Neverblender stock model import failed')
    if sha(source)!=args.source_sha256:raise RuntimeError('Import mutated frozen source')
    preferences={}
    item=bpy.context.preferences.addons.get('neverblender')
    if item:
        prefs=item.preferences
        for prop in prefs.bl_rna.properties:
            if prop.type=='STRING':preferences[prop.identifier]=getattr(prefs,prop.identifier)
    report={'schemaVersion':1,'kind':'shared-blender-import-smoke',
        'blenderVersion':bpy.app.version_string,'neverblenderVersion':list(module.bl_info['version']),
        'actuallyLoadedAddon':str(origin),'loadedAddonSha256':sha(origin),
        'enabledAndLoaded':addon_utils.check('neverblender'),
        'source':str(source),'sourceSha256':sha(source),'sourceChanged':False,
        'operator':'scene.nvb_mdlimport','result':sorted(result),
        'importedMeshes':[{'name':obj.name,'vertices':len(obj.data.vertices),
                          'faces':len(obj.data.polygons),'materials':len(obj.data.materials)} for obj in meshes],
        'addonStringPreferences':preferences,'background':bpy.app.background,
        'preferencesChanged':False,'gameClientTesting':False}
    path=args.output.resolve()
    if path.exists():raise RuntimeError('Fresh import smoke receipt required')
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'receipt':str(path),'sha256':sha(path),'loadedAddon':str(origin),
                     'meshCount':len(meshes),'faces':sum(len(obj.data.polygons) for obj in meshes)}),flush=True)


if __name__=='__main__':main()
