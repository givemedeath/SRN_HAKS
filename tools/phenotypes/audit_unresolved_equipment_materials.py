"""Read-only material source closure for unresolved stock Troll equipment inputs."""
import argparse
import json
from pathlib import Path
import re
import shutil

from audit_geometry import arrays
from audit_native_static_equipment import decode_static_equipment
from audit_stock_equipment_palettes import read_stock_plt
from measure_held_equipment import table_rows
from pipeline import digest,save_json
from retarget import NODE
import shared_toolchain

IMAGE_TYPES=('.dds','.plt','.tga')
MATERIAL_TYPES=('.mtr',)+IMAGE_TYPES
FIELDS=('bitmap','texture0','materialname','materialfile','render','renderhint','ambient','diffuse','specular','shininess','alpha','selfillumcolor')
ARTIFACT_ROOT=Path(__file__).resolve().parents[2]/'output/phenotypes'


def mesh_materials(text):
    result=[]
    for node in NODE.finditer(text.split('endmodelgeom',1)[0]):
        vertices=arrays(node[3],'verts')
        if not vertices:continue
        fields={key:[m.strip() for m in re.findall(r'(?mi)^\s*'+key+r'\s+([^\n]+)',node[3])] for key in FIELDS}
        if len(fields['render'])>1:raise ValueError('Ambiguous rendered-source flag')
        enabled=fields['render']!=['0']
        names={token.lower() for key in ('bitmap','texture0','materialname','materialfile') for token in fields[key] if token.lower() not in ('null','****','')}
        result.append({'node':node[2],'type':node[1].lower(),'vertices':len(vertices),'textureVertices':len(arrays(node[3],'tverts')),
            'authoredVertexColors':len(arrays(node[3],'colors')),'fields':fields,'renderEnabled':enabled,
            'renderDefaultApplied':not fields['render'],'requestedMaterialOrTextureNames':sorted(names),
            'explicitUntexturedDeclaration':not names and any(fields[key]==['NULL'] or fields[key]==['null'] for key in ('bitmap','texture0'))})
    return result


def named_closure(stem,names):
    present=[stem+ext for ext in MATERIAL_TYPES if stem+ext in names]
    metadata=[stem+'.txi'] if stem+'.txi' in names else []
    return {'name':stem,'presentImageOrMaterialResources':present,'presentTextureMetadata':metadata,
            'declaredImageOrMaterialAbsent':not present,'metadataAloneCanCloseBaseColor':False,
            'intendedUntexturedMaterialProved':False,'bindingAccepted':False}


