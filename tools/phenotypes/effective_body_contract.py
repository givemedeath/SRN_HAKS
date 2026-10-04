"""Current native body inventory; compiler provenance and runtime maps stay separate."""
import json
from pathlib import Path
import re

from stage_stock_part import require, sha
from stock_limb_contract import ATTACHMENTS, PAIRS, validate_receipt_lineage

BODY_PARTS={'chest','pelvis',*ATTACHMENTS}
PRESERVED_PARTS={'chest','pelvis','legl','legr','shinl','shinr'}


def validate_body_ownership(model_parts, resource_names, complete):
    """Exact native Human namespace, including the one accepted cloth material."""
    parts=set(model_parts.values())
    require(len(parts)==len(model_parts) and PRESERVED_PARTS<=parts<=BODY_PARTS,
            'Duplicate, missing accepted or undeclared body ownership')
    require(model_parts=={'pmh0_'+part+'001.mdl':part for part in parts},
            'Undeclared body model namespace')
    for left,right in PAIRS:
        require((left in parts)==(right in parts),'Body requires complete selected pairs')
    require(complete==(parts==BODY_PARTS),'Complete-body status differs from actual ownership')
    expected=set()
    for part in parts:
        prefix='pmh0_'+part+'001'
        expected.update(prefix+suffix for suffix in ('.mdl','.mtr','.plt','n.tga','r.tga'))
    expected.update({'pmh0_pelvis001f.mtr','pmh0_pelvis001f.tga'})
    require(set(resource_names)==expected,'Missing or undeclared body/material resource')
    return parts


def validate_preserved_bytes(selection, actual):
    preserved=selection.get('accepted6ResourceHashes',{})
    expected={'pmh0_'+part+'001'+suffix for part in PRESERVED_PARTS
              for suffix in ('.mdl','.mtr','.plt','n.tga','r.tga')}
    expected.update({'pmh0_pelvis001f.mtr','pmh0_pelvis001f.tga'})
    require(set(preserved)==expected and all(actual.get(name)==pin for name,pin in preserved.items()),
            'Accepted six effective resource bytes changed')


def hashes(directory):
    require(directory.is_dir() and all(p.is_file() for p in directory.iterdir()),'Flat resource directory required')
    return {p.name:sha(p) for p in sorted(directory.iterdir())}


def validate_effective_normal_dependencies(converted, native):
    """A roughness descendant may not change the original normal/diffuse bindings."""
    resources=Path(converted)/'resources'; dependencies=native['materialResourceHashes']
    origins=[]
    def visit(data):
        composition=data.get('composition',{})
        rows=composition.get('sourceReceipts')
        if rows is None: rows=list(composition.get('perModelReceipts',{}).values())
        for row in rows:
            path=Path(row['path']); origins.append(path.parent/'resources')
            visit(json.loads(path.read_text()))
    visit(native)
    def bindings(text):
        return {int(slot):name.lower().removesuffix('.tga').removesuffix('.dds')
                for slot,name in re.findall(r'(?im)^\s*texture([01])\s+"?([^\s"]+)',text)}
    hint=r'(?im)^\s*renderhint\s+"?NormalTangents"?\s*$'
    checked=[]
    for material in sorted(resources.glob('*.mtr')):
        text=re.sub(r'//[^\n]*','',material.read_text(encoding='ascii'))
        require(re.search(hint,text),'Current body material lacks NormalTangents: '+material.name)
        require(material.name in dependencies,'Body tangent material absent from compiler union')
        if sha(material)==dependencies[material.name]: original=material
        else:
            matches=[directory/material.name for directory in origins
                     if (directory/material.name).is_file()
                     and sha(directory/material.name)==dependencies[material.name]]
            require(matches,'Original compile-time material unavailable/changed: '+material.name)
            original=matches[0]
        original_text=re.sub(r'//[^\n]*','',original.read_text(encoding='ascii'))
        current_bindings=bindings(text)
        require(re.search(hint,original_text) and current_bindings==bindings(original_text)
                and 1 in current_bindings,'Effective material changes compiled tangent bindings: '+material.name)
        for reference in current_bindings.values():
            owned=[resources/(reference+suffix) for suffix in ('.tga','.dds')
                   if (resources/(reference+suffix)).exists()]
            require(owned,'Body material missing owned texture: '+reference)
            for texture in owned:
                require(dependencies.get(texture.name)==sha(texture),
                        'Effective texture changes compiled tangent dependency: '+texture.name)
        checked.append(material.name)
    return checked


