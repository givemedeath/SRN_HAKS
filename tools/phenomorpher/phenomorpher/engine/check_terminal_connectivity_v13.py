"""Independent source-calibrated seam diagnostics, never anatomy approval.

Terminal eligibility is frozen in source coordinates. Whole-mesh contact at an
unrelated thigh/hand cannot hide a detached connector. Triangle surfaces and
source-offset correspondence are complementary evidence, not intersection gates.
"""
import hashlib
import json
from pathlib import Path
import numpy as np

SEGMENTS={'bicepl':('lbicep_g','lforearm_g'),'bicepr':('rbicep_g','rforearm_g'),
 'forel':('lforearm_g','lhand_g'),'forer':('rforearm_g','rhand_g'),
 'legl':('lthigh_g','lshin_g'),'legr':('rthigh_g','rshin_g'),
 'shinl':('lshin_g','lfoot_g'),'shinr':('rshin_g','rfoot_g')}
LINKS=(('chest','pelvis'),('chest','bicepl'),('chest','bicepr'),
 ('bicepl','forel'),('bicepr','forer'),('forel','handl'),('forer','handr'),
 ('pelvis','legl'),('pelvis','legr'),('legl','shinl'),('legr','shinr'),
 ('shinl','footl'),('shinr','footr'))

def pin(path):
    p=Path(path).resolve();return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}

def load_archive(directory):
    d=Path(directory);pins=[pin(d/'assembly-meta.json'),pin(d/'geometry.npz')]
    meta=json.loads((d/'assembly-meta.json').read_text(encoding='utf-8-sig'))
    with np.load(d/'geometry.npz',allow_pickle=False) as data:
        meshes=[{'part':r['part'],'name':r['name'],'render':r['render'],
                 'position':data[r['positionsKey']].copy(),'faces':data[r['facesKey']].copy()}
                for r in meta['meshes']]
    return meshes,{k:np.asarray(v,float) for k,v in meta['jointFramesMeters'].items()},pins

def controls(left,right,frames):
    p=lambda key:np.asarray(frames[key],float)[:3,3]
    if left in SEGMENTS:
        a,b=SEGMENTS[left];other=SEGMENTS.get(right,(a,b))
        return (p(a),p(b),True),(p(other[0]),p(other[1]),False)
    if (left,right)==('chest','pelvis'):
        return (p('torso_g'),p('neck_g'),False),(p('pelvis_g'),p('torso_g'),True)
    if left=='chest':
        a,b=SEGMENTS[right];return (p('torso_g'),p(a),True),(p(a),p(b),False)
    if left=='pelvis':
        a,b=SEGMENTS[right];return (p('pelvis_g'),p(a),True),(p(a),p(b),False)
    raise ValueError('Unknown anatomical connector')

def terminal_indices(points,start,end,distal,fraction=.25):
    axis=np.asarray(end)-start;n=np.linalg.norm(axis)
    if n<1e-10:raise ValueError('Degenerate connector axis')
    z=(points-start)@(axis/n);lo,hi=z.min(),z.max()
    return np.flatnonzero(z>=hi-fraction*(hi-lo) if distal else z<=lo+fraction*(hi-lo))

def point_triangle_distances(points,triangles):
    """Exact point-to-filled-triangle distance including edges; no vertex-only proxy."""
    points=np.asarray(points,float);tri=np.asarray(triangles,float)
    if not len(points) or not len(tri):raise ValueError('Empty terminal geometry')
    result=[]
    for chunk in np.array_split(points,max(1,int(np.ceil(len(points)/64)))):
        q=chunk[:,None,:];a,b,c=tri[:,0],tri[:,1],tri[:,2]
        best=np.full((len(chunk),len(tri)),np.inf)
        for u,v in ((a,b),(b,c),(c,a)):
            edge=v-u;den=np.sum(edge*edge,axis=1)
            t=np.clip(np.sum((q-u)*edge,axis=2)/np.maximum(den,1e-30),0,1)
            best=np.minimum(best,np.sum((q-(u+t[:,:,None]*edge))**2,axis=2))
        n=np.cross(b-a,c-a);den=np.sum(n*n,axis=1)
        signed=np.sum((q-a)*n,axis=2);proj=q-signed[:,:,None]*n/np.maximum(den,1e-30)[None,:,None]
        signs=[np.sum(np.cross(v-u,proj-u)*n,axis=2) for u,v in ((a,b),(b,c),(c,a))]
        inside=(np.minimum.reduce(signs)>=-1e-15)&(den[None,:]>1e-24)
        best=np.where(inside,np.minimum(best,signed*signed/np.maximum(den,1e-30)),best)
        result.extend(np.sqrt(best.min(axis=1)).tolist())
    return np.asarray(result)