def audit(inventory_path,replacement_table,extraction_path,diagnosis_path,toolchain,migration,output):
    inventory_path=inventory_path.resolve();output=output.resolve()
    shared_toolchain.load(toolchain,migration)
    if output.exists() or not output.is_relative_to(ARTIFACT_ROOT.resolve()):raise ValueError('Fresh isolated material audit output required')
    inventory=json.loads(inventory_path.read_text());frozen={}
    def freeze(path,expected=None):
        path=Path(path).resolve();value=digest(path)
        if expected is not None and value!=expected:raise ValueError('Frozen source changed: '+str(path))
        if output.is_relative_to(path.parent) and path.parent.name in ('raw','ascii'):raise ValueError('Audit overlaps frozen source resources')
        frozen[str(path)]=value;return path
    for p in (inventory_path,replacement_table,extraction_path,diagnosis_path,toolchain,migration,Path(__file__)):
        freeze(p)
    extraction=json.loads(Path(extraction_path).read_text())
    if not extraction.get('overridesDisabled') or extraction['sourceInventorySha256']!=digest(inventory_path):raise ValueError('Installed extraction provenance differs')
    if extraction['sharedToolchain']['sha256']!=digest(toolchain) or extraction['migration']['sha256']!=digest(migration):raise ValueError('Shared toolchain provenance differs')
    replacement_table=freeze(replacement_table,extraction['files'][str(Path(replacement_table).resolve())])
    view=freeze(inventory['resourceViewPath'],inventory['resourceViewSha256']);locations={line.split()[0].lower():line for line in view.read_text().splitlines() if line.strip()}
    models={row['resource']:row for row in inventory['models']};deps={row['name']:row for row in inventory['dependencies']}
    findings={}
    for source in ('pmh0_robe001.mdl','pmh0_shol255.mdl'):
        row=models[source];raw=freeze(row['rawPath'],row['sha256']);ascii_path=freeze(row['asciiPath'],row['asciiSha256']);meshes=mesh_materials(ascii_path.read_text(encoding='ascii'))
        render=[m for m in meshes if m['renderEnabled']];closures=[named_closure(stem,locations) for stem in sorted({s for m in render for s in m['requestedMaterialOrTextureNames']})]
        native=None
        if raw.read_bytes()[:4]==b'\0'*4:
            decoded=decode_static_equipment(raw.read_bytes());native=[{'node':n['name'],'render':n['render'],'bitmap':n['bitmap'],'vertices':n['vertices']} for n in decoded['nodes'] if 'bitmap' in n]
        findings[source]={'rawSha256':row['sha256'],'asciiSha256':row['asciiSha256'],'effectiveLocation':row['effectiveLocation'],
            'nativeFormat':'binary' if native is not None else 'installed ASCII','meshMaterials':meshes,'renderedMeshCount':len(render),'nativeRenderedMaterialDeclarations':native,
            'requestedClosure':closures,'classification':'Requested rendered image/material dependency absent; intentional untextured material unproved',
            'crossFamilySameStyleResources':[line for name,line in locations.items() if re.fullmatch(r'p[fm][a-z][0-9]_'+re.escape(Path(source).stem[5:])+r'\.(mdl|plt|dds|tga|mtr|txi)',name)],
            'fallbackSelected':False,'replacementSelected':False,'styleDropped':False,'sourceMaterialAccepted':False}
    tables={}
    for name,style in (('parts_robe.2da',1),('parts_shoulder.2da',255)):
        p=freeze(deps[name]['rawPath'],deps[name]['sha256']);rows=table_rows(p)
        tables[name]={'sha256':digest(p),'effectiveLocation':deps[name]['effectiveLocation'],'columns':list(next(iter(rows.values()))),
            'requestedStyle':style,'requestedRow':rows.get(style),'maximumInstalledRow':max(rows),'alternateTextureColumnPresent':any('tex' in c.lower() for c in next(iter(rows.values())))}
    tables['replacetexture.2da']={'sha256':digest(replacement_table),'rows':table_rows(replacement_table),'requestedStyleMappingsPresent':False}
    witnesses={}
    for name in ('pmh0_robe002.mdl','pmh0_shol011.mdl','pmh0_shor011.mdl'):
        row=models[name];p=freeze(row['asciiPath'],row['asciiSha256']);materials=[m for m in mesh_materials(p.read_text(encoding='ascii')) if m['renderEnabled']];palettes=[]
        for dep in row['renderTextureDependencies']:
            info=deps[dep];palette=freeze(info['rawPath'],info['sha256']);palettes.append({'resource':dep,'sha256':info['sha256'],'effectiveLocation':info['effectiveLocation'],
                'validation':read_stock_plt(palette.read_bytes()) if palette.suffix.lower()=='.plt' else None,'selectedForUnresolvedStyle':False})
        witnesses[name]={'materialDeclarations':materials,'paletteInputs':palettes,'bodyFitOrGeometryCalibrationPerformed':False}
    for path,value in frozen.items():
        if digest(Path(path))!=value:raise ValueError('Frozen source changed during read-only audit')
    output.mkdir(parents=True);shutil.copyfile(Path(__file__),output/'executed-audit_unresolved_equipment_materials.py')
    receipt={'schemaVersion':1,'kind':'unresolved-equipment-material-source-closure','sourceInventory':{'path':str(inventory_path),'sha256':digest(inventory_path)},
        'sharedToolchain':{'path':str(Path(toolchain).resolve()),'sha256':digest(toolchain)},'toolMigration':{'path':str(Path(migration).resolve()),'sha256':digest(migration)},
        'findings':findings,'tables':tables,'positiveMaterialWitnesses':witnesses,'frozenInputs':frozen,
        'classificationScope':'Installed named resources, mesh declarations and table ownership; renderer fallback and author intent are not observed.',
        'priorDiagnosis':{'path':str(diagnosis_path.resolve()),'sha256':digest(diagnosis_path)},
        'productionAccepted':False,'clientAccepted':False,'materialBindingsAccepted':False,'profilesAccepted':False,'collisionReviewsAccepted':False,
        'originalResourcesModified':False,'geometryCalibrationPerformed':False,'runtimeSelectionChanged':False,
        'documentation':[{'url':'https://nwn.wiki/spaces/NWN1/pages/53671005/Model%2BTable%2Bof%2BParameters','scope':'Default render1; possible missing-texture white fallback, with parts defaults marked as needing checking.'},
            {'url':'https://nwn.wiki/spaces/NWN1/pages/14618045/PLT','scope':'Multipart PLT ownership; race-specific parts may default to Human palette of the same style.'}],
        'limitations':['Missing texture fallback is documented as possible, not observed or accepted here.','Human self-named style palettes are themselves missing; cross-race same-style fallback cannot supply those absent resources.',
            'Blank ACBONUS does not imply intentionally untextured material: stock robe002 also has blank ACBONUS and a valid native palette.',
            'Shoulder011 lineage does not authorize a replacement for shoulder255.','No models, palettes, materials, table rows, target contracts, ledgers or selections were changed.']}
    save_json(output/'closure.json',receipt);return output/'closure.json'


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for field in ('inventory','replacement-table','extraction','prior-diagnosis','shared-toolchain','migration','output'):parser.add_argument('--'+field,type=Path,required=True)
    args=parser.parse_args();path=audit(args.inventory,args.replacement_table,args.extraction,args.prior_diagnosis,args.shared_toolchain,args.migration,args.output)
    print(json.dumps({'receipt':str(path),'sha256':digest(path),'materialBindingsAccepted':False}))