def validate_effective_body(converted):
    converted=Path(converted).resolve(); path=converted/'effective-material-inventory.json'
    record=json.loads(path.read_text())
    require(record.get('schemaVersion')==1 and record.get('kind')=='effective-native-body-inventory',
            'Explicit current native/runtime inventory required')
    resources=converted/'resources'; actual=hashes(resources)
    require(actual==record['resourceHashes'],'Actual current native body inventory changed')
    validate_body_ownership(record['modelParts'],actual,record['completeBodySelected'])
    native_path=converted/'native-compile.json'
    require(sha(native_path)==record['nativeReceiptSha256'],'Original compiler union changed')
    native=json.loads(native_path.read_text()); validate_receipt_lineage(native)
    require(native.get('complete') is True,'Incomplete native union')
    models={row['name']:row for row in native['models']}
    require(len(models)==len(native['models']) and set(models)==set(record['modelParts']), 'Model ownership differs')
    require(hashes(converted/'ascii')=={name:row['sourceSha256'] for name,row in models.items()},
            'Source ASCII model inventory changed')
    for name,row in models.items():
        part=record['modelParts'][name]
        require(part in BODY_PARTS and name=='pmh0_'+part+'001.mdl', 'Undeclared body model namespace')
        require(actual[name]==row['binarySha256'] and (resources/name).stat().st_size==row['bytes']
                and (resources/name).read_bytes()[:4]==b'\0\0\0\0','Actual native output differs')
        text=(converted/'ascii'/name).read_text(encoding='ascii')
        require(not re.search(r'(?mi)^\s*newanim\s',text) and re.search(
            r'(?mi)^setsupermodel\s+'+re.escape(Path(name).stem)+r'\s+NULL\s*$',text),
            'Body part changes animations/supermodel')
    runtime={name:pin for name,pin in actual.items() if not name.endswith('.mdl')}
    require(runtime==record['runtimeMaterialResourceHashes'],'Effective runtime material inventory differs')
    require(set(actual)==set(models)|set(runtime), 'Undeclared body resource')
    selections=[]
    for path_string,pin in record['frozenInputs'].items():
        frozen=Path(path_string)
        require(sha(frozen)==pin, 'Frozen current body provenance changed: '+path_string)
        if frozen.suffix=='.json':
            data=json.loads(frozen.read_text())
            if 'accepted6ResourceHashes' in data: selections.append(data)
    require(len(selections)==1,'Exactly one frozen accepted-six selection required')
    validate_preserved_bytes(selections[0],actual)
    require(record.get('acceptedSixBytesExact') is True,'Accepted baseline preservation flag differs')
    conversion=json.loads((converted/'conversion.json').read_text())
    require(conversion['ownedResourceHashes']==actual and conversion['modelPrefix']=='pmh0'
            and conversion['rigMode']=='stock-exact-game-fallback' and conversion['stockOtherPartsFromGame'] is True
            and conversion['equipmentMode']=='stock-identity'
            and conversion['height']==conversion['stockReferenceHeight']==1.9339157,
            'Current native body changes stock identity')
    require({row['model']+'.mdl' for row in conversion['parts']}==set(models)
            and len(conversion['parts'])==len(models),'Conversion part ownership differs')
    validate_effective_normal_dependencies(converted,native)
    return native,runtime,record
