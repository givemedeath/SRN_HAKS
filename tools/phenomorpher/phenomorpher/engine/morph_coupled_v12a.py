"""Canonical-pose shape fitting with explicit shared-source join reconciliation.

No rig, rotations, authored topology, textures or native resources are written.
Uniform per-part fitting is a separate input stage. Original source shape remains
the correspondence authority; close source terminals receive a common endpoint.
"""
import numpy as np
from .silhouette_model import cross_section,measure
from .fit_morph_preview_v11 import copy_meshes,geometry_hash,orthogonal_arm_width
from .morph_preview_pose_v10 import pose_rigid_meshes

LINKS=(('chest','pelvis'),
       ('chest','bicepl'),('chest','bicepr'),('bicepl','forel'),('bicepr','forer'),
       ('forel','handl'),('forer','handr'),('pelvis','legl'),('pelvis','legr'),
       ('legl','shinl'),('legr','shinr'),('shinl','footl'),('shinr','footr'))
GROUPS={'torso':('chest','pelvis'), 'leftLeg':('legl','shinl','footl'),
        'rightLeg':('legr','shinr','footr')}

def interpolate(z,knots):
    rows=sorted(knots);x=np.array([r[0] for r in rows]);y=np.array([r[1] for r in rows])
    if len(x)==1:return np.full_like(np.asarray(z,float),y[0])
    i=np.clip(np.searchsorted(x,z,side='right')-1,0,len(x)-2)
    t=np.clip((np.asarray(z)-x[i])/(x[i+1]-x[i]),0,1)
    t=t*t*(3-2*t)
    return y[i]+t*(y[i+1]-y[i])

def slice_bounds(meshes,z,axis):
    values=[]
    for m in meshes:
        if not m.get('render',True):continue
        p=np.asarray(m['position']);tri=p[np.asarray(m['faces'])];d=tri[:,:,2]-z
        for a,b in ((0,1),(1,2),(2,0)):
            on=np.abs(d[:,a])<1e-9
            values.extend(tri[on,a,axis].tolist())
            cross=d[:,a]*d[:,b]<0
            t=d[cross,a]/(d[cross,a]-d[cross,b])
            values.extend((tri[cross,a,axis]+t*(tri[cross,b,axis]-tri[cross,a,axis])).tolist())
    return (float(min(values)),float(max(values))) if len(values)>1 else None

def desired(packet,key):
    row=packet.get('proposedTargets',{}).get(key,{})
    value=row.get('modelFittingMeters')
    return float(value) if value is not None and np.isfinite(value) and value>0 else None

