"""Additive minimum seam audit with explicit coincident torso-pivot fallback.

Source triangles crossing a terminal band are exactly clipped in source space;
the same barycentric vertices are transported into candidate geometry. No new
anatomical landmark, joint position, connector or approval is invented.
"""
import numpy as np
from .check_terminal_connectivity_v13 import LINKS,controls,load_archive,pin
from .check_terminal_connectivity_v13a import triangle_minimum_distance

def source_controls(left,right,frames):
    a,b=controls(left,right,frames);fallback=False
    if (left,right)==('chest','pelvis') and np.linalg.norm(b[1]-b[0])<1e-10:
        shared=np.asarray(frames['pelvis_g'])[:3,3];neck=np.asarray(frames['neck_g'])[:3,3]
        if np.linalg.norm(neck-shared)<1e-10:raise ValueError('Coincident torso pivot also lacks native neck axis')
        a=(shared,neck,False);b=(shared,neck,True);fallback=True
    return a,b,fallback

def clipped_terminal_geometry(source,candidate,part,control,fraction=.25):
    start,end,distal=control;axis=np.asarray(end)-start
    if np.linalg.norm(axis)<1e-10:raise ValueError('Degenerate source terminal axis')
    axis/=np.linalg.norm(axis);source_tri=[];candidate_tri=[]
    for sm,cm in zip(source,candidate):
        if sm['part']!=part or not sm.get('render',True):continue
        if (sm['name'],sm['part'])!=(cm['name'],cm['part']) or not np.array_equal(sm['faces'],cm['faces']):raise ValueError('Inventory/topology mismatch')
        p=np.asarray(sm['position'],float);q=np.asarray(cm['position'],float)
        if p.shape!=q.shape:raise ValueError('Vertex inventory mismatch')
        projection=(p-start)@axis;lo,hi=projection.min(),projection.max()
        if hi-lo<1e-10:raise ValueError('Source terminal mesh has zero projected extent')
        cut=hi-fraction*(hi-lo) if distal else lo+fraction*(hi-lo)
        sign=1 if distal else -1
        for face in np.asarray(sm['faces'],int):
            weights=[np.eye(3)[i] for i in range(3)];distance=sign*(projection[face]-cut)
            out=[]
            for i in range(3):
                j=(i+1)%3;inside=distance[i]>=-1e-12;next_inside=distance[j]>=-1e-12
                if inside:out.append(weights[i])
                if inside!=next_inside:
                    t=distance[i]/(distance[i]-distance[j]);out.append((1-t)*weights[i]+t*weights[j])
            for i in range(1,len(out)-1):
                bary=np.array([out[0],out[i],out[i+1]])
                st=bary@p[face];ct=bary@q[face]
                if np.linalg.norm(np.cross(st[1]-st[0],st[2]-st[0]))>1e-16:
                    source_tri.append(st);candidate_tri.append(ct)
    if not source_tri:raise ValueError('Source-clipped terminal triangles unavailable: '+part)
    return np.array(source_tri),np.array(candidate_tri)

def audit_minimum(source,candidate,source_frames,candidate_frames,part_scales=None,epsilon=1e-8):
    if len(source)!=len(candidate):raise ValueError('Inventory count changed')
    scales=part_scales or {};rows=[]
    for left,right in LINKS:
        try:
            a,b,fallback=source_controls(left,right,source_frames)
            sa,ca=clipped_terminal_geometry(source,candidate,left,a)
            sb,cb=clipped_terminal_geometry(source,candidate,right,b)
            sg=triangle_minimum_distance(sa,sb);cg=triangle_minimum_distance(ca,cb)
            scale=min(float(scales.get(left,1)),float(scales.get(right,1)))
            if scale<=0 or not np.isfinite(scale):raise ValueError('Invalid adjacent scale')
            budget=sg*scale
            rows.append({'parts':[left,right],'status':'measured','sourceMinimumClearanceMeters':sg,
                'candidateMinimumClearanceMeters':cg,'sourceDerivedMaximumClearanceMeters':budget,
                'minimumAdjacentUniformScale':scale,'numericEpsilonMeters':epsilon,
                'sourceAuthoredContact':sg<=epsilon,'candidateActualContact':cg<=epsilon,
                'sourceCalibratedClearanceGate':cg<=budget+epsilon,
                'coincidentTorsoPivotFallbackApplied':fallback,
                'sourceTerminalTriangleCounts':[len(sa),len(sb)]})
        except (KeyError,ValueError) as e:rows.append({'parts':[left,right],'status':'unavailable','reason':str(e)})
    return {'kind':'independent-source-clipped-terminal-minimum-v13b','connectors':rows,
        'allRequiredSourceCalibratedTerminalGates':all(r.get('sourceCalibratedClearanceGate',False) for r in rows),
        'allRequiredTerminalContacts':all(r.get('candidateActualContact',False) for r in rows),
        'terminalEligibility':'Exact source-native proximal/distal25% triangle clipping; same barycentric cut transported to candidate.',
        'fallbackPolicy':'Only coincident pelvis/torso controls use their unchanged shared pivot toward native neck; opposing torso bands. No new anatomy target.',
        'P10Policy':'Distribution diagnostic only, no hard gate','assetApprovalCreated':False,'anatomyApproval':False}

def audit_archives_minimum(source_directory,candidate_directory,part_scales=None):
    s,sf,sp=load_archive(source_directory);c,cf,cp=load_archive(candidate_directory)
    result=audit_minimum(s,c,sf,cf,part_scales)
    for row in sp+cp:
        if pin(row['path'])!=row:raise ValueError('Archive changed during audit')
    result['inputPins']=sp+cp;result['inputsUnchanged']=True
    return result
