"""Independent exact terminal minimum clearance; P10 remains a watchpoint.

Source authored nonzero clearances are permitted. Contact is geometric evidence,
not an anatomy, motion, client or production approval.
"""
import numpy as np
from .check_terminal_connectivity_v13 import (LINKS,controls,terminal_geometry,
    point_triangle_distances,load_archive,pin)

def segment_segment_squared(a,b,c,d):
    """Exact closest distance of two finite segments, including parallel ones."""
    u=b-a;v=d-c;w=a-c;aa=u@u;bb=u@v;cc=v@v;dd=u@w;ee=v@w
    candidates=[]
    for s in (0.,1.):
        t=np.clip((ee+s*bb)/cc,0,1) if cc>1e-30 else 0.
        candidates.append(np.sum((w+s*u-t*v)**2))
    for t in (0.,1.):
        s=np.clip((t*bb-dd)/aa,0,1) if aa>1e-30 else 0.
        candidates.append(np.sum((w+s*u-t*v)**2))
    den=aa*cc-bb*bb
    if den>1e-24*max(aa*cc,1e-30):
        s=(bb*ee-cc*dd)/den;t=(aa*ee-bb*dd)/den
        if 0<=s<=1 and 0<=t<=1:candidates.append(np.sum((w+s*u-t*v)**2))
    return float(min(candidates))

def segment_hits_triangle(a,b,tri):
    edge1=tri[1]-tri[0];edge2=tri[2]-tri[0];direction=b-a
    h=np.cross(direction,edge2);det=edge1@h
    if abs(det)<1e-14:return False  # Coplanar contacts are caught by filled faces/edges.
    inverse=1/det;s=a-tri[0];u=inverse*(s@h)
    if u< -1e-10 or u>1+1e-10:return False
    q=np.cross(s,edge1);v=inverse*(direction@q)
    if v< -1e-10 or u+v>1+1e-10:return False
    t=inverse*(edge2@q)
    return bool(-1e-10<=t<=1+1e-10)

def triangle_minimum_distance(left,right):
    """Filled-triangle union clearance: vertex-face, edge-edge and crossings."""
    left=np.asarray(left,float);right=np.asarray(right,float)
    if not len(left) or not len(right):raise ValueError('Empty source-defined terminal triangle set')
    if not np.isfinite(left).all() or not np.isfinite(right).all():raise ValueError('Nonfinite triangles')
    best=min(float(point_triangle_distances(left.reshape(-1,3),right).min()),
             float(point_triangle_distances(right.reshape(-1,3),left).min()))
    if best<1e-10:return 0.
    edges=((0,1),(1,2),(2,0))
    for a in left:
        for b in right:
            # AABB distance lower bound avoids expensive irrelevant pairs.
            separation=np.maximum(np.maximum(a.min(axis=0)-b.max(axis=0),b.min(axis=0)-a.max(axis=0)),0)
            if separation@separation>best*best:continue
            if any(segment_hits_triangle(a[i],a[j],b) or segment_hits_triangle(b[i],b[j],a) for i,j in edges):return 0.
            for i,j in edges:
                for k,l in edges:best=min(best,float(np.sqrt(segment_segment_squared(a[i],a[j],b[k],b[l]))))
            if best<1e-10:return 0.
    return best

def audit_minimum(source,candidate,source_frames,candidate_frames,part_scales=None,epsilon=1e-8):
    scales=part_scales or {};rows=[]
    for left,right in LINKS:
        try:
            ca,cb=controls(left,right,source_frames)
            _,_,sa,fa=terminal_geometry(source,candidate,left,ca)
            _,_,sb,fb=terminal_geometry(source,candidate,right,cb)
            sg=triangle_minimum_distance(sa,sb);fg=triangle_minimum_distance(fa,fb)
            scale=min(float(scales.get(left,1)),float(scales.get(right,1)))
            if scale<=0 or not np.isfinite(scale):raise ValueError('Invalid adjacent scale')
            budget=sg*scale
            rows.append({'parts':[left,right],'status':'measured','sourceMinimumClearanceMeters':sg,
                'candidateMinimumClearanceMeters':fg,'minimumAdjacentUniformScale':scale,
                'sourceDerivedMaximumClearanceMeters':budget,'numericEpsilonMeters':epsilon,
                'sourceAuthoredContact':bool(sg<=epsilon),'candidateActualContact':bool(fg<=epsilon),
                'sourceCalibratedClearanceGate':bool(fg<=budget+epsilon)})
        except (KeyError,ValueError) as e:rows.append({'parts':[left,right],'status':'unavailable','reason':str(e)})
    return {'kind':'independent-source-calibrated-terminal-minimum-v13a','connectors':rows,
        'allRequiredSourceCalibratedTerminalGates':all(r.get('sourceCalibratedClearanceGate',False) for r in rows),
        'allRequiredTerminalContacts':all(r.get('candidateActualContact',False) for r in rows),
        'P10Policy':'distribution watchpoint only; never hard acceptance rejection',
        'assetApprovalCreated':False,'anatomyApproval':False,'motionAcceptance':False,
        'terminalEligibility':'Frozen source-native proximal/distal25%, whole triangles with all vertices eligible.'}

def audit_archives_minimum(source_directory,candidate_directory,part_scales=None):
    s,sf,sp=load_archive(source_directory);c,cf,cp=load_archive(candidate_directory)
    result=audit_minimum(s,c,sf,cf,part_scales)
    for row in sp+cp:
        if pin(row['path'])!=row:raise ValueError('Archive changed during audit')
    result['inputPins']=sp+cp;result['inputsUnchanged']=True
    return result
