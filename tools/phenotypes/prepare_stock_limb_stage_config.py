"""Extract exact embedded 2K limb maps and bind a supplied fitted receipt.

This prepares a strict stage_stock_part configuration, not an acceptance claim.
"""
import argparse
from io import BytesIO
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image

from place_purposebuilt_pelvis import read_glb, embedded_maps, raw_corners
from stage_stock_part import require, sha, save
from stock_limb_contract import ATTACHMENTS, OPPOSITE


JOINTS=ATTACHMENTS


def receipt_lineage(path,seen=None):
    """Bind current candidate/parent links and determine actual stock side."""
    path=Path(path).resolve();seen=set() if seen is None else seen
    require(path not in seen and len(seen)<32,'Cyclic/excessive fit receipt lineage')
    seen=seen|{path};record=json.loads(path.read_text());candidate=Path(record['candidate']).resolve()
    require(sha(candidate)==record['candidateSha256'],'Fitted/mirrored source association differs')
    archive=record.get('nativeCornerArchive')
    require(archive and sha(archive['path'])==archive['sha256'],'Native corner archive missing/changed')
    links=[{'receipt':str(path),'receiptSha256':sha(path),'candidate':str(candidate),'candidateSha256':sha(candidate)}]
    if record.get('parentReceipt') or record.get('sourceReceipt'):
        mirror=bool(record.get('sourceReceipt'))
        key='sourceReceipt' if mirror else 'parentReceipt';parent=Path(record[key]).resolve()
        require(sha(parent)==record[key+'Sha256'],'Parent fit/mirror receipt changed')
        parent_candidate,parent_part,ancestor=receipt_lineage(parent,seen)
        source_key='source' if mirror else ('parentSource' if 'parentSource' in record else 'parentCandidate')
        require(Path(record[source_key]).resolve()==parent_candidate
                and record[source_key+'Sha256']==sha(parent_candidate),'Parent candidate association differs')
        parent_doc,parent_bin=read_glb(parent_candidate);doc,binary=read_glb(candidate)
        require(embedded_maps(doc,binary)==embedded_maps(parent_doc,parent_bin),'Fit/repair/mirror changed embedded maps')
        if mirror:
            config=record['configuration'];target=config.get('targetJoint');part=next((p for p,j in JOINTS.items() if j==target),None)
            require(part and part==OPPOSITE[parent_part] and config.get('sourceJoint')==JOINTS[parent_part],
                    'Mirror donor/target joint side association differs')
            matrix=np.asarray(record['sourceToTargetLocal'],dtype=float)
            require(matrix.shape==(4,4) and np.isfinite(matrix).all() and np.linalg.det(matrix[:3,:3])<0,
                    'Mirrored candidate lacks a finite reflected source-to-target transform')
            rotation=matrix[:3,:3]
            require(np.allclose(rotation.T@rotation,np.eye(3),atol=1e-9,rtol=0)
                    and np.allclose(matrix[3],[0,0,0,1],atol=1e-12,rtol=0),'Mirror stage requires an orthogonal measured frame reflection')
            parent_extra={};extra={}
            pp,pn,pu,_=raw_corners(parent_doc,parent_bin,allow_wrapper=True,extra=parent_extra)
            cp,cn,cu,_=raw_corners(doc,binary,extra=extra);order=[0,2,1]
            require(cp.shape==pp.shape and np.allclose(cp,pp[:,order]@rotation.T+matrix[:3,3],atol=6e-8,rtol=0)
                    and np.allclose(cn,pn[:,order]@rotation.T,atol=1e-7,rtol=0)
                    and np.array_equal(cu,pu[:,order]),'Actual mirrored P/N/UV does not match recorded reflection/winding')
            require(set(extra)==set(parent_extra),'Mirrored attribute inventory changed')
            if 'TANGENT' in extra:
                pt=np.concatenate(parent_extra['TANGENT']['rows'])[:,order];ct=np.concatenate(extra['TANGENT']['rows'])
                require(np.allclose(ct[:,:,:3],pt[:,:,:3]@rotation.T,atol=1e-7,rtol=0)
                        and np.array_equal(ct[:,:,3],-pt[:,:,3]),'Actual mirrored tangents/handedness differ')
        else:part=parent_part
        if 'part' in record:require(record['part']==part,'Descendant changes inherited limb side')
        if 'joint' in record:require(record['joint']==JOINTS[part],'Descendant changes inherited stock joint')
        return candidate,part,links+ancestor
    part=record.get('part')
    require(part in JOINTS and record.get('joint')==JOINTS[part]
            and record.get('model')=='pmh0_'+part+'001','Base fit lacks explicit limb model/joint association')
    require(record.get('generation') and sha(record['generation'])==record['generationSha256'],
            'Base fit generation association changed/missing')
    generation=json.loads(Path(record['generation']).read_text());source=Path(record['source']).resolve()
    require(sha(source)==record['sourceSha256'] and generation.get('state')=='success'
            and generation.get('promptId')==record['jobPromptId'] and any(
            Path(o.get('localPath','')).resolve()==source and o.get('sha256')==sha(source)
            for o in generation.get('outputs',[])),'Base fit source is not an exact successful generated output')
    original_doc,original_binary=read_glb(source);candidate_doc,candidate_binary=read_glb(candidate)
    require(embedded_maps(original_doc,original_binary)==embedded_maps(candidate_doc,candidate_binary),
            'Base fit changed original generated maps')
    return candidate,part,links


