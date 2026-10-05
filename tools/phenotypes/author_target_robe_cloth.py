"""Author a diagnostic-only Cloth1 palette for stock robe001; no stock pixel donor."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import numpy as np
from PIL import Image

from armory_rigid import rigid_frames
from audit_geometry import arrays
from audit_stock_equipment_palettes import read_stock_plt
from pipeline import digest,save_json
from prepare_target_material_donors import uv_coverage
from retarget import NODE
import shared_toolchain
import target_contract as contract

ARTIFACT_ROOT=Path(__file__).resolve().parents[2]/'output/phenotypes'
HIDDEN={'rootdummy','pelvis_g','lthigh_g','lshin_g','rthigh_g','rshin_g','torso_g','rbicep_g','rforearm_g','rshould_g','lbicep_g','lforearm_g','lshould_g'}


def separate_source_cloth(text):
    visible=[];hidden=[]
    for block in NODE.finditer(text.split('endmodelgeom',1)[0]):
        if not arrays(block[3],'verts'):continue
        def field(key):
            values=re.findall(r'(?mi)^\s*'+key+r'\s+([^\n]+)',block[3])
            if len(values)>1:raise ValueError('Ambiguous source field: '+key)
            return values[0].strip() if values else None
        row={'node':block[2],'type':block[1].lower(),'render':field('render'),'bitmap':field('bitmap'),
             'sourceBlockSha256':hashlib.sha256(block[0].encode('ascii')).hexdigest()}
        if row['render']=='0':
            if row['bitmap']!='NULL' or row['node'].lower() not in HIDDEN:raise ValueError('Hidden bind ownership is not explicitly NULL')
            hidden.append(row);continue
        if row['node']!='Robe' or row['type']!='trimesh' or row['bitmap']!='pmh0_robe001':raise ValueError('Visible cloth ownership is unproved')
        if any(field(k) for k in ('texture0','materialname','materialfile')) or re.search(r'(?mi)^\s*weights\s',block[3]):raise ValueError('Unexpected visible cloth material/skin ownership')
        visible.append((row,block))
    if len(visible)!=1 or {r['node'].lower() for r in hidden}!=HIDDEN or len(hidden)!=13:raise ValueError('Exact one-cloth/thirteen-hidden-bind separation required')
    _,_,frames=rigid_frames(text);row,block=visible[0]
    return row,block,hidden,frames[row['node'].lower()]


def authored_cloth_plt(header_template,shade=128):
    metadata=read_stock_plt(header_template)
    if shade!=128:raise ValueError('Explicit diagnostic neutral shade128 only')
    pixels=np.empty((metadata['height'],metadata['width'],2),dtype=np.uint8);pixels[:,:,0]=shade;pixels[:,:,1]=4
    blob=header_template[:24]+pixels.tobytes();actual=read_stock_plt(blob)
    if actual['materialChannelPixelCounts']!={'4':metadata['height']*metadata['width']} or actual['shadeMinimum']!=shade or actual['shadeMaximum']!=shade:raise ValueError('Authored cloth pixels invalid')
    return blob,actual


def prepare(inventory_path,closure_path,stock_baseline,cloth_palette,target_path,toolchain,migration,output):
    shared_toolchain.load(toolchain,migration);data=contract.load(target_path)
    if data['identity']['prefix']=='pmh0':raise ValueError('No Human material outputs')
    output=output.resolve()
    if output.exists() or not output.is_relative_to(ARTIFACT_ROOT.resolve()):raise ValueError('Fresh isolated authored-cloth diagnostic output required')
    inventory=json.loads(inventory_path.read_text());closure=json.loads(closure_path.read_text());baseline=json.loads(stock_baseline.read_text());frozen={}
    def freeze(path,expected=None):
        path=Path(path).resolve();value=digest(path)
        if expected is not None and value!=expected:raise ValueError('Frozen source changed: '+str(path))
        if output.is_relative_to(path.parent) and path.parent.name in ('raw','ascii','resources'):raise ValueError('Output overlaps source resources')
        frozen[str(path)]=value;return path
    for p in (inventory_path,closure_path,stock_baseline,cloth_palette,target_path,toolchain,migration,Path(__file__)):freeze(p)
    if closure['sourceInventory']['sha256']!=digest(inventory_path) or closure['materialBindingsAccepted'] is not False:raise ValueError('Original missing-material closure must remain pending')
    source=next(r for r in inventory['models'] if r['resource']=='pmh0_robe001.mdl');source_path=freeze(source['asciiPath'],source['asciiSha256']);freeze(source['rawPath'],source['sha256'])
    missing=[m for m in inventory['missingDependencies'] if m['model']==source['resource']]
    if not missing:raise ValueError('Original missing-resource provenance required')
    text=source_path.read_text(encoding='ascii');visible,block,hidden,frame=separate_source_cloth(text)
    template=next(r for r in inventory['dependencies'] if r['name']=='pmh0_robe002.plt');template_path=freeze(template['rawPath'],template['sha256'])
    palette_pin=next(r for r in baseline['resources'] if r['name']=='pal_cloth01.tga')['sha256'];freeze(cloth_palette,palette_pin)
    palette=np.asarray(Image.open(cloth_palette).convert('RGBA'))
    if palette.shape!=(176,256,4):raise ValueError('Expected exact stock Cloth palette dimensions')
    color=palette[0,128]
    if color[3]!=255 or max(color[:3])-min(color[:3])>40:raise ValueError('Stock raster-row0 shade128 is not an opaque neutral diagnostic swatch')
    blob,header=authored_cloth_plt(template_path.read_bytes());verts=np.asarray(arrays(block[3],'verts'));faces=np.asarray(arrays(block[3],'faces'));uv=np.asarray(arrays(block[3],'tverts'))
    mask,coverage=uv_coverage(uv,faces,header['width'],header['height']);world=verts@frame[:3,:3].T+frame[:3,3]
    for name,value in frozen.items():
        if digest(Path(name))!=value:raise ValueError('Frozen input changed before authored palette output')
    output.mkdir(parents=True);resources=output/'diagnostic-only/resources';resources.mkdir(parents=True)
    palette_output=resources/(data['identity']['prefix']+'_robe001.plt');palette_output.write_bytes(blob)
    preview=output/'offline-tinted-palette-row0.png';Image.fromarray(np.tile(color,(header['height'],header['width'],1)),mode='RGBA').save(preview)
    shutil.copyfile(Path(__file__),output/'executed-author_target_robe_cloth.py')
    receipt={'schemaVersion':1,'kind':'target-authored-robe-cloth-diagnostic',**contract.binding(target_path,data,'runtime'),
        'materialSpace':'native-texture','geometrySpace':'original stock model-local bind','statureApplications':0,
        'sourceInventory':{'path':str(inventory_path.resolve()),'sha256':digest(inventory_path)},'sourceClosure':{'path':str(closure_path.resolve()),'sha256':digest(closure_path)},
        'sourceAscii':{'path':str(source_path),'sha256':digest(source_path)},'sourceEffectiveLocation':source['effectiveLocation'],'originalMissingDependencies':missing,
        'visibleCloth':{**visible,'vertices':len(verts),'faces':len(faces),'textureVertices':len(uv),'modelLocalFrame':frame.tolist(),
            'bounds':{'minimum':world.min(0).tolist(),'maximum':world.max(0).tolist()},'authoredNormals':len(arrays(block[3],'normals'))},
        'hiddenBindMeshes':hidden,'separationProved':True,'allSourceGeometryUvsBindsUntouched':True,
        'authoredPalette':{'path':str(palette_output),'name':palette_output.name,'sha256':digest(palette_output),'headerTemplate':template,
            'headerOnlyCopied':True,'native24ByteHeaderExact':blob[:24]==template_path.read_bytes()[:24],'stockPixelsCopied':False,
            'recipe':{'shade':128,'materialLayer':4,'meaning':'Cloth1','allTexelsUniform':True,'newContent':True},'nativePlt':header,'uvCoverage':coverage},
        'offlinePalettePreview':{'path':str(preview),'sha256':digest(preview),'stockClothPalette':{'path':str(cloth_palette.resolve()),'sha256':palette_pin},
            'interpretedRasterRow':0,'interpretedShade':128,'rgba':color.tolist(),'alpha':255,'clientColorRowSemanticsAccepted':False,'clientOpacityAccepted':False},
        'sharedToolchain':{'path':str(toolchain.resolve()),'sha256':digest(toolchain)},'toolMigration':{'path':str(migration.resolve()),'sha256':digest(migration)},'frozenInputs':frozen,
        'stockDonorClaimed':False,'stockAuthorIntentClaimed':False,'sourceClosureResolved':False,'materialDonorAdopted':False,'missingResourcesWaived':False,
        'productionAccepted':False,'clientAccepted':False,'materialBindingsAccepted':False,'profilesAccepted':False,'collisionReviewsAccepted':False,
        'geometryCalibrationPerformed':False,'geometryExported':False,'runtimeSelectionChanged':False,'installedOrPublishedResourcesWritten':False,
        'limitations':['New uniform Cloth1 shade content; not a recovered stock palette or painted shading.','The original ten UV-degenerate triangles are preserved, not repaired or discarded.',
            'Offline neutral swatch uses the decoded stock palette raster-row0 and requires literal client color/opacity validation.','No body, underwear, other cloth layer, global palette or material alias was authored.',
            'Original robe geometry and hidden bind hierarchy remain untouched; private Troll rig/skin conversion, fit, motion and client acceptance remain pending.']}
    save_json(output/'authored.json',receipt);return output/'authored.json'


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for field in ('inventory','closure','stock-baseline','cloth-palette','target-contract','shared-toolchain','migration','output'):parser.add_argument('--'+field,type=Path,required=True)
    args=parser.parse_args();path=prepare(args.inventory,args.closure,args.stock_baseline,args.cloth_palette,args.target_contract,args.shared_toolchain,args.migration,args.output)
    print(json.dumps({'receipt':str(path),'sha256':digest(path),'materialDonorAdopted':False}))
