"""Exact minimum-clearance acceleration; no threshold or contact weakening.

Contacts are checked before distance work, using overlapping triangle AABBs.
Noncontact distance uses exact face/edge pairs ordered by AABB lower bounds.
All discarded pairs have a rigorous bound above the best exact distance.
"""
import numpy as np
from . import check_terminal_connectivity_v13b as base
from .check_terminal_connectivity_v13 import point_triangle_distances
from .check_terminal_connectivity_v13a import segment_hits_triangle,segment_segment_squared

EDGES=((0,1),(1,2),(2,0))

def pair_distance(a,b):
    if any(segment_hits_triangle(a[i],a[j],b) or segment_hits_triangle(b[i],b[j],a) for i,j in EDGES):return 0.
    best=min(float(point_triangle_distances(a,b[None]).min()),float(point_triangle_distances(b,a[None]).min()))
    if best<1e-10:return 0.
    for i,j in EDGES:
        for k,l in EDGES:best=min(best,float(np.sqrt(segment_segment_squared(a[i],a[j],b[k],b[l]))))
    return 0. if best<1e-10 else best

def triangle_minimum_distance(left,right):
    left=np.asarray(left,float);right=np.asarray(right,float)
    if not len(left) or not len(right):raise ValueError('Empty source-defined terminal triangle set')
    if not np.isfinite(left).all() or not np.isfinite(right).all():raise ValueError('Nonfinite triangles')
    alo,ahi=left.min(axis=1),left.max(axis=1);blo,bhi=right.min(axis=1),right.max(axis=1)
    # Rigorous contact candidates first. Shared vertices and coplanar containment
    # are tested by filled-face distances; transverse intersections by segments.
    for i,a in enumerate(left):
        overlap=np.all((blo<=ahi[i]+1e-12)&(bhi>=alo[i]-1e-12),axis=1)
        for j in np.flatnonzero(overlap):
            if pair_distance(a,right[j])==0.:return 0.
    # Seed a real distance from the closest AABB pair, not an all-vertices tensor.
    best=np.inf;row_order=[]
    for i in range(len(left)):
        sep=np.maximum(np.maximum(alo[i]-bhi,blo-ahi[i]),0)
        bounds=np.sum(sep*sep,axis=1);j=int(np.argmin(bounds))
        row_order.append((float(bounds[j]),i,j))
    row_order.sort()
    best=pair_distance(left[row_order[0][1]],right[row_order[0][2]])
    for row_bound,i,_ in row_order:
        if row_bound>best*best:break
        sep=np.maximum(np.maximum(alo[i]-bhi,blo-ahi[i]),0);bounds=np.sum(sep*sep,axis=1)
        js=np.flatnonzero(bounds<=best*best);js=js[np.argsort(bounds[js])]
        for j in js:
            if bounds[j]>best*best:break
            best=min(best,pair_distance(left[i],right[j]))
            if best==0.:return 0.
    return best

def audit_minimum(source,candidate,source_frames,candidate_frames,part_scales=None,epsilon=1e-8):
    if len(source)!=len(candidate):raise ValueError('Inventory count changed')
    scales=part_scales or {};rows=[]
    for left,right in base.LINKS:
        try:
            a,b,fallback=base.source_controls(left,right,source_frames)
            sa,ca=base.clipped_terminal_geometry(source,candidate,left,a)
            sb,cb=base.clipped_terminal_geometry(source,candidate,right,b)
            sg=triangle_minimum_distance(sa,sb);cg=triangle_minimum_distance(ca,cb)
            scale=min(float(scales.get(left,1)),float(scales.get(right,1)))
            if scale<=0 or not np.isfinite(scale):raise ValueError('Invalid adjacent scale')
            budget=sg*scale
            rows.append({'parts':[left,right],'status':'measured','sourceMinimumClearanceMeters':sg,
                'candidateMinimumClearanceMeters':cg,'sourceDerivedMaximumClearanceMeters':budget,
                'minimumAdjacentUniformScale':scale,'numericEpsilonMeters':epsilon,
                'sourceAuthoredContact':sg<=epsilon,'candidateActualContact':cg<=epsilon,
                'sourceCalibratedClearanceGate':cg<=budget+epsilon,
                'coincidentTorsoPivotFallbackApplied':fallback,'sourceTerminalTriangleCounts':[len(sa),len(sb)]})
        except (KeyError,ValueError) as e:rows.append({'parts':[left,right],'status':'unavailable','reason':str(e)})
    return {'kind':'independent-source-clipped-terminal-minimum-v13c','connectors':rows,
        'allRequiredSourceCalibratedTerminalGates':all(r.get('sourceCalibratedClearanceGate',False) for r in rows),
        'allRequiredTerminalContacts':all(r.get('candidateActualContact',False) for r in rows),
        'terminalEligibility':'Exact source-native proximal/distal25% triangle clipping; same barycentric cut transported to candidate.',
        'fallbackPolicy':'Only coincident pelvis/torso controls use their unchanged shared pivot toward native neck; opposing torso bands. No new anatomy target.',
        'P10Policy':'Distribution diagnostic only, no hard gate','assetApprovalCreated':False,'anatomyApproval':False}

def audit_archives_minimum(source_directory,candidate_directory,part_scales=None):
    s,sf,sp=base.load_archive(source_directory);c,cf,cp=base.load_archive(candidate_directory)
    result=audit_minimum(s,c,sf,cf,part_scales)
    for row in sp+cp:
        if base.pin(row['path'])!=row:raise ValueError('Archive changed during audit')
    result['kind']='independent-source-clipped-terminal-minimum-v13c'
    result['inputPins']=sp+cp;result['inputsUnchanged']=True
    return result
