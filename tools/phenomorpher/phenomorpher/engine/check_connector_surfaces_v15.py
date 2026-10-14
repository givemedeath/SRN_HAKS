"""Source-owned seam coverage diagnostics; point contact is not connector fit.

Area quadrature samples fixed source triangle interiors. The same barycentric
samples and nearest-source witnesses are transported to the candidate. Distances
are exact to filled triangles, not nearest vertices or silhouette projections.
"""
import numpy as np
from .check_terminal_connectivity_v13 import LINKS
from .check_terminal_connectivity_v13b import source_controls,clipped_terminal_geometry
from .check_terminal_connectivity_v13c import triangle_minimum_distance

BARY=np.array([[2/3,1/6,1/6],[1/6,2/3,1/6],[1/6,1/6,2/3]],float)

def closest_surface(points,triangles):
    p=np.asarray(points,float);t=np.asarray(triangles,float)
    if p.ndim!=2 or p.shape[1]!=3 or t.ndim!=3 or t.shape[1:]!=(3,3) or not len(t):raise ValueError('Nonempty 3D points and triangles required')
    if not np.isfinite(p).all() or not np.isfinite(t).all():raise ValueError('Finite surface geometry required')
    a,b,c=t[:,0],t[:,1],t[:,2];v0=b-a;v1=c-a
    d00=np.sum(v0*v0,axis=1);d01=np.sum(v0*v1,axis=1);d11=np.sum(v1*v1,axis=1);den=d00*d11-d01*d01
    distances=[];indices=[];weights=[]
    for start in range(0,len(p),32):
        q=p[start:start+32,None,:];v2=q-a;d20=np.sum(v2*v0,axis=2);d21=np.sum(v2*v1,axis=2)
        safe=np.where(np.abs(den)>1e-30,den,1.)
        v=(d11*d20-d01*d21)/safe;w=(d00*d21-d01*d20)/safe;u=1-v-w
        bary=np.stack((u,v,w),axis=2);projection=np.einsum('ptv,tvc->ptc',bary,t)
        inside=(u>=0)&(v>=0)&(w>=0)&(np.abs(den)[None,:]>1e-30)
        best=np.where(inside,np.sum((q-projection)**2,axis=2),np.inf);best_bary=bary.copy()
        for i,j in ((0,1),(1,2),(2,0)):
            edge=t[:,j]-t[:,i];length2=np.sum(edge*edge,axis=1);f=np.clip(np.sum((q-t[:,i])*edge,axis=2)/np.maximum(length2,1e-30),0,1)
            x=t[:,i]+f[:,:,None]*edge;d=np.sum((q-x)**2,axis=2);replace=d<best;edge_bary=np.zeros_like(bary);edge_bary[:,:,i]=1-f;edge_bary[:,:,j]=f
            best_bary=np.where(replace[:,:,None],edge_bary,best_bary);best=np.minimum(best,d)
        idx=best.argmin(axis=1);row=np.arange(len(q));distances.extend(np.sqrt(best[row,idx]));indices.extend(idx);weights.extend(best_bary[row,idx])
    return np.asarray(distances),np.asarray(indices,int),np.asarray(weights)

def quadrature(source,candidate):
    area=np.linalg.norm(np.cross(source[:,1]-source[:,0],source[:,2]-source[:,0]),axis=1)/2
    use=area>1e-16
    if not use.any():raise ValueError('No nondegenerate source terminal triangles')
    s=source[use];c=candidate[use]
    return np.einsum('sv,tvc->tsc',BARY,s).reshape(-1,3),np.einsum('sv,tvc->tsc',BARY,c).reshape(-1,3),np.repeat(area[use]/len(BARY),len(BARY))

def weighted_distribution(values,weights):
    order=np.argsort(values);v=np.asarray(values)[order];w=np.asarray(weights)[order];c=np.cumsum(w);c/=c[-1]
    return {'min':float(v[0]),'p10':float(np.interp(.1,c,v)),'median':float(np.interp(.5,c,v)),'p90':float(np.interp(.9,c,v)),'p99':float(np.interp(.99,c,v)),'max':float(v[-1]),'areaWeightedMean':float(np.sum(v*w)/np.sum(w))}

def directional_coverage(source_a,candidate_a,source_b,candidate_b,scale,epsilon=1e-8):
    sp,cp,weights=quadrature(source_a,candidate_a);sd,idx,bary=closest_surface(sp,source_b);cd,_,_=closest_surface(cp,candidate_b)
    sw=np.einsum('pv,pvc->pc',bary,source_b[idx]);cw=np.einsum('pv,pvc->pc',bary,candidate_b[idx]);witness=np.linalg.norm(cp-cw,axis=1)
    budget=sd*scale;worsened=cd>budget+epsilon;source_near=sd<=weighted_distribution(sd,weights)['p10']+epsilon
    total=weights.sum();near_area=weights[source_near].sum()
    vector_residual=(cp-cw)-scale*(sp-sw)
    return {'sourceSurfaceDistanceMeters':weighted_distribution(sd,weights),'candidateSurfaceDistanceMeters':weighted_distribution(cd,weights),
            'sourcePairedCandidateSeamDistanceMeters':weighted_distribution(witness,weights),
            'sourcePairedVectorResidualMeters':weighted_distribution(np.linalg.norm(vector_residual,axis=1),weights),
            'sourceCalibratedCoveredAreaFraction':float(weights[~worsened].sum()/total),
            'sourceCalibratedWorsenedAreaFraction':float(weights[worsened].sum()/total),
            'sourceNearestDecileCoveredAreaFraction':float(weights[source_near&~worsened].sum()/near_area),
            'sourceQuadratureAreaSquareMeters':float(total),'sampleCount':len(sp),'numericEpsilonMeters':epsilon,
            'samplePolicy':'Three interior barycentric samples per exact source-owned terminal triangle, weighted by source triangle area; diagnostic finite quadrature, not continuous coverage certification',
            'pairedWitnessPolicy':'Opposite source triangle index and barycentric closest point fixed before candidate evaluation; geometry correspondence retained',
            'sourceDistanceScaleBasis':scale}