def material_maps(doc,binary):
    """Reject unhandled visible modifiers; return untouched encoded PNG maps."""
    require(not doc.get('skins') and not doc.get('animations'),'Static detached part required')
    _,_,_,records=raw_corners(doc,binary)
    require(records,'No active rendered mesh primitives')
    references={};limitations=[]
    for primitive in records:
        material=doc['materials'][primitive['material']];pbr=material.get('pbrMetallicRoughness',{})
        require(pbr.get('baseColorFactor',[1,1,1,1])==[1,1,1,1],'Unsupported base-color factor needs explicit material operation')
        require(material.get('alphaMode','OPAQUE')=='OPAQUE','Unsupported alpha material needs explicit operation')
        require(not material.get('extensions') and material.get('emissiveFactor',[0,0,0])==[0,0,0],
                'Unsupported material extension/emissive modifier')
        require('COLOR_0' not in primitive['sourceAttributeAccessors'],'Vertex color needs an explicit native material policy')
        require(material.get('normalTexture',{}).get('scale',1)==1,'Explicit normal-strength operation required')
        for key,texture in [('color',pbr['baseColorTexture']),('normal',material['normalTexture'])]:
            require(texture.get('texCoord',0)==0 and not texture.get('extensions'),'Unchanged TEXCOORD_0 required')
            tex=doc['textures'][texture['index']]
            require(not tex.get('extensions'),'Unsupported texture extension')
            image_index=tex['source']
            require(key not in references or references[key]==image_index,'One common map pair required')
            references[key]=image_index
        limitations.append({'materialIndex':primitive['material'],'doubleSided':material.get('doubleSided',False),
            'packedOcclusionRoughnessMetallicRetainedInGLB':bool(material.get('occlusionTexture') or pbr.get('metallicRoughnessTexture')),
            'nativeRepresentation':'Skin layer0 PLT plus tangent normal map; AO/MR, source sampler and doubleSided are not translated by this adapter.'})
    maps={}
    for key,index in references.items():
        image=doc['images'][index]
        require(image.get('mimeType')=='image/png' and 'bufferView' in image and not image.get('uri'),'Exact embedded PNG maps required')
        view=doc['bufferViews'][image['bufferView']];start=view.get('byteOffset',0);length=view['byteLength']
        require(view.get('buffer',0)==0 and start>=0 and length>0 and start+length<=len(binary),'Embedded image buffer bounds invalid')
        blob=binary[start:start+length]
        with Image.open(BytesIO(blob)) as pixels:
            require(pixels.size==(2048,2048) and pixels.mode in ('RGB','RGBA'),'RGB/RGBA matching2K maps required')
            if pixels.mode=='RGBA':require(np.asarray(pixels)[:,:,3].min()==255,'Nonopaque image alpha needs explicit material operation')
            maps[key]={'imageIndex':index,'blob':blob,'mode':pixels.mode}
    require(set(maps)=={'color','normal'},'Active common color/normal map pair required')
    return maps,limitations


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--part', choices=sorted(JOINTS), required=True)
    parser.add_argument('--stock-bank', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source,part,lineage=receipt_lineage(args.receipt)
    require(part==args.part,'Requested stage side differs from fitted/mirrored receipt')
    doc, binary = read_glb(source)
    maps,limitations=material_maps(doc,binary)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    paths = {}
    map_proofs = {}
    for key, image in maps.items():
        path = output / (key + '.png')
        path.write_bytes(image['blob'])
        require(path.read_bytes()==image['blob'],'PNG extraction changed original encoded image bytes')
        paths[key] = path
        map_proofs[key] = {'imageIndex': image['imageIndex'], 'path': str(path), 'sha256': sha(path),
            'embeddedBlobSha256':hashlib.sha256(image['blob']).hexdigest(),'encodedBytesExact':True,'pixelsExact': True,'mode':image['mode']}
    bank = args.stock_bank.resolve()
    config = {'schemaVersion': 1, 'diagnosticOnly': True, 'slug': 'human_male_fit', 'prefix': 'pmh0',
        'part': args.part, 'model': 'pmh0_' + args.part + '001', 'joint': JOINTS[args.part],
        'stockHeightMeters': 1.9339157, 'appearance': 6, 'raceId': 6, 'gender': 'male',
        'source': str(source), 'color': str(paths['color']), 'normal': str(paths['normal']),
        'stockBaseline': str(bank / 'stock'), 'fixtureBaseline': str(bank / 'fixture'),
        'stageHumanStockComparator': False, 'normalStrength': 1, 'skinLayer': 0, 'equipmentMode': 'stock-identity',
        'inputInventory': str(bank / 'input-inventory.json'), 'inputInventorySha256': sha(bank / 'input-inventory.json'),
        'expectedInputHashes': {'source': sha(source), **{key: sha(path) for key, path in paths.items()}},
        'reviewedFitReceipt': {'path': str(args.receipt.resolve()), 'sha256': sha(args.receipt)},
        'fitReceiptIsUserAcceptance':False,'sourceReceiptLineage':lineage}
    save(output / 'stage-config.json', config)
    save(output / 'map-extraction.json', {'source': str(source), 'sourceSha256': sha(source),
        'helperDependencyHashes':{'stock_limb_contract.py':sha(Path(__file__).with_name('stock_limb_contract.py'))},
        'receipt': str(args.receipt.resolve()), 'receiptSha256': sha(args.receipt), 'maps': map_proofs,
        'normalStrength': 1, 'embeddedMapBytesChanged':False,'sourceMaterialsChanged':False,
        'sourceReceiptLineage':lineage,'materialRepresentationLimitations':limitations,
        'skinOnlyPalettePolicy':'All generated native PLT pixels layer0. Does not independently prove anatomical/texture semantic purity.',
        'clientAccepted': False})
    shutil.copyfile(__file__, output / 'executed-helper.py')
    print(json.dumps({'configuration': str(output / 'stage-config.json'), 'unchangedMapPixels': True}))


if __name__ == '__main__':
    main()
