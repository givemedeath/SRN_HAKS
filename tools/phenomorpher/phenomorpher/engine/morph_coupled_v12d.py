"""Canonical-pose shape fitting with explicit shared-source join reconciliation.

No rig, rotations, authored topology, textures or native resources are written.
Uniform per-part fitting is a separate input stage. Original source shape remains
the correspondence authority; close source terminals receive a common endpoint.
"""
import numpy as np
from .silhouette_model import cross_section,measure
from .fit_morph_preview_v11 import copy_meshes,geometry_hash,orthogonal_arm_width
from .morph_preview_pose_v10 import pose_rigid_meshes
from .warp_segments_v12 import warp_segments,SEGMENTS
from .warp_torso_support_v12 import warp_torso_support,nearest_distances,smoothstep
from .morph_coupled_v12c import contour_transition

LINKS=(('chest','pelvis'),
       ('chest','bicepl'),('chest','bicepr'),('bicepl','forel'),('bicepr','forer'),
       ('forel','handl'),('forer','handr'),('pelvis','legl'),('pelvis','legr'),
       ('legl','shinl'),('legr','shinr'),('shinl','footl'),('shinr','footr'))
GROUPS={'torso':('chest','pelvis'), 'leftLeg':('legl','shinl','footl'),
        'rightLeg':('legr','shinr','footr')}

def interpolate(z,knots):
    rows=sorted({float(z):float(value) for z,value in knots}.items());x=np.array([r[0] for r in rows]);y=np.array([r[1] for r in rows])
    if not len(rows) or not np.isfinite(x).all() or not np.isfinite(y).all() or np.any(y<=0):raise ValueError('Finite positive contour factors required')
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

def terminal_mask(points,start,end,distal,fraction=.25):
    """Native projected terminal extent; no silhouette/anatomy detector."""
    points=np.asarray(points,float);axis=np.asarray(end,float)-np.asarray(start,float)
    length=np.linalg.norm(axis)
    if length<=1e-9:return np.zeros(len(points),bool)
    value=(points-np.asarray(start,float))@(axis/length)
    if not len(value):return np.zeros(0,bool)
    low,high=value.min(),value.max();span=high-low
    if span<=1e-9:return np.zeros(len(points),bool)
    return value>=high-fraction*span if distal else value<=low+fraction*span


def link_terminal_controls(left,right,source_frames):
    """Use authored native branch endpoints, including torso branch controls."""
    frame=lambda name:np.asarray(source_frames[name])[:3,3]
    if left in SEGMENTS:
        a,b=SEGMENTS[left];start,end=frame(a),frame(b)
        rstart,rend=(frame(SEGMENTS[right][0]),frame(SEGMENTS[right][1])) if right in SEGMENTS else (start,end)
        return (start,end,True),(rstart,rend,False)
    if left=='chest' and right=='pelvis':
        return (frame('torso_g'),frame('neck_g'),False),(frame('pelvis_g'),frame('torso_g'),True)
    if left=='chest' and right in ('bicepl','bicepr'):
        start,end=SEGMENTS[right]
        return (frame('torso_g'),frame(start),True),(frame(start),frame(end),False)
    if left=='pelvis' and right in ('legl','legr'):
        start,end=SEGMENTS[right]
        return (frame('pelvis_g'),frame(start),True),(frame(start),frame(end),False)
    raise ValueError('Unsupported native terminal link')


def reconcile_joins(source,fitted,source_frames=None,links=LINKS,max_source_gap=.012,influence=.10):
    """Common source-correspondence endpoints plus broad smooth displacement.

    Only pairs already close in the donor are joined. No new hidden connectors
    are fabricated. Correspondence distances and remaining endpoint gaps are
    reported; finite correspondence is not visual or motion acceptance.
    """
    result=copy_meshes(fitted);report=[];constraints={}
    for left,right in links:
        if source_frames is None:
            report.append({'parts':[left,right],'status':'native terminal frames unavailable; no sewing','pairs':0});continue
        try:left_control,right_control=link_terminal_controls(left,right,source_frames)
        except KeyError:
            report.append({'parts':[left,right],'status':'native terminal frames unavailable; no sewing','pairs':0});continue
        ai=[i for i,m in enumerate(source) if m['part']==left and m.get('render',True)]
        bi=[i for i,m in enumerate(source) if m['part']==right and m.get('render',True)]
        pairs=[]
        for a in ai:
            pa=np.asarray(source[a]['position'])
            eligible_a=np.flatnonzero(terminal_mask(pa,*left_control))
            for b in bi:
                pb=np.asarray(source[b]['position'])
                eligible_b=np.flatnonzero(terminal_mask(pb,*right_control))
                if not len(eligible_a) or not len(eligible_b):continue
                for start in range(0,len(eligible_a),128):
                    chosen=eligible_a[start:start+128]
                    distance=np.sum((pa[chosen,None,:]-pb[None,eligible_b,:])**2,axis=2)
                    near=np.argmin(distance,axis=1);good=np.flatnonzero(distance[np.arange(len(near)),near]<=max_source_gap**2)
                    pairs.extend((a,int(chosen[i]),b,int(eligible_b[near[i]])) for i in good)
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
                   'eligibility':'native projected proximal/distal 25% source terminal regions only',
                   'visualAcceptance':False,'motionAcceptance':False}