def closed_owner_triangles(meshes,part):
    triangles=[];edges={}
    for m in meshes:
        if m['part']!=part or not m.get('render',True):continue
        tri=np.asarray(m['position'])[np.asarray(m['faces'],int)];triangles.extend(tri)
        for t in tri:
            # Exact geometric duplicates across UV splits share an edge here;
            # this is a read-only closedness test, never topology welding.
            for i,j in ((0,1),(1,2),(2,0)):
                a=tuple(t[i]);b=tuple(t[j]);key=tuple(sorted((a,b)));direction=1 if a<=b else -1
                edges.setdefault(key,[]).append(direction)
    if not triangles or any(len(v)!=2 or sum(v)!=0 for v in edges.values()):return None
    return np.asarray(triangles,float)

def inside_closed(points,triangles):
    result=[]
    for p in points:
        a,b,c=(triangles[:,i]-p for i in range(3));la=np.linalg.norm(a,axis=1);lb=np.linalg.norm(b,axis=1);lc=np.linalg.norm(c,axis=1)
        numerator=np.einsum('ij,ij->i',a,np.cross(b,c));denominator=la*lb*lc+np.sum(a*b,axis=1)*lc+np.sum(b*c,axis=1)*la+np.sum(c*a,axis=1)*lb
        angle=float(np.sum(2*np.arctan2(numerator,denominator)));result.append(abs(angle)>2*np.pi)
    return np.asarray(result,bool)

def penetration(source_points,candidate_points,weights,source_closed,candidate_closed,scale,epsilon=1e-8):
    if source_closed is None or candidate_closed is None:return {'status':'unavailable','reason':'Opposite owning part is not an exactly closed consistently oriented manifold; open terminal bands cannot define solid penetration'}
    sd,_,_=closest_surface(source_points,source_closed);cd,_,_=closest_surface(candidate_points,candidate_closed)
    si=inside_closed(source_points,source_closed)&(sd>epsilon);ci=inside_closed(candidate_points,candidate_closed)&(cd>epsilon)
    source_depth=np.where(si,sd,0.);candidate_depth=np.where(ci,cd,0.);new=candidate_depth>scale*source_depth+epsilon
    return {'status':'measured','sourceInsideAreaFraction':float(weights[si].sum()/weights.sum()),'candidateInsideAreaFraction':float(weights[ci].sum()/weights.sum()),
            'sourceCalibratedWorsenedPenetrationAreaFraction':float(weights[new].sum()/weights.sum()),'sourceDepthMeters':weighted_distribution(source_depth,weights),
            'candidateDepthMeters':weighted_distribution(candidate_depth,weights),'limitations':'Finite source surface samples inside the opposite closed part; solid-angle diagnostic, not collision resolution or anatomy approval'}

def audit(source,candidate,source_frames,candidate_frames,part_scales=None,links=LINKS):
    if len(source)!=len(candidate):raise ValueError('Source/candidate mesh count differs')
    for s,c in zip(source,candidate):
        if (s['part'],s['name'],s.get('render',True))!=(c['part'],c['name'],c.get('render',True)) or np.asarray(s['position']).shape!=np.asarray(c['position']).shape or not np.array_equal(s['faces'],c['faces']):raise ValueError('Source-owned mesh/topology lineage differs')
    rows=[];scales=part_scales or {};closed={}
    for left,right in links:
        try:
            ac,bc,fallback=source_controls(left,right,source_frames)
            sa,ca=clipped_terminal_geometry(source,candidate,left,ac);sb,cb=clipped_terminal_geometry(source,candidate,right,bc)
            scale=min(float(scales.get(left,1.)),float(scales.get(right,1.)))
            if not np.isfinite(scale) or scale<=0:raise ValueError('Positive adjacent part scale required')
            directions=[]
            for name,s,c,other_s,other_c,other_part in ((left,sa,ca,sb,cb,right),(right,sb,cb,sa,ca,left)):
                row=directional_coverage(s,c,other_s,other_c,scale);row['sampleOwner']=name
                sp,cp,w=quadrature(s,c)
                if other_part not in closed:closed[other_part]=(closed_owner_triangles(source,other_part),closed_owner_triangles(candidate,other_part))
                row['penetration']=penetration(sp,cp,w,*closed[other_part],scale)
                directions.append(row)
            rows.append({'parts':[left,right],'status':'measured','sourceMinimumClearanceMeters':triangle_minimum_distance(sa,sb),
                         'candidateMinimumClearanceMeters':triangle_minimum_distance(ca,cb),'directions':directions,'coincidentTorsoPivotFallbackApplied':fallback,
                         'minimumContactAloneCertifiesCoverage':False})
        except (KeyError,ValueError) as error:rows.append({'parts':[left,right],'status':'unavailable','reason':str(error)})
    return {'kind':'source-owned-area-seam-and-penetration-diagnostic-v15','connectors':rows,'allRequestedConnectorsMeasured':all(r['status']=='measured' for r in rows),
            'sourceTerminalAuthority':'Exact source native proximal/distal25% clipped triangles with identical candidate barycentric transport; no candidate re-detection',
            'candidateFramesUsedToRedetectTerminals':False,'coverageAcceptanceThresholdInvented':False,'rasterAllowanceAdded':False,
            'assetApprovalCreated':False,'anatomyAcceptance':False,'motionAcceptance':False,'nativeValidated':False,'clientValidated':False,'productionAccepted':False}