def reconcile_joins(source,fitted,links=LINKS,max_source_gap=.012,influence=.10):
    """Common source-correspondence endpoints plus broad smooth displacement.

    Only pairs already close in the donor are joined. No new hidden connectors
    are fabricated. Correspondence distances and remaining endpoint gaps are
    reported; finite correspondence is not visual or motion acceptance.
    """
    result=copy_meshes(fitted);report=[];constraints={}
    for left,right in links:
        ai=[i for i,m in enumerate(source) if m['part']==left and m.get('render',True)]
        bi=[i for i,m in enumerate(source) if m['part']==right and m.get('render',True)]
        pairs=[]
        for a in ai:
            pa=np.asarray(source[a]['position'])
            for b in bi:
                pb=np.asarray(source[b]['position'])
                for start in range(0,len(pa),128):
                    distance=np.sum((pa[start:start+128,None,:]-pb[None,:,:])**2,axis=2)
                    near=np.argmin(distance,axis=1);good=np.flatnonzero(distance[np.arange(len(near)),near]<=max_source_gap**2)
                    pairs.extend((a,start+int(i),b,int(near[i])) for i in good)
        if not pairs:
            report.append({'parts':[left,right],'status':'source correspondence unavailable','pairs':0});continue
        before=[]
        for a,ia,b,ib in pairs:
            qa=np.asarray(fitted[a]['position'])[ia];qb=np.asarray(fitted[b]['position'])[ib]
            common=(qa+qb)/2;before.append(float(np.linalg.norm(qa-qb)))
            for index,vertex,q in ((a,ia,qa),(b,ib,qb)):
                constraints.setdefault((index,vertex),[]).append(common-q)
        report.append({'parts':[left,right],'pairs':len(pairs),'maxGapBeforeMeters':max(before),'status':'shared source terminal correction'})
    # Correct each mesh once with all of its terminals, so successive joins do
    # not erase previous changes. Smooth support spans eligible anatomy.
    for index,m in enumerate(result):
        rows=[(vertex,np.mean(v,axis=0)) for (i,vertex),v in constraints.items() if i==index]
        if not rows:continue
        points=np.asarray(source[index]['position']);anchors=points[[r[0] for r in rows]];delta=np.array([r[1] for r in rows])
        correction=np.zeros_like(points)
        for start in range(0,len(points),128):
            dist=np.linalg.norm(points[start:start+128,None,:]-anchors[None,:,:],axis=2)
            near=dist.argmin(axis=1);d=dist[np.arange(len(near)),near]
            t=np.clip(dist/influence,0,1);support=1-t*t*(3-2*t)
            weights=support/np.maximum(dist,1e-10)**2
            denominator=weights.sum(axis=1)
            mapped=np.divide(weights@delta,denominator[:,None],out=np.zeros((len(near),3)),where=denominator[:,None]>0)
            outer=np.clip(d/influence,0,1);envelope=1-outer*outer*(3-2*outer)
            correction[start:start+len(near)]=mapped*envelope[:,None]
        m['position']+=correction
    # Endpoint residuals include many-to-one correspondence compromises.
    max_residual=0.
    for (i,v),values in constraints.items():
        intended=np.asarray(fitted[i]['position'])[v]+np.mean(values,axis=0)
        max_residual=max(max_residual,float(np.linalg.norm(result[i]['position'][v]-intended)))
    return result,{'joins':report,'endpointCorrectionResidualMeters':max_residual,
                   'sourceGapThresholdMeters':max_source_gap,'influenceSourceMeters':influence,
                   'visualAcceptance':False,'motionAcceptance':False}

