"""Read-only recipe, footprint and corner audit of a bounded Troll diagnostic.

This additional receipt is required for any future explicit diagnostic adapter;
it does not authorize stage/native/client use or conceal original source defects.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import numpy as np
from bounded_pelvis_connector_v2 import build_cap, signed_area
from place_purposebuilt_pelvis import read_glb, accessor


def require(ok, msg):
    if not ok: raise ValueError(msg)


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def stamp(p): return {'path': str(Path(p).resolve()), 'sha256': sha(p)}


def load_primitives(doc, binary):
    result=[]
    for prim in doc['meshes'][0]['primitives']:
        attrs={key:accessor(doc,binary,index) for key,index in prim['attributes'].items()}
        f=accessor(doc,binary,prim['indices']).reshape(-1,3).astype(np.int64)
        result.append((attrs,f))
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--diagnostic',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    require(not args.output.exists(),'Fresh audit directory required');d=json.loads(args.diagnostic.read_text())
    require(d['kind']=='bounded-troll-pelvis-port-diagnostic' and d['targetId']=='troll-male-muscular-purposebuilt-v1' and
            d['part']=='pelvis' and d['coordinateSpace']=='working' and d['statureApplications']==0 and
            all(d[k] is False for k in ('selectionMade','materialAccepted','anatomyAccepted','productionAccepted','clientAccepted','closedExteriorClaim')),
            'Unaccepted Troll-only bounded identity required')
    for path,h in d['frozenInputs'].items():require(sha(path)==h,'Frozen input changed')
    require(sha(d['targetContract'])==d['targetContractSha256'],'Frozen target changed')
    config=json.loads(Path(d['config']['path']).read_text());require(sha(d['config']['path'])==d['config']['sha256'],'Configuration changed')
    pins=config['inputs'];design=json.loads(Path(pins['geometryDesign']['path']).read_text())
    recipe_path=Path(design['config']['path']);require(sha(recipe_path)==design['config']['sha256'],'Geometry recipe changed')
    recipe=json.loads(recipe_path.read_text());require(recipe['insetFraction']==.01 and recipe['dropSource']==.001,'Reviewed shallow recipe changed')
    source_doc,source_bin=read_glb(d['source']['path']);source_rows=load_primitives(source_doc,source_bin)
    sp,sf=source_rows[0][0]['POSITION'],source_rows[0][1]
    mapping=np.load(d['faceMapping']['path']);require(sha(d['faceMapping']['path'])==d['faceMapping']['sha256'],'Face mapping changed')
    kept,deleted=mapping['keptOriginalFaceIds'],mapping['deletedOriginalFaceIds']
    proposal=np.load(pins['faceSelection']['path'])
    require(np.array_equal(deleted,proposal['foundation4598IncludingOrphanDeletedOriginalFaceIds']) and
            np.array_equal(kept,proposal['foundation4598IncludingOrphanKeptOriginalFaceIds']) and
            np.array_equal(mapping['sourceOriginalFaces'],sf),'Exact removal mapping changed')
    fit=json.loads(Path(d['properFit']['path']).read_text());fd,fb=read_glb(fit['candidate']);fp=load_primitives(fd,fb)[0][0]['POSITION']
    port_rows=[];checks=[]
    for space in ('source','working'):
        ex=d['exports'][space];require(sha(ex['candidate']['path'])==ex['candidate']['sha256'],'Export hash changed')
        doc,blob=read_glb(ex['candidate']['path']);rows=load_primitives(doc,blob)
        parent_doc,parent_bin,parentp=(source_doc,source_bin,sp) if space=='source' else (fd,fb,fp)
        require(blob[:len(parent_bin)]==parent_bin,'Original full BIN prefix changed')
        require(np.array_equal(rows[0][1],sf[kept]),'Original corner order changed')
        for key,values in rows[0][0].items():
            parent=accessor(parent_doc,parent_bin,parent_doc['meshes'][0]['primitives'][0]['attributes'][key])
            require(np.array_equal(values,parent),'Outside attribute changed: '+key)
        checks.append(space+': literal original BIN/attributes/corners unchanged')
        for i,side in enumerate(('left','right'),1):
            originalrows=mapping[side+'CapOriginalPortRows'];ring=sp[originalrows].astype(float)
            reproduced=build_cap(ring,recipe['insetFraction'],recipe['dropSource'])
            expected=mapping[side+'CapTopologyPositionsSource'];faces=mapping[side+'CapTopologyFaces']
            require(np.array_equal(expected,reproduced['positions'].astype(np.float32)) and
                    np.array_equal(faces,reproduced['faces']) and
                    np.array_equal(mapping[side+'CapEarPartition'],reproduced['ears']) and
                    np.array_equal(mapping[side+'CapFaceEarOwnership'],reproduced['faceEar']), 'Frozen cap recipe cannot reproduce')
            topologypos=mapping[side+'CapTopologyPositions'+space.title()]
            attrs,cf=rows[i]
            require(np.array_equal(attrs['POSITION'][cf],topologypos[faces]),'Serialized cap corner mapping changed')
            require(np.array_equal(topologypos[:68],parentp[originalrows]),'Fixed original ring changed')
            boundary={tuple(map(tuple,(topologypos[j],topologypos[(j+1)%68]))):1 for j in range(68)}
            edgeowners={}
            for tri in topologypos[faces]:
                for a,b in zip(tri,np.roll(tri,-1,axis=0)):
                    key=tuple(sorted((tuple(a),tuple(b))));edgeowners.setdefault(key,[]).append((tuple(a),tuple(b)))
            single={v[0] for v in edgeowners.values() if len(v)==1}
            require(single==set(boundary) and all(len(v) in (1,2) and (len(v)==1 or v[0]==v[1][::-1]) for v in edgeowners.values()),'Projected cap disk boundary/winding changed')
            xyz=attrs['POSITION'][cf].astype(float);cross=np.cross(xyz[:,1]-xyz[:,0],xyz[:,2]-xyz[:,0])
            require(np.all(cross[:,1]<0),'Projected cap orientation reverses')
            expected_area=signed_area(parentp[originalrows][:,[0,2]].astype(float));actual_area=float(-cross[:,1].sum()/2)
            require(abs(expected_area-actual_area)<1e-12,'Projected footprint coverage changed')
            audit=ex['geometryAudit'];require(all(audit['checks'].values()) and not any(c['bodyIntersection']['forbiddenContacts'] or c['selfIntersection']['forbiddenContacts'] for c in audit['caps']), 'Final serialized contact audit failed')
            port_rows.append({'space':space,'side':side,'recipeReproducedExactly':True,'exactFixedBoundaryAndOpposedInternalEdges':True,
                'projectedFacesStrictlyOrientationPreserving':True,'expectedPortArea':expected_area,'serializedCapProjectedArea':actual_area,
                'maximumCoverageAreaError':abs(expected_area-actual_area),'newOutsideOriginalFootprint':False,
                'proof':'Coherent disk with exact simple port boundary and strictly positive projected Jacobian; exact signed area coverage and no non-shared cap intersections prove injective coverage of that footprint.'})
    args.output.mkdir(parents=True);snap=args.output/'helper-snapshots';snap.mkdir()
    for path in (Path(__file__),Path(__file__).with_name('bounded_pelvis_connector_v2.py'),Path(__file__).with_name('place_purposebuilt_pelvis.py')):
        shutil.copyfile(path,snap/path.name)
    evidence={'schemaVersion':1,'kind':'independent-bounded-troll-pelvis-diagnostic-recipe-audit','diagnostic':stamp(args.diagnostic),
        'recipe':stamp(recipe_path),'ports':port_rows,'checks':checks,'exactRecipeAndFootprintVerified':True,
        'originalOutsideAttributeAndCornerBytesVerified':True,'topologyAndIntersections':{s:d['exports'][s]['geometryAudit'] for s in ('source','working')},
        'pending':'Neutral cap material lacks final skin/garment atlas ownership; original coincident pairs and bad normal remain; existing closed target-part lineage unsupported.',
        'selectionMade':False,'anatomyAccepted':False,'materialAccepted':False,'productionAccepted':False,'clientAccepted':False}
    path=args.output/'audit.json';path.write_text(json.dumps(evidence,indent=2)+'\n');print(json.dumps({'audit':stamp(path),'ports':port_rows}),flush=True)


if __name__=='__main__':main()