def fit_stage2(stage1,packet,source_standing_meshes,preserve=False):
    base=stage1['standingMeshes'];world=stage1['standingFrames'];out=copy_meshes(base)
    if preserve:return {**stage1,'receipt':{'identityPreserved':True,'sourceGeometryHash':geometry_hash(base),'previewGeometryHash':geometry_hash(out),'shapeMorphApplied':False}}
    source_frames=stage1['sourceStandingFrames'];uniform=stage1['uniformScale']
    base,segments=warp_segments(source_standing_meshes,base,source_frames,world,stage1['partScales'],uniform)
    base,shoulder_support=warp_torso_support(source_standing_meshes,base,source_frames,world,stage1['partScales'],uniform)
    out=copy_meshes(base)
    neck_points=[np.asarray(m['position']) for m in source_standing_meshes if m['part']=='neck' and len(m['position'])]
    neck_cloud=np.concatenate(neck_points) if neck_points else np.asarray([source_frames['neck_g'][:3,3]])
    protection={i:smoothstep((nearest_distances(np.asarray(m['position']),neck_cloud)-.02)/.12)
                for i,m in enumerate(source_standing_meshes) if m['part']=='chest'}
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
            if group=='torso':
                upper=min(float(world[k][2,3]) for k in ('neck_g','lbicep_g','rbicep_g'))
                conflicted=[(z,f) for z,f in knots if z>=upper-.01]
                if conflicted:deferred.append({'group':group,'axis':axis,'reason':'measurement plane conflicts with protected native upper terminal','knots':conflicted})
                knots=[(z,f) for z,f in knots if z<upper-.01]
                knots.extend(((upper,1.),(max(hi,upper+1e-5),1.)))
            # Endpoint factors continue the nearest supported section through
            # source overlap. Forcing1 at an arbitrary mesh cap creates a shelf.
            profiles[group]['axes'][str(axis)]=knots
            samples=np.linspace(lo+1e-6,hi-1e-6,120);centers=[]
            for z in samples:
                bounds=slice_bounds(selected,z,axis)
                centers.append(np.mean(bounds) if bounds else np.nan)
            good=np.isfinite(centers);centers=np.interp(samples,samples[good],np.asarray(centers)[good])
            for mesh_index,m in enumerate(out):
                if m['part'] not in parts:continue
                p=m['position'];c=np.interp(p[:,2],samples,centers)
                factors=interpolate(p[:,2],knots)
                if group=='torso' and mesh_index in protection:factors=1.+(factors-1.)*protection[mesh_index]
                p[:,axis]=c+(p[:,axis]-c)*factors
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
    out,joins=reconcile_joins(source_standing_meshes,out,source_frames)
    # Explicit broad waist endpoint profile removes an existing intermediate
    # flare instead of multiplying it into a cuff or secondary shoulder.
    waist=plane['waist'];low=max(floor+height*.40,waist-height*.065);high=min(floor+height*.72,waist+height*.065)
    out,taper=contour_transition(out,('chest','pelvis'),low,high,blend=height*.01)
    stations=packet.get('pelvisSurfaceStations',[]);station_fit=[]
    if stations:
        selected=[m for m in out if m['part'] in ('chest','pelvis') and m.get('render',True)]
        knots=[]
        for row in stations:
            goal=row.get('modelFittingWidthMeters');z=floor+height*row['targetHeightFraction'];bounds=slice_bounds(selected,z,0)
            if goal is not None and bounds is not None and bounds[1]-bounds[0]>1e-5:
                factor=float(goal)/(bounds[1]-bounds[0])
                if .35<=factor<=2.5:knots.append((z,factor));station_fit.append({'zMeters':z,'factor':factor})
                else:deferred.append({'key':'pelvisSurfaceStation','ratio':factor,'reason':'recommendation exceeds pilot deformation bound'})
        for section in ('waist','chest'):
            z=plane[section];goal=desired(packet,section+'Width');bounds=slice_bounds(selected,z,0)
            if goal is not None and bounds is not None and bounds[1]-bounds[0]>1e-5:knots.append((z,goal/(bounds[1]-bounds[0])))
        if knots:
            upper=min(float(world[k][2,3]) for k in ('neck_g','lbicep_g','rbicep_g'))
            knots=[(z,f) for z,f in knots if z<upper-.01];knots.append((upper,1.))
            torso_high=max(float(m['position'][:,2].max()) for m in selected);knots.append((max(torso_high,upper+1e-5),1.))
            center=float(np.mean([world['pelvis_g'][0,3],world['torso_g'][0,3]]))
            for mesh_index,m in enumerate(out):
                if m['part'] not in ('chest','pelvis'):continue
                factors=interpolate(m['position'][:,2],knots)
                if mesh_index in protection:factors=1.+(factors-1.)*protection[mesh_index]
                m['position'][:,0]=center+(m['position'][:,0]-center)*factors
    # Restrict every downstream correction near the authored neck connector,
    # not only the radial pass. This remains a broad smooth source-space gate.
    for mesh_index,gate in protection.items():
        out[mesh_index]['position']=np.asarray(base[mesh_index]['position'])+gate[:,None]*(np.asarray(out[mesh_index]['position'])-np.asarray(base[mesh_index]['position']))
        protected=gate==0.;out[mesh_index]['position'][protected]=np.asarray(base[mesh_index]['position'])[protected]
    bind=pose_rigid_meshes(out,world,stage1['bindFrames'])
    final_measure=measure(out,{k:v[:3,3].tolist() for k,v in world.items()})
    final_floor=final_measure['boundsMeters'][0][2];final_height=final_measure['bindStatureMeters']
    final_plane={s:final_floor+float(packet['views']['front'][s+'Height']['value'])*final_height for s in plane}
    residuals={}
    for group,parts in GROUPS.items():
        selected=[m for m in out if m['part'] in parts]
        for section in (('waist','chest') if group=='torso' else ('ankle','calf','knee','midThigh')):
            for axis,suffix in ((0,'Width'),(1,'Depth')):
                key=section+suffix;goal=desired(packet,key);actual=cross_section(selected,final_plane[section],axis)
                if goal is not None:residuals[group+':'+key]={'requestedMeters':goal,'actualMeters':actual,'deltaMeters':None if actual is None else actual-goal,'finalPlaneZMeters':final_plane[section]}
    for side in ('l','r'):
        for part,key,a,b in (('bicep'+side,'upperArmWidth',side+'bicep_g',side+'forearm_g'),('fore'+side,'forearmWidth',side+'forearm_g',side+'hand_g')):
            goal=desired(packet,key);actual=orthogonal_arm_width([m for m in out if m['part']==part],world[a][:3,3],world[b][:3,3])
            if goal is not None:residuals[part+':'+key]={'requestedMeters':goal,'actualMeters':actual,'deltaMeters':None if actual is None else actual-goal}
        feet=[m['position'] for m in out if m['part']=='foot'+side and m.get('render',True)]
        for axis,key in ((0,'footWidth'),(1,'footLength')):
            goal=desired(packet,key);actual=float(np.ptp(np.concatenate(feet)[:,axis])) if feet else None
            if goal is not None:residuals['foot'+side+':'+key]={'requestedMeters':goal,'actualMeters':actual,'deltaMeters':None if actual is None else actual-goal}
    for index,row in enumerate(stations):
        goal=row.get('modelFittingWidthMeters');z=final_floor+final_height*row['targetHeightFraction']
        actual=cross_section([m for m in out if m['part'] in ('chest','pelvis')],z,0)
        if goal is not None:residuals['pelvisStation:'+str(index)]={'requestedMeters':goal,'actualMeters':actual,'deltaMeters':None if actual is None else actual-goal,'finalPlaneZMeters':z}
    residuals['stature']={'requestedMeters':float(packet['targetStatureMeters']),'actualMeters':final_height,'deltaMeters':final_height-float(packet['targetStatureMeters'])}
    receipt={'shapeMorphApplied':True,'identityPreserved':False,'stageOrder':'uniform scale/position; differential limb geometry; native chest support; radial contours; source-terminal reconciliation; broad waist taper; bounded pelvis stations',
             'sourceGeometryHash':geometry_hash(stage1['standingMeshes']),'previewGeometryHash':geometry_hash(out),'profiles':profiles,'arms':arm_receipts,
             'segmentGeometry':segments,'shoulderSupport':shoulder_support,'connectorEndpointRefinement':taper,
             'pelvisSurfaceStations':stations,'pelvisStationFits':station_fit,
             'joins':joins,'residuals':residuals,'deferred':deferred,'rigRotationsUnchanged':True,'rigPositionsRetainedFromStage1':True,
             'visualAcceptance':False,'motionAcceptance':False,'productionAccepted':False}
    receipt['headNeckPreservedFromStage1']=all(np.array_equal(m['position'],stage1['standingMeshes'][i]['position']) for i,m in enumerate(out) if m['part'] in ('head','neck'))
    receipt['localDeltas']=stage1['localDeltas'];receipt['partScales']=stage1['partScales'];receipt['canonicalRoundtrip']=stage1['receipt']['controllerRoundtripMaximumMatrixError']
    return {**stage1,'standingMeshes':out,'bindMeshes':bind,'receipt':receipt}
