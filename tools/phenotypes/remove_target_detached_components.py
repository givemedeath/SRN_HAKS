"""Remove explicitly measured, fully detached generator components.

Retain exact source face order, all original attributes and embedded maps.
This operation never classifies an inner sheet or repairs a connected surface.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import numpy as np

import target_contract as contract
from conservative_face_selection import descendant, mesh_arrays, topology
from place_purposebuilt_pelvis import raw_corners, read_glb
from repair_target_part_faces import repair_archive, frozen_receipt_inputs
from target_part_pipeline import pin, read_target, verify_source_receipt


def digest_ids(ids):
    return hashlib.sha256(np.asarray(ids, dtype='<i8').tobytes()).hexdigest()


def vertex_components(positions, faces):
    """Read-only exact coordinate connectivity includes point contacts."""
    _, inverse = np.unique(positions, axis=0, return_inverse=True)
    triangles = inverse[faces]
    roots = np.arange(int(inverse.max())+1)
    def find(value):
        while roots[value] != value:
            roots[value] = roots[roots[value]]
            value = int(roots[value])
        return value
    for a, b, c in triangles:
        first = find(int(a))
        for value in (b, c):
            other = find(int(value))
            if other != first:
                roots[other] = first
    owners = np.asarray([find(int(row[0])) for row in triangles])
    groups = [np.flatnonzero(owners == value) for value in np.unique(owners)]
    return sorted(groups, key=lambda row: (-len(row), int(row[0])))


def catalogue(positions, faces):
    groups = vertex_components(positions, faces)
    rows = []
    for ids in groups:
        corners = positions[faces[ids]].astype(float)
        area = np.linalg.norm(np.cross(corners[:,1]-corners[:,0],
                                       corners[:,2]-corners[:,0]), axis=1)*.5
        rows.append({'seedSourceFaceId':int(ids[0]), 'faceCount':len(ids),
                     'faceIdsSha256':digest_ids(ids),
                     'boundsLocalMetres':[corners.min((0,1)).tolist(),corners.max((0,1)).tolist()],
                     'surfaceAreaMetresSquared':float(area.sum())})
    return groups, rows


def select_components(positions, faces, requested, maximum_fraction):
    contract.require(type(maximum_fraction) in (float,int) and
                     0 < maximum_fraction <= .10,
                     'Explicit removal fraction at most ten percent required')
    contract.require(type(requested) is list and len(requested)>0,
                     'Explicit measured detached components required')
    groups, rows = catalogue(positions, faces)
    found = []
    for record in requested:
        contract.require(type(record) is dict and set(record)==
                         {'seedSourceFaceId','faceCount','faceIdsSha256','reason'},
                         'Exact component seed/count/hash/reason required')
        seed=record['seedSourceFaceId']
        contract.require(type(seed) is int and 0<=seed<len(faces),
                         'Valid original source face seed required')
        matches=[i for i,ids in enumerate(groups) if seed in ids]
        contract.require(len(matches)==1,'Component seed membership differs')
        index=matches[0]
        contract.require(index!=0,'Largest anatomical component must remain protected')
        row=rows[index]
        contract.require(type(record['faceCount']) is int and
                         record['faceCount']==row['faceCount'] and
                         record['faceIdsSha256']==row['faceIdsSha256'],
                         'Measured component membership/count changed')
        contract.require(isinstance(record['reason'],str) and record['reason'].strip(),
                         'Measured component removal reason required')
        contract.require(index not in found,'Repeated detached component request')
        found.append(index)
    removed=np.sort(np.concatenate([groups[i] for i in found]))
    contract.require(len(removed)/len(faces)<=maximum_fraction,
                     'Measured detached removal exceeds explicit fraction')
    kept=np.setdiff1d(np.arange(len(faces),dtype=np.int64),removed)
    # Exact point disjointness is stronger than shared-edge disjointness.
    retained_positions=np.unique(positions[faces[kept]].reshape(-1,3),axis=0)
    removed_positions=np.unique(positions[faces[removed]].reshape(-1,3),axis=0)
    joined=np.concatenate((retained_positions,removed_positions))
    contract.require(len(np.unique(joined,axis=0))==len(joined),
                     'Removed region contacts retained anatomy')
    return kept, removed, rows, [rows[i] for i in found]


def execute(config_path, output):
    config_path=Path(config_path).resolve()
    cfg=json.loads(config_path.read_text(encoding='utf-8'))
    allowed={'schemaVersion','kind','diagnosticOnly','targetContract','targetContractSha256',
             'part','coordinateSpace','source','sourceSha256','sourceReceipt',
             'sourceReceiptSha256','removedComponents','maximumRemovedFaceFraction',
             'measurementReceipt','protectedInputs','notes'}
    contract.require(set(cfg)<=allowed and cfg.get('kind')=='target-detached-component-removal'
                     and cfg.get('diagnosticOnly') is True,'Explicit detached removal controls required')
    target_path,target=read_target(cfg)
    contract.require(cfg['coordinateSpace']=='working','Remove debris before runtime conversion')
    source=pin(cfg['source'],cfg['sourceSha256'])
    parent_path=pin(cfg['sourceReceipt'],cfg['sourceReceiptSha256'])
    parent=verify_source_receipt(source,parent_path,target_path,target,cfg['part'],'working')
    contract.require(parent['operation']=='fit' and not parent['proof']['reflected'],
                     'Original proper fitted parent required; repeated repair rejected')
    measured=cfg['measurementReceipt']
    contract.require(type(measured) is dict and set(measured)=={'path','sha256'},
                     'Pinned detached-component measurement required')
    measurement=pin(measured['path'],measured['sha256'])
    measurement_doc=json.loads(measurement.read_text(encoding='utf-8'))
    contract.require(measurement_doc.get('kind')=='target-detached-component-measurement'
                     and measurement_doc.get('schemaVersion')==2,'Bound component measurement receipt required')
    contract.verify_binding(measurement_doc,target_path,target,'working')
    contract.require(measurement_doc.get('part')==cfg['part']
                     and measurement_doc.get('source')==str(source)
                     and measurement_doc.get('sourceSha256')==contract.sha(source)
                     and measurement_doc.get('sourceReceiptSha256')==contract.sha(parent_path),
                     'Component measurement belongs to another source/part')
    inputs={str(p):contract.sha(p) for p in (config_path,target_path,source,parent_path,measurement)}
    inputs.update(frozen_receipt_inputs(parent))
    for name,expected in cfg.get('protectedInputs',{}).items():
        inputs[str(pin(name,expected))]=expected
    helpers=('remove_target_detached_components.py','conservative_face_selection.py',
             'repair_target_part_faces.py','target_part_pipeline.py','target_contract.py',
             'place_purposebuilt_pelvis.py')
    for name in helpers:
        path=Path(__file__).with_name(name).resolve();inputs[str(path)]=contract.sha(path)
    doc,blob=read_glb(source);positions,faces,_=mesh_arrays(doc,blob)
    kept,removed,rows,removed_rows=select_components(positions,faces,cfg['removedComponents'],
                                                     cfg['maximumRemovedFaceFraction'])
    contract.require(measurement_doc.get('componentCatalogue')==rows,
                     'Component measurement no longer reproduces exact catalogue')
    corner_path=pin(parent['nativeCornerArchive']['path'],parent['nativeCornerArchive']['sha256'])
    inputs[str(corner_path)]=contract.sha(corner_path)
    with np.load(corner_path,allow_pickle=False) as old:
        archive=repair_archive({key:old[key] for key in old.files},faces,kept,np.empty((0,3),np.int64))
    before=topology(positions,faces)
    output=Path(output).resolve()
    contract.require(not output.exists(),'Fresh immutable component repair required')
    output.mkdir(parents=True)
    candidate=output/'candidate-local.glb';proof=descendant(source,candidate,kept)
    after=proof['afterTopology']
    for key in ('boundaryEdges','nonmanifoldEdges','nonmanifoldVertexLinks',
                'inconsistentManifoldEdgeWindings','zeroAreaFaces'):
        contract.require(after[key]<=before[key],'Detached removal introduced topology defect: '+key)
    p,n,uv,_=raw_corners(*read_glb(candidate))
    contract.require(np.array_equal(p,raw_corners(doc,blob)[0][kept]) and
                     np.array_equal(n,raw_corners(doc,blob)[1][kept]) and
                     np.array_equal(uv,raw_corners(doc,blob)[2][kept]),
                     'Retained encoded corner attributes changed')
    corners=output/'native-corners.npz';np.savez_compressed(corners,**archive)
    membership=output/'component-membership.npz'
    np.savez_compressed(membership,sourceFaces=faces,keptSourceFaceIds=kept,
                        removedSourceFaceIds=removed)
    snapshots={}
    for name in helpers:
        original=Path(__file__).with_name(name).resolve()
        saved=output/'helper-snapshots'/name;saved.parent.mkdir(exist_ok=True)
        shutil.copyfile(original,saved)
        snapshots[str(original)]={'snapshot':str(saved),'sha256':contract.sha(saved)}
    receipt={'schemaVersion':2,'kind':'target-part-geometry','operation':'detached-component-removal',
             **contract.binding(target_path,target,'working'),'part':cfg['part'],
             'joint':parent['joint'],'model':parent['model'],'sourcePart':cfg['part'],
             'source':str(source),'sourceSha256':contract.sha(source),
             'sourceReceipt':str(parent_path),'sourceReceiptSha256':contract.sha(parent_path),
             'candidate':str(candidate),'candidateSha256':contract.sha(candidate),
             'nativeCornerArchive':{'path':str(corners),'sha256':contract.sha(corners)},
             'componentMembership':{'path':str(membership),'sha256':contract.sha(membership)},
             'statureApplications':0,'sourceToAttachmentLocal':np.eye(4).tolist(),
             'attachmentWorld':parent['attachmentWorld'],'reflectionWorld':None,
             'proof':{**proof,'beforeTopology':before,'componentCatalogue':rows,
                      'removedComponents':removed_rows,'retainedDoublePrecisionCornersExact':True,
                      'noPointContactsBetweenRemovedAndRetainedComponents':True,
                      'maximumRemovedFaceFraction':cfg['maximumRemovedFaceFraction']},
             'frozenInputs':inputs,'helperSnapshots':snapshots,'diagnosticOnly':True,
             'rigMode':contract.rig_mode(target),'rigValidated':contract.rig_ready(target),
             'rigPilotAccepted':False,'clientAccepted':False,'productionAccepted':False,
             'limitation':'Detached debris only; connected interior shells, anatomy, garments and posed interfaces remain separately open.'}
    for name,expected in inputs.items():pin(name,expected)
    path=output/'geometry.json';path.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    return path


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();path=execute(args.config,args.output)
    print(json.dumps({'receipt':str(path),'sha256':contract.sha(path)}))
