"""Disposable proper-rotation/uniform-scale trials on a frozen capped pelvis.

No mesh/cap/atlas editing: add one glTF scene wrapper and rotate authoritative
native normals by proper R only. Original BIN/material/UV bytes remain exact.
"""
import argparse,copy,json,hashlib,shutil
from pathlib import Path
import numpy as np
from place_purposebuilt_pelvis import read_glb,write_glb,rotation_xyz,BASIS,sha

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ['baseline','config','output']:ap.add_argument('--'+name,type=Path,required=True)
    args=ap.parse_args();assert not args.output.exists()
    config=json.loads(args.config.read_text());allowed={'diagnosticOnly','label','baselineGlbSha256','baselineReceiptSha256','baselineArchiveSha256','baselineReceiptKind','uniformScale','rotationDegreesXYZ','anchorPelvisLocal','translationPelvisLocal','landmarkNotes'}
    if set(config)-allowed or config.get('diagnosticOnly') is not True:raise RuntimeError('Unknown postfit controls')
    kind=config.get('baselineReceiptKind','conditioning')
    if kind not in ['conditioning','cap-material','cap-shaping','cut-preview','rim-polish']:raise RuntimeError('Unknown baseline receipt kind')
    receiptpath=args.baseline/({'conditioning':'conditioning.json','cap-material':'cap-skin-material.json','cap-shaping':'cap-shaping.json','cut-preview':'cut-preview.json','rim-polish':'rim-polish.json'}[kind]);base=json.loads(receiptpath.read_text())
    source=Path(base['conditionedSource']['path'] if kind=='cap-material' else base['candidate']);archive=Path(base['nativeCornerArchive']['path'])
    expected_source_sha=base['conditionedSource']['sha256'] if kind=='cap-material' else base['candidateSha256']
    if sha(source)!=expected_source_sha or sha(archive)!=base['nativeCornerArchive']['sha256']:
        raise RuntimeError('Baseline receipt self-association changed')
    for actual,key in [(source,'baselineGlbSha256'),(receiptpath,'baselineReceiptSha256'),(archive,'baselineArchiveSha256')]:
        if sha(actual)!=config[key]:raise RuntimeError('Frozen baseline association changed '+key)
    scale=float(config['uniformScale']);degrees=np.asarray(config['rotationDegreesXYZ'],float);anchor=np.asarray(config['anchorPelvisLocal'],float)
    if any(row.shape!=(3,) or not np.isfinite(row).all() for row in [degrees,anchor]):
        raise RuntimeError('Finite three-dimensional rotation and anchor required')
    r=rotation_xyz(degrees)
    translation=np.asarray(config.get('translationPelvisLocal',[0,0,0]),float)
    if translation.shape!=(3,) or not np.isfinite(translation).all() or abs(translation).max()>.015:raise RuntimeError('Outside declared small translation trial bounds')
    if not(.96<=scale<=1.04 and np.linalg.det(r)>0 and np.allclose(r.T@r,np.eye(3),atol=1e-12)):raise RuntimeError('Outside declared uniform/proper trial bounds')
    if abs(degrees[0])>6 or degrees[1]!=0 or degrees[2]!=0:raise RuntimeError('Outside declared X-pitch-only trial bounds')
    args.output.mkdir(parents=True);doc,binary=read_glb(source);originaldoc=copy.deepcopy(doc)
    affine=anchor+translation-scale*r@anchor
    matrix=np.eye(4);matrix[:3,:3]=BASIS.T@r@BASIS*scale;matrix[:3,3]=BASIS.T@affine
    roots=doc['scenes'][doc.get('scene',0)]['nodes'];wrapper=len(doc['nodes'])
    doc['nodes'].append({'name':'Declared diagnostic postfit similarity','matrix':matrix.flatten(order='F').tolist(),'children':list(roots)})
    doc['scenes'][doc.get('scene',0)]['nodes']=[wrapper]
    candidate=args.output/'postfit-local.glb';write_glb(candidate,doc,binary)
    sourcearrays=np.load(archive);arrays={key:sourcearrays[key] for key in sourcearrays.files}
    p=arrays['positions'];n=arrays['normals'];pp=p@r.T*scale+affine;nn=n@r.T
    arrays['positions']=pp;arrays['normals']=nn
    arrays['postFitBasePositions']=p;arrays['postFitBaseNormals']=n
    native=args.output/'conditioned-corners.npz';np.savez_compressed(native,**arrays)
    actualdoc,actualbin=read_glb(candidate)
    proof={'originalBinByteExact':binary==actualbin,'sourceNodesUnchanged':actualdoc['nodes'][:-1]==originaldoc['nodes'],'materialsMapsUvIndicesExact':all(actualdoc.get(key)==originaldoc.get(key) for key in ['materials','textures','images','meshes','accessors','bufferViews','buffers']),
        'normalLengthsPreservedMaximumError':float(abs(np.linalg.norm(n,axis=2)-np.linalg.norm(nn,axis=2)).max()),'uniformTriangleEdgeMaximumError':float(abs(np.linalg.norm(pp[:,1]-pp[:,0],axis=1)-scale*np.linalg.norm(p[:,1]-p[:,0],axis=1)).max()),'nativeUvExact':np.array_equal(arrays['uvNative'],sourcearrays['uvNative']),'capDomainUvExact':np.array_equal(arrays['capUVLocal'],sourcearrays['capUVLocal'],equal_nan=True),'normalPolicy':'Proper rotation only, no inverse-scale/recompute/normalization','anchorPositionError':float(abs(anchor@r.T*scale+affine-anchor-translation).max())}
    result={'diagnosticOnly':True,'configuration':config,'baselineReceiptKind':kind,'baselineReceipt':str(receiptpath.resolve()),'baselineReceiptSha256':sha(receiptpath),'baselineSource':str(source.resolve()),'baselineSourceSha256':sha(source),'baselineNativeCornerArchive':{'path':str(archive.resolve()),'sha256':sha(archive)},'candidate':str(candidate.resolve()),'candidateSha256':sha(candidate),'nativeCornerArchive':{'path':str(native.resolve()),'sha256':sha(native)},'properRotationMatrix':r.tolist(),'rawWrapperMatrix':matrix.tolist(),'nativeAffineTranslation':affine.tolist(),'targetBoundsPelvisLocal':{'min':pp.min((0,1)).tolist(),'max':pp.max((0,1)).tolist(),'extent':np.ptp(pp.reshape(-1,3),axis=0).tolist()},'proof':proof,'limitation':'Disposable fitting trial only; prior capped baseline and protected torso unchanged. SourceFace/barycentric provenance now composes through this explicit postfit similarity; no stager acceptance implied.'}
    (args.output/'postfit.json').write_text(json.dumps(result,indent=2)+'\n')
    if kind in ['conditioning','rim-polish']:
        replacement_base=args.baseline
    elif kind=='cap-material':
        # A sequential repair/shaping material receipt records the original
        # conditioning receipt in its proof; use only its preview context.
        geometry_context=base.get('geometryReceipt',base.get('proof',{}).get('originalGeometryReceipt'))
        if not geometry_context or sha(Path(geometry_context['path']))!=geometry_context['sha256']:
            raise RuntimeError('Material preview geometry context is missing or changed')
        replacement_base=Path(geometry_context['path']).parent
    elif kind=='cut-preview':
        context=base['previewContext']
        if sha(Path(context['path']))!=context['sha256']:
            raise RuntimeError('Cut preview context changed')
        replacement_base=Path(context['path']).parent
    else:
        replacement_base=Path(base['selectedPostFitReceipt']['path']).parent
    replacement=json.loads((replacement_base/'stock-replacement.json').read_text());replacement['parts']['pelvis']=str(candidate.resolve());replacement['label']=config['label'];replacement['postFitReceipt']=str((args.output/'postfit.json').resolve());(args.output/'stock-replacement.json').write_text(json.dumps(replacement,indent=2)+'\n')
    shutil.copy2(args.config,args.output/'executed-config.json');shutil.copy2(__file__,args.output/'executed-helper.py')
    print(json.dumps({'candidate':str(candidate),'sha256':result['candidateSha256'],'bounds':result['targetBoundsPelvisLocal'],'proof':proof}))
if __name__=='__main__':main()
