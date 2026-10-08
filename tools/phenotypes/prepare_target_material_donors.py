"""Prepare explicitly unaccepted target-owned material donor diagnostics only."""
import argparse
import json
from pathlib import Path
import re
import shutil
import numpy as np

from audit_geometry import arrays
from audit_native_static_equipment import decode_static_equipment
from audit_stock_equipment_palettes import read_stock_plt
from pipeline import digest,save_json
from retarget import NODE
import shared_toolchain
import target_contract as contract

ARTIFACT_ROOT=Path(__file__).resolve().parents[2]/'output/phenotypes'


def uv_meshes(text):
    result=[]
    for block in NODE.finditer(text.split('endmodelgeom',1)[0]):
        vertices=arrays(block[3],'verts');uv=arrays(block[3],'tverts')
        if not vertices or not uv or re.search(r'(?mi)^\s*render\s+0\s*$',block[3]):continue
        result.append({'name':block[2],'type':block[1].lower(),'verts':np.asarray(vertices),'faces':np.asarray(arrays(block[3],'faces')),
            'tverts':np.asarray(uv),'normals':np.asarray(arrays(block[3],'normals'))})
    return result


def compare_meshes(source,donor):
    if len(source)!=len(donor):return {'meshCounts':[len(source),len(donor)],'orderedVertexFaceUvCorrespondenceExact':False,'meshes':[]}
    results=[]
    for a,b in zip(source,donor):
        fields={key:{'sourceShape':list(a[key].shape),'donorShape':list(b[key].shape),'exact':bool(np.array_equal(a[key],b[key]))} for key in ('verts','faces','tverts','normals')}
        results.append({'sourceNode':a['name'],'donorNode':b['name'],'typesEqual':a['type']==b['type'],'arrays':fields})
    return {'meshCounts':[len(source),len(donor)],'orderedVertexFaceUvCorrespondenceExact':all(r['typesEqual'] and all(v['exact'] for v in r['arrays'].values()) for r in results),'meshes':results}


def uv_coverage(uv,faces,width,height):
    uv=np.asarray(uv,float);faces=np.asarray(faces,float)
    if uv.ndim!=2 or uv.shape[1]!=3 or not np.isfinite(uv).all() or faces.ndim!=2 or faces.shape[1]!=8:raise ValueError('Expected native MDL texture coordinates and eight-column faces')
    indices=faces[:,4:7]
    if not np.array_equal(indices,np.round(indices)) or indices.min()<0 or indices.max()>=len(uv):raise ValueError('Face texture indices outside source UV array')
    if np.min(uv[:,:2])<-1e-9 or np.max(uv[:,:2])>1+1e-9:raise ValueError('Wrapping/clipping UVs require separate review')
    y,x=np.mgrid[:height,:width];points=np.stack(((x+.5)/width,(y+.5)/height),axis=-1)
    mask=np.zeros((height,width),dtype=bool);degenerate=0
    for ids in indices.astype(int):
        a,b,c=uv[ids,:2];e1=b-a;e2=c-a;area=e1[0]*e2[1]-e1[1]*e2[0]
        if abs(area)<1e-12:degenerate+=1;continue
        p=points-a;u=(p[:,:,0]*e2[1]-p[:,:,1]*e2[0])/area;v=(e1[0]*p[:,:,1]-e1[1]*p[:,:,0])/area
        mask|=(u>=-1e-12)&(v>=-1e-12)&(u+v<=1+1e-12)
    return mask,{'uvBounds':[uv[:,:2].min(0).tolist(),uv[:,:2].max(0).tolist()],'triangles':len(faces),'degenerateUvTriangles':degenerate,
        'texelCentersCovered':int(mask.sum()),'totalTexels':width*height,'coverageFraction':float(mask.mean()),'filterFootprintIncluded':False,
        'method':'Union of triangles at texel centers, using face texture indices; no filtering, wrapping or invented UV correspondence.'}


def layer_coverage(blob,mask):
    height,width=mask.shape;pixels=np.frombuffer(blob,np.uint8,offset=24).reshape(height,width,2);results={}
    for label,coverage in (('row0-as-v0',mask),('row0-as-v1',mask[::-1])):
        selected=pixels[coverage];results[label]={'layerPixelCounts':{str(int(k)):int(v) for k,v in zip(*np.unique(selected[:,1],return_counts=True))},
            'shadeMinimum':int(selected[:,0].min()),'shadeMaximum':int(selected[:,0].max()),'shade255Pixels':int((selected[:,0]==255).sum())}
    return {'orientations':results,'clientTextureRowOrientationAccepted':False,
        'compatibilityBasis':'Source255 and donor011 use identical ordered UVs/faces, so native shader row orientation and filtering affect both equally.'}


