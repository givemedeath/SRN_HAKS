"""Additive connector refinement: explicit endpoint contours, no flare multiplier."""
import numpy as np
from .morph_coupled_v12a import fit_stage2 as initial_fit,slice_bounds,copy_meshes,geometry_hash,interpolate
from .silhouette_model import measure,cross_section
from .morph_preview_pose_v10 import pose_rigid_meshes

def contour_transition(meshes,parts,low,high,blend=.015):
    """Continuous straight endpoint profile through a broad eligible connector.

    Actual endpoint widths/depths and contour centers are retained. Short smooth
    boundary blends preserve neighboring authored contours; interior flares are
    explicitly replaced instead of multiplying an existing cuff or shelf.
    """
    if high-low<=2*blend:raise ValueError('Broad connector interval required')
    out=copy_meshes(meshes);selected=[m for m in meshes if m['part'] in parts and m.get('render',True)]
    profiles={}
    for axis in (0,1):
        start=slice_bounds(selected,low,axis);end=slice_bounds(selected,high,axis)
        if start is None or end is None:continue
        vertex_z=np.concatenate([m['position'][:,2] for m in selected]);vertex_z=vertex_z[(vertex_z>=low)&(vertex_z<=high)]
        samples=np.unique(np.r_[np.linspace(low,high,180),vertex_z]);bounds=[slice_bounds(selected,z,axis) for z in samples]
        good=np.array([b is not None and b[1]-b[0]>1e-6 for b in bounds])
        if good.sum()<2:continue
        lower=np.interp(samples,samples[good],[bounds[i][0] for i in np.flatnonzero(good)])
        upper=np.interp(samples,samples[good],[bounds[i][1] for i in np.flatnonzero(good)])
        for mesh in out:
            if mesh['part'] not in parts:continue
            p=mesh['position'];used=(p[:,2]>=low)&(p[:,2]<=high);z=p[used,2]
            t=(z-low)/(high-low);want_lo=start[0]+t*(end[0]-start[0]);want_hi=start[1]+t*(end[1]-start[1])
            old_lo=np.interp(z,samples,lower);old_hi=np.interp(z,samples,upper)
            normalized=(p[used,axis]-old_lo)/np.maximum(old_hi-old_lo,1e-6)
            mapped=want_lo+normalized*(want_hi-want_lo)
            distance=np.minimum(z-low,high-z);u=np.clip(distance/blend,0,1);weight=u*u*(3-2*u)
            p[used,axis]+=weight*(mapped-p[used,axis])
        profiles[str(axis)]={'lowContourMeters':list(start),'highContourMeters':list(end),'type':'explicit linear endpoint bounds; smooth boundary blends'}
    return out,{'parts':list(parts),'lowZMeters':float(low),'highZMeters':float(high),'boundaryBlendMeters':blend,'endpointProfiles':profiles,'visibleAcceptance':False}

def fit_stage2(stage1,packet,source_standing_meshes,preserve=False):
    result=initial_fit(stage1,packet,source_standing_meshes,preserve)
    if preserve:return result
    out=result['standingMeshes'];frames=result['standingFrames'];joints={k:v[:3,3].tolist() for k,v in frames.items()}
    measurement=measure(out,joints);ground=measurement['boundsMeters'][0][2];height=measurement['bindStatureMeters']
    waist_fraction=float(packet['views']['front']['waistHeight']['value'])
    waist=ground+height*waist_fraction
    # Waist station is a reviewed visible contour. The broad interval is a
    # deformation policy, not a newly invented hip joint or anatomy target.
    low=max(ground+height*.40,waist-height*.065);high=min(ground+height*.72,waist+height*.065)
    out,taper=contour_transition(out,('chest','pelvis'),low,high,blend=height*.01)
    # Optional additional manually reviewed pelvis WIDTH stations calibrate the
    # outer envelope; depth remains unavailable where arms hide the contour.
    stations=packet.get('pelvisSurfaceStations',[])
    if stations:
        selected=[m for m in out if m['part'] in ('chest','pelvis') and m.get('render',True)]
        knots=[]
        for row in stations:
            goal=row.get('modelFittingWidthMeters');fraction=row['targetHeightFraction'];z=ground+height*fraction
            bounds=slice_bounds(selected,z,0)
            if goal is not None and bounds is not None:knots.append((z,float(goal)/(bounds[1]-bounds[0])))
        for section in ('waist','chest'):
            row=packet['proposedTargets'].get(section+'Width',{});z=ground+height*packet['views']['front'][section+'Height']['value'];bounds=slice_bounds(selected,z,0)
            if row.get('modelFittingMeters') is not None and bounds is not None:knots.append((z,float(row['modelFittingMeters'])/(bounds[1]-bounds[0])))
        if knots:
            for m in out:
                if m['part'] not in ('chest','pelvis'):continue
                p=m['position'];center=float(np.mean([frames['pelvis_g'][0,3],frames['torso_g'][0,3]]))
                p[:,0]=center+(p[:,0]-center)*interpolate(p[:,2],knots)
    result['standingMeshes']=out;result['bindMeshes']=pose_rigid_meshes(out,frames,result['bindFrames'])
    receipt=result['receipt'];receipt['connectorEndpointRefinement']=taper;receipt['pelvisSurfaceStations']=stations
    receipt['previewGeometryHash']=geometry_hash(out)
    # Remeasure every receipt section at the final actual physical planes.
    measurement=measure(out,joints);ground=measurement['boundsMeters'][0][2];height=measurement['bindStatureMeters']
    for key,row in receipt['residuals'].items():
        group,dimension=key.split(':');suffix='Width' if dimension.endswith('Width') else 'Depth';section=dimension[:-len(suffix)]
        parts=('chest','pelvis') if group=='torso' else ('legl','shinl','footl') if group=='leftLeg' else ('legr','shinr','footr')
        z=ground+height*packet['views']['front'][section+'Height']['value'];value=cross_section([m for m in out if m['part'] in parts],z,0 if suffix=='Width' else 1)
        row['actualMeters']=value;row['deltaMeters']=None if value is None else value-row['requestedMeters'];row['finalPlaneZMeters']=z
    receipt['localDeltas']=stage1['localDeltas'];receipt['partScales']=stage1['partScales'];receipt['canonicalRoundtrip']=stage1['receipt']['controllerRoundtripMaximumMatrixError']
    return result