def terminal_geometry(source,fitted,part,control):
    s=[];f=[];st=[];ft=[]
    for sm,fm in zip(source,fitted):
        if sm['part']!=part or not sm.get('render',True):continue
        if (sm['name'],sm['part'])!=(fm['name'],fm['part']) or not np.array_equal(sm['faces'],fm['faces']):
            raise ValueError('Mesh inventory/topology changed')
        p=np.asarray(sm['position']);q=np.asarray(fm['position']);idx=terminal_indices(p,*control)
        if p.shape!=q.shape:raise ValueError('Vertex inventory changed')
        faces=np.asarray(sm['faces'],int);keep=np.all(np.isin(faces,idx),axis=1)
        s.extend(p[idx]);f.extend(q[idx]);st.extend(p[faces[keep]]);ft.extend(q[faces[keep]])
    return tuple(np.asarray(x) for x in (s,f,st,ft))

def distribution(values):
    return {'min':float(np.min(values)),'p10':float(np.quantile(values,.1)),
            'median':float(np.median(values)),'p90':float(np.quantile(values,.9)),'max':float(np.max(values))}

def audit(source,fitted,source_frames,fitted_frames,part_scales=None,raster_uncertainty=.002):
    if len(source)!=len(fitted):raise ValueError('Inventory length changed')
    scales=part_scales or {};rows=[]
    for left,right in LINKS:
        try:
            ca,cb=controls(left,right,source_frames)
            sa,fa,sta,fta=terminal_geometry(source,fitted,left,ca)
            sb,fb,stb,ftb=terminal_geometry(source,fitted,right,cb)
            source_dist=np.r_[point_triangle_distances(sa,stb),point_triangle_distances(sb,sta)]
            fitted_dist=np.r_[point_triangle_distances(fa,ftb),point_triangle_distances(fb,fta)]
            scale=.5*(float(scales.get(left,1))+float(scales.get(right,1)))
            if scale<=0 or not np.isfinite(scale):raise ValueError('Invalid scale')
            threshold=float(np.quantile(source_dist,.1))*scale+raster_uncertainty
            # Source close-neighbour identities preserve offset contact as evidence.
            near=np.sum((sa[:,None]-sb[None])**2,axis=2);j=near.argmin(axis=1)
            sd=np.sqrt(near[np.arange(len(sa)),j]);eligible=sd<=np.quantile(sd,.1)+raster_uncertainty
            gaps=np.linalg.norm(fa[eligible]-fb[j[eligible]],axis=1)
            axis_controls=controls(left,right,fitted_frames)
            axis=axis_controls[0][1]-axis_controls[0][0];axis/=np.linalg.norm(axis)
            axis_gaps={}
            for name,v in [('X',np.array([1.,0,0])),('Y',np.array([0.,1,0])),('Z',np.array([0.,0,1])),('jointLongAxis',axis)]:
                aa=fa@v;bb=fb@v;axis_gaps[name]=float(max(aa.min()-bb.max(),bb.min()-aa.max(),0))
            rows.append({'parts':[left,right],'status':'measured','sourceTerminalSurfaceDistanceMeters':distribution(source_dist),
                'candidateTerminalSurfaceDistanceMeters':distribution(fitted_dist),'sourceDerivedP10ThresholdMeters':threshold,
                'surfaceNearCoverageFraction':float(np.mean(fitted_dist<=threshold)),
                'sourceNearCorrespondenceGapMeters':distribution(gaps),'candidateTerminalProjectionSeparationMeters':axis_gaps,
                'seamWorsenedBeyondSourceRasterBudget':bool(np.quantile(fitted_dist,.1)>threshold),
                'sourceOffsetScaleBasis':scale,'terminalFraction':.25,'sourceCorrespondenceCount':int(eligible.sum())})
        except (KeyError,ValueError) as e:rows.append({'parts':[left,right],'status':'unavailable','reason':str(e)})
    return {'kind':'source-calibrated-terminal-connectivity-diagnostic-v13','connectors':rows,
            'rasterUncertaintyMeters':raster_uncertainty,'assetApprovalCreated':False,'anatomyAcceptance':False,
            'policy':'P10 surface separation and fixed source correspondences diagnose seam worsening. Projection overlap is necessary evidence only, never proof of 3D contact. Source offset gaps are retained; no mandatory full-surface intersection. Native/client/motion and matched visual gates remain required.'}

def audit_archives(source_directory,candidate_directory,part_scales=None):
    source,sf,sp=load_archive(source_directory);candidate,cf,cp=load_archive(candidate_directory)
    result=audit(source,candidate,sf,cf,part_scales);pins=sp+cp
    for row in pins:
        if pin(row['path'])!=row:raise ValueError('Archive changed during audit')
    result['inputPins']=pins;result['inputsUnchanged']=True
    return result