def target_palette_name(data):
    if data['identity']['prefix']=='pmh0' or data['identity']['gender']!='male' or data['identity']['phenotype']!=0:raise ValueError('Diagnostic cannot write Human or female resources')
    return data['identity']['prefix']+'_shol255.plt'


def prepare(inventory_path,closure_path,target_path,toolchain,migration,output):
    shared_toolchain.load(toolchain,migration);data=contract.load(target_path);destination=target_palette_name(data)
    output=output.resolve()
    if output.exists() or not output.is_relative_to(ARTIFACT_ROOT.resolve()):raise ValueError('Fresh isolated donor diagnostic output required')
    inventory=json.loads(inventory_path.read_text());closure=json.loads(closure_path.read_text());frozen={}
    def freeze(path,expected=None):
        path=Path(path).resolve();value=digest(path)
        if expected is not None and value!=expected:raise ValueError('Frozen donor/source changed: '+str(path))
        if output.is_relative_to(path.parent) and path.parent.name in ('raw','ascii','resources'):raise ValueError('Donor output overlaps frozen inputs')
        frozen[str(path)]=value;return path
    for p in (inventory_path,closure_path,target_path,toolchain,migration,Path(__file__)):freeze(p)
    if closure['sourceInventory']['sha256']!=digest(inventory_path) or closure['materialBindingsAccepted'] is not False:raise ValueError('Missing-source closure provenance required')
    source_missing=[r for r in inventory['missingDependencies'] if r['model'] in ('pmh0_robe001.mdl','pmh0_shol255.mdl')]
    if {r['model'] for r in source_missing}!={'pmh0_robe001.mdl','pmh0_shol255.mdl'}:raise ValueError('Original missing-resource records must remain explicit')
    models={r['resource']:r for r in inventory['models']};deps={r['name']:r for r in inventory['dependencies']}
    def source(name):
        row=models[name];freeze(row['rawPath'],row['sha256']);path=freeze(row['asciiPath'],row['asciiSha256']);return row,uv_meshes(path.read_text(encoding='ascii'))
    original,a=source('pmh0_shol255.mdl');donor,b=source('pmh0_shol011.mdl')
    if original['part']!=donor['part'] or original['part']!='shol':raise ValueError('Same-side shoulder donor ownership required')
    correspondence=compare_meshes(a,b)
    if not correspondence['orderedVertexFaceUvCorrespondenceExact'] or len(a)!=1:raise ValueError('Shoulder donor source correspondence is not exact')
    native=[decode_static_equipment(Path(row['rawPath']).read_bytes())['meshes'] for row in (original,donor)]
    native_checks={key:all(np.array_equal(x[key],y[key]) for x,y in zip(*native)) for key in ('positions','normals','faces','worldPositions','worldNormals')}
    native_checks['uv']=len(native[0])==len(native[1]) and all(len(x['uv'])==len(y['uv']) and all(np.array_equal(p,q) for p,q in zip(x['uv'],y['uv'])) for x,y in zip(*native))
    if not all(native_checks.values()):raise ValueError('Independent native shoulder correspondence differs')
    palette=deps['pmh0_shol011.plt'];palette_path=freeze(palette['rawPath'],palette['sha256'])
    if palette['name'] not in donor['renderTextureDependencies']:raise ValueError('Donor palette is not declared installed source ownership')
    blob=palette_path.read_bytes();header=read_stock_plt(blob);mask,coverage=uv_coverage(a[0]['tverts'],a[0]['faces'],header['width'],header['height'])
    material_layers=layer_coverage(blob,mask)
    robe,robe_mesh=source('pmh0_robe001.mdl');robe_candidates=[]
    for name,row in sorted(models.items()):
        if row['part']!='robe' or name==robe['resource']:continue
        _,mesh=source(name);proof=compare_meshes(robe_mesh,mesh)
        counts={field:int(sum(len(m[field]) for m in mesh)) for field in ('verts','faces','tverts')};source_counts={field:int(sum(len(m[field]) for m in robe_mesh)) for field in counts}
        robe_candidates.append({'sourceResource':name,'meshCount':len(mesh),'counts':counts,'countDifferences':{key:abs(counts[key]-source_counts[key]) for key in counts},
            'correspondence':proof,'donorAccepted':False,'paletteCopied':False})
    exact_robe=[r for r in robe_candidates if r['correspondence']['orderedVertexFaceUvCorrespondenceExact']]
    if exact_robe:raise ValueError('Unexpected exact robe donor needs a separately reviewed diagnostic; no automatic selection')
    for path,value in frozen.items():
        if digest(Path(path))!=value:raise ValueError('Frozen input changed before donor copy')
    output.mkdir(parents=True);resources=output/'diagnostic-only/resources';resources.mkdir(parents=True);target=resources/destination;shutil.copyfile(palette_path,target)
    if digest(target)!=palette['sha256']:raise ValueError('Native donor palette copy differs')
    shutil.copyfile(Path(__file__),output/'executed-prepare_target_material_donors.py')
    receipt={'schemaVersion':1,'kind':'target-equipment-material-donor-diagnostic',**contract.binding(target_path,data,'runtime'),
        'materialSpace':'native-texture','statureApplications':0,'sourceInventory':{'path':str(inventory_path.resolve()),'sha256':digest(inventory_path)},
        'sourceClosureReceipt':{'path':str(closure_path.resolve()),'sha256':digest(closure_path)},'sharedToolchain':{'path':str(toolchain.resolve()),'sha256':digest(toolchain)},
        'toolMigration':{'path':str(migration.resolve()),'sha256':digest(migration)},'originalMissingDependencies':source_missing,'frozenInputs':frozen,
        'shoulder255':{'proposal':'Explicit same-side stock shoulder011 metal-palette donor diagnostic only','sourceResource':original['resource'],'donorResource':donor['resource'],
            'asciiCorrespondence':correspondence,'independentNativeArraysExact':native_checks,'sourcePalette':{'resource':palette['name'],'sha256':palette['sha256'],'effectiveLocation':palette['effectiveLocation']},
            'diagnosticResource':{'name':destination,'path':str(target),'sha256':digest(target)},'nativePlt':header,'uvCoverage':coverage,'layerCoverage':material_layers,
            'nativePaletteBytesPreserved':True,'renderedAppearanceAccepted':False,'sourceClosureResolved':False,'materialDonorAdopted':False},
        'robe001':{'sourceResource':robe['resource'],'sourceCounts':source_counts,'scope':'All12 other inventoried installed Human male phenotype0 robe resources',
            'candidates':robe_candidates,'exactDonorCount':0,'closestTextureVertexCount':min(robe_candidates,key=lambda r:r['countDifferences']['tverts'])['sourceResource'],
            'closestVertexCount':min(robe_candidates,key=lambda r:r['countDifferences']['verts'])['sourceResource'],'proposal':'Reject stock palette donor: exact UV/layout/vertex correspondence is unproved',
            'diagnosticPaletteCreated':False,'sourceClosureResolved':False,'materialDonorAdopted':False},
        'missingResourcesWaived':False,'originalResourcesModified':False,'geometryCalibrationPerformed':False,'geometryExported':False,'runtimeSelectionChanged':False,
        'productionAccepted':False,'clientAccepted':False,'materialBindingsAccepted':False,'profilesAccepted':False,'collisionReviewsAccepted':False,
        'limitations':['Shoulder diagnostic preserves two metal layers; it is not a skin palette.','Texel-center coverage excludes filtering and live renderer behavior.',
            'Only one target-owned PLT is copied; no model, fixture, HAK, 2DA or final selection is changed.','Robe candidates are compared in the declared Human male phenotype0 stock inventory, not every external/custom resource.',
            'Final adoption requires root review, explicit material ownership and literal client evidence; original missing-source records remain blocking.']}
    save_json(output/'donors.json',receipt);return output/'donors.json'


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for field in ('inventory','closure','target-contract','shared-toolchain','migration','output'):parser.add_argument('--'+field,type=Path,required=True)
    args=parser.parse_args();path=prepare(args.inventory,args.closure,args.target_contract,args.shared_toolchain,args.migration,args.output)
    print(json.dumps({'receipt':str(path),'sha256':digest(path),'materialDonorAdopted':False}))