def fit_stage2(stage1,packet,source_standing_meshes,preserve=False):
    base=stage1['standingMeshes'];world=stage1['standingFrames'];out=copy_meshes(base)
    if preserve:return {**stage1,'receipt':{'identityPreserved':True,'sourceGeometryHash':geometry_hash(base),'previewGeometryHash':geometry_hash(out),'shapeMorphApplied':False}}
    measured=measure(base,{k:v[:3,3].tolist() for k,v in world.items()})
    floor=measured['boundsMeters'][0][2];height=measured['bindStatureMeters']
    plane={s:floor+float(packet['views']['front'][s+'Height']['value'])*height for s in ('chest','waist','midThigh','knee','calf','ankle')}
    profiles={};deferred=[]
    for group,parts in GROUPS.items():
        selected=[m for m in base if m['part'] in parts and m.get('render',True)]
        if not selected:continue
        points=np.concatenate([m['position'] for m in selected]);lo,hi=points[:,2].min(),points[:,2].max()
        sections=('waist','chest') if group=='torso' else ('ankle','calf','knee','midThigh')
        profiles[group]={'parts':parts,'axes':{}}
        for axis,suffix in ((0,'Width'),(1,'Depth')):
            knots=[]
            for section in sections:
                z=plane[section];goal=desired(packet,section+suffix)
                bounds=slice_bounds(selected,z,axis)
                if goal is None or bounds is None or bounds[1]-bounds[0]<1e-5:continue
                ratio=goal/(bounds[1]-bounds[0])
                if not .35<=ratio<=2.5:
                    deferred.append({'key':section+suffix,'ratio':ratio,'reason':'recommendation exceeds pilot deformation bound; retained residual'});continue
                knots.append((z,ratio))
            if group!='torso':
                foot='footl' if group=='leftLeg' else 'footr'
                feet=[m['position'] for m in base if m['part']==foot and m.get('render',True)]
                goal=desired(packet,'footWidth' if axis==0 else 'footLength')
                if feet and goal is not None:
                    fp=np.concatenate(feet);extent=float(np.ptp(fp[:,axis]));fz=float(fp[:,2].min()+.25*np.ptp(fp[:,2]))
                    ratio=goal/extent if extent>1e-5 else None
                    if ratio is not None and .35<=ratio<=2.5:knots.append((fz,ratio))
            if not knots:continue
            # Endpoint factors continue the nearest supported section through
            # source overlap. Forcing1 at an arbitrary mesh cap creates a shelf.
            profiles[group]['axes'][str(axis)]=knots
            samples=np.linspace(lo+1e-6,hi-1e-6,120);centers=[]
            for z in samples:
                bounds=slice_bounds(selected,z,axis)
                centers.append(np.mean(bounds) if bounds else np.nan)
            good=np.isfinite(centers);centers=np.interp(samples,samples[good],np.asarray(centers)[good])
            for m in out:
                if m['part'] not in parts:continue
                p=m['position'];c=np.interp(p[:,2],samples,centers)
                p[:,axis]=c+(p[:,axis]-c)*interpolate(p[:,2],knots)
    # Front-normal arm width only. Depth stays unavailable unless measured;
    # uniform stage-one limb volume is the explicit default for that axis.
    arm_receipts=[]
    for side,parts in (('l',('bicepl','forel','handl')),('r',('bicepr','forer','handr'))):
        for part,key,a,b in ((parts[0],'upperArmWidth',side+'bicep_g',side+'forearm_g'),(parts[1],'forearmWidth',side+'forearm_g',side+'hand_g')):
            goal=desired(packet,key);selected=[m for m in base if m['part']==part]
            start=world[a][:3,3];end=world[b][:3,3];value=orthogonal_arm_width(selected,start,end)
            if goal is None or value is None or value<1e-5:continue
            ratio=goal/value
            if not .35<=ratio<=2.5:deferred.append({'key':key,'ratio':ratio});continue
            axis=end-start;axis[1]=0;axis/=np.linalg.norm(axis);transverse=np.array([axis[2],0,-axis[0]])
            for m in out:
                if m['part']!=part:continue
                p=m['position'];radial=(p-start)@transverse
                p+=(ratio-1)*radial[:,None]*transverse
            arm_receipts.append({'part':part,'axis':'front bone-normal only','factor':ratio,'depth':'unavailable; stage1 uniform scaling retained'})
    # Source correspondence is evaluated in ORIGINAL accepted standing, while
    # target corrections operate on the already fitted and morphed geometry.
    out,joins=reconcile_joins(source_standing_meshes,out)
    bind=pose_rigid_meshes(out,world,stage1['bindFrames'])
    residuals={}
    for group,parts in GROUPS.items():
        selected=[m for m in out if m['part'] in parts]
        for section in (('waist','chest') if group=='torso' else ('ankle','calf','knee','midThigh')):
            for axis,suffix in ((0,'Width'),(1,'Depth')):
                key=section+suffix;goal=desired(packet,key);actual=cross_section(selected,plane[section],axis)
                if goal is not None:residuals[group+':'+key]={'requestedMeters':goal,'actualMeters':actual,'deltaMeters':None if actual is None else actual-goal}
    receipt={'shapeMorphApplied':True,'identityPreserved':False,'stageOrder':'uniform per-part scale + rig positioning, then width/depth fields + common-source terminal reconciliation',
             'sourceGeometryHash':geometry_hash(base),'previewGeometryHash':geometry_hash(out),'profiles':profiles,'arms':arm_receipts,
             'joins':joins,'residuals':residuals,'deferred':deferred,'rigRotationsUnchanged':True,'rigPositionsRetainedFromStage1':True,
             'visualAcceptance':False,'motionAcceptance':False,'productionAccepted':False}
    return {**stage1,'standingMeshes':out,'bindMeshes':bind,'receipt':receipt}
