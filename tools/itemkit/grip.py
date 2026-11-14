"""Measured native grip calibration and UV-preserving corner transforms."""
import numpy as np
from tools.headkit.common import require,digest
from .geometry import transform


class GripDeparture(ValueError):
    def __init__(self, report, message=None):
        super().__init__(message or 'Grip width/depth departs from standard; review the retained measurement instead of distorting the pistol')
        self.report = report


def bind_departure(report, review):
    """Require an approved review of this exact measurement, or retain it for one."""
    review=review or {}
    if not (review.get('decision')=='approved' and review.get('measurementDigest')==report['measurementDigest']
            and isinstance(review.get('notes'),str) and review['notes'].strip()):
        raise GripDeparture(report)
    report['departureReview']=review


def section_dimensions(vertices, faces, y):
    tri = np.asarray(vertices, float)[faces]; hits = []
    for a,b in ((0,1),(1,2),(2,0)):
        v,w = tri[:,a],tri[:,b]
        crossing = (v[:,1]-y)*(w[:,1]-y) < 0
        v,w = v[crossing],w[crossing]
        if len(v): hits.extend(v+(w-v)*((y-v[:,1])/(w[:,1]-v[:,1]))[:,None])
    require(len(hits)>=3, 'Usable grip section has no surface')
    return np.ptp(np.asarray(hits),axis=0)[[0,2]]


def reference_sections(vertices, faces, standard, centre, length):
    rows=[]
    for row in standard['referenceSections']:
        fraction=row['fractionFromPommel']
        depth,width=section_dimensions(vertices,faces,centre+(fraction-.5)*length)
        rows.append({'fractionFromPommel':fraction,'depth':float(depth),'visibleFaceWidth':float(width)})
    return rows


def calibration(vertices, faces, matrix, origin, standard):
    require(standard.get('id')=='cougar-approved-grip-v1' and standard['approval']['gripSizingApproved'],
            'Reviewed grip reference required')
    origin=np.asarray(origin,float);matrix=np.asarray(matrix,float)
    fitted=np.c_[vertices,np.ones(len(vertices))]@matrix.T
    measured=section_dimensions(fitted[:,:3],faces,origin[1])
    target=standard['targetMidpointSection']
    scales=np.array([target['depth']/measured[0],1.,target['visibleFaceWidth']/measured[1]])
    require(np.isfinite(scales).all() and np.all(scales>0), 'Positive grip calibration required')
    correction=np.eye(4);correction[:3,:3]=np.diag(scales);correction[:3,3]=origin-origin*scales
    result=correction@matrix
    final=(np.c_[vertices,np.ones(len(vertices))]@result.T)[:,:3]
    sections=reference_sections(final,faces,standard,origin[1],standard['usableLength']) if 'usableLength' in standard else []
    return result,{'reference':standard['id'],'transverseScale':scales.tolist(),
                   'sourceSection':measured.tolist(),'measuredFittedSections':sections}


def affine_corners(positions,normals,uv,matrix):
    """Transform exact authored corners; UVs are retained without resampling."""
    p=np.asarray(positions,float);n=np.asarray(normals,float);m=np.asarray(matrix,float)
    require(m.shape==(4,4) and np.isfinite(m).all() and np.allclose(m[3],[0,0,0,1])
            and np.linalg.det(m[:3,:3])>0,'Positive finite affine transform required')
    transformed=transform(p,m)
    normals=n@np.linalg.inv(m[:3,:3]);normals/=np.linalg.norm(normals,axis=-1)[...,None]
    return transformed,normals,np.asarray(uv).copy()


def two_hand_uniform(vertices,faces,matrix,endpoints,origin,standard,review=None):
    """Measure a length departure while retaining the two-hand reference proportions.

    The approved Cougar depth remains the sizing authority. Neither the original
    one-hand length nor its transverse correction is applied to a two-hand hilt.
    The resulting departure still needs the downstream both-body visual review.
    """
    require(standard.get('id')=='cougar-approved-grip-v1'
            and standard.get('approval',{}).get('gripSizingApproved') is True,'Approved melee grip reference required')
    m=np.asarray(matrix,float);ends=np.asarray(endpoints,float);origin=np.asarray(origin,float)
    require(m.shape==(4,4) and np.isfinite(m).all() and np.allclose(m[3],[0,0,0,1]),'Finite grip transform required')
    gram=m[:3,:3].T@m[:3,:3]
    require(np.linalg.det(m[:3,:3])>0 and np.allclose(gram,np.eye(3)*gram[0,0],atol=1e-12,rtol=1e-7),
            'Two-hand fitting must preserve proportions uniformly')
    require(ends.shape==(2,3) and origin.shape==(3,) and np.isfinite(ends).all() and np.isfinite(origin).all(),'Measured usable landmarks required')
    final=transform(vertices,m);e=transform(ends,m);length=np.linalg.norm(e[1]-e[0])
    require(length>0 and np.linalg.norm(e.mean(0)-origin)<.002
            and np.allclose((e[1]-e[0])/length,[0,1,0],atol=1e-6),'Two-hand grip must follow native+Y at its measured origin')
    sections=reference_sections(final,faces,standard,origin[1],length)
    mid=next(r for r in sections if r['fractionFromPommel']==.5);target=standard['targetMidpointSection']
    # The approved depth is the default authority. A design whose round, thick grip would make a two-hander shorter
    # than a one-hander (wave-1 Claymore: 0.98 m by depth) may depart only through an explicit, digest-bound review.
    depth_departs=abs(mid['depth']/target['depth']-1)>=.01
    report={'reference':standard['id'],'standardDigest':digest(standard),'fitMatrix':m.tolist(),
            'sizingAuthority':'midpoint-depth-two-hand','usableLength':float(length),'nativeGripOrigin':origin.tolist(),
            'measuredFittedSections':sections,'midpointRelativeDifferences':{
                'depth':mid['depth']/target['depth']-1,'visibleFaceWidth':mid['visibleFaceWidth']/target['visibleFaceWidth']-1,
                'usableLength':float(length)/standard['usableLength']-1},
            'proportionsAndAnglesPreserved':True,'bothBodyVisualReviewRequired':True}
    report['measurementDigest']=digest(report)
    # An unapproved depth departure is refused like any other, but with its measurement retained: the measure-only
    # pass needs this digest before anyone can approve the departure.
    if depth_departs and (review or {}).get('depthDepartureApproved') is not True:
        report['depthDepartureApproved']=False
        raise GripDeparture(report,'Two-hand grip must match approved midpoint thickness unless a review of this measurement approves the depth departure')
    # Length is the intended departure; width over 5% needs the same bound review as firearms.
    if depth_departs or abs(report['midpointRelativeDifferences']['visibleFaceWidth'])>.05:bind_departure(report,review)
    return m,report


def transverse_uniform(vertices,faces,matrix,origin,standard,review=None,basis='depth'):
    """Thin a long shaft to one approved grip dimension with one scale on both transverse axes.

    The per-axis hilt calibration sets depth and face width separately, which flattens a shaft that is not shaped like
    the reference hilt: the 1.90 m stun staff (a 1.2:1 shaft) came out 1.7:1, scaled 0.40 on one axis and 0.56 on the
    other. Here the length stays as fitted, the midpoint `basis` dimension ('depth', or 'visibleFaceWidth' for a
    thicker shaft) meets the standard and the section keeps its own proportions, so the other dimension departs by
    construction and needs a review bound to this exact measurement.
    """
    require(basis in ('depth','visibleFaceWidth'),'Section basis must be depth or visibleFaceWidth')
    require(standard.get('id')=='cougar-approved-grip-v1'
            and standard.get('approval',{}).get('gripSizingApproved') is True,'Approved melee grip reference required')
    m=np.asarray(matrix,float);origin=np.asarray(origin,float)
    require(m.shape==(4,4) and np.isfinite(m).all() and np.allclose(m[3],[0,0,0,1]) and origin.shape==(3,),'Finite grip transform required')
    gram=m[:3,:3].T@m[:3,:3]
    require(np.linalg.det(m[:3,:3])>0 and np.allclose(gram,np.eye(3)*gram[0,0],atol=1e-12,rtol=1e-7),
            'A transverse-uniform grip starts from a uniform fit')
    measured=section_dimensions(transform(vertices,m),faces,origin[1]);target=standard['targetMidpointSection']
    k=float(target[basis]/measured[0 if basis=='depth' else 1]);require(np.isfinite(k) and k>0,'Positive grip calibration required')
    correction=np.eye(4);correction[:3,:3]=np.diag([k,1.,k]);correction[:3,3]=origin-origin*[k,1.,k];result=correction@m
    sections=reference_sections(transform(vertices,result),faces,standard,origin[1],standard['usableLength'])
    mid=next(r for r in sections if r['fractionFromPommel']==.5)
    report={'reference':standard['id'],'standardDigest':digest(standard),'fitMatrix':result.tolist(),
            'sizingAuthority':'midpoint-depth-uniform','sectionBasis':basis,'usableLength':float(standard['usableLength']),'nativeGripOrigin':origin.tolist(),
            'sourceSection':measured.tolist(),'transverseScale':[k,1.,k],'measuredFittedSections':sections,'midpointRelativeDifferences':{
                'depth':mid['depth']/target['depth']-1,'visibleFaceWidth':mid['visibleFaceWidth']/target['visibleFaceWidth']-1},
            'sectionProportionsPreserved':True,'bothBodyVisualReviewRequired':True}
    report['measurementDigest']=digest(report);bind_departure(report,review)
    return result,report


def one_hand_round(vertices,faces,matrix,origin,standard,review=None,ends=None):
    """Keep a round one-hand grip round instead of squashing it to the reference section.

    The usable length stays the sizing authority. Both transverse axes get the same scale, chosen so the grip's
    midpoint diameter equals the approved visible-face width; a club's circular handle and square end caps
    survive (the wave-1 Club became a 4 x 6.5 cm oval with a slanted pommel under the per-axis correction, and a
    7.3 cm log with no correction at all). The depth therefore departs from the standard by construction: it
    always needs a review bound to this exact measurement, and the both-body visual hand-fit review afterwards.
    """
    require(standard.get('id')=='cougar-approved-grip-v1'
            and standard.get('approval',{}).get('gripSizingApproved') is True,'Approved melee grip reference required')
    m=np.asarray(matrix,float);origin=np.asarray(origin,float)
    require(m.shape==(4,4) and np.isfinite(m).all() and np.allclose(m[3],[0,0,0,1]) and origin.shape==(3,),'Finite grip transform required')
    gram=m[:3,:3].T@m[:3,:3]
    require(np.linalg.det(m[:3,:3])>0 and np.allclose(gram,np.eye(3)*gram[0,0],atol=1e-12,rtol=1e-7),
            'A round one-hand grip starts from a uniform fit')
    measured=section_dimensions(transform(vertices,m),faces,origin[1]);target=standard['targetMidpointSection']
    require(abs(measured[0]/measured[1]-1)<.1,'Grip section is not round; use the standard transverse calibration')
    k=float(target['visibleFaceWidth']/measured.mean());require(np.isfinite(k) and k>0,'Positive grip calibration required')
    correction=np.eye(4);correction[:3,:3]=np.diag([k,1.,k]);correction[:3,3]=origin-origin*[k,1.,k];result=correction@m
    # A chosen overall length (`ends`: the reviewed handle's endpoints) samples the handle itself, not the hand's length,
    # which would run past a short handle into the guard or off the pommel (the wave-4 Sai, 2026-11-13).
    usable=float(standard['usableLength']) if ends is None else float(np.linalg.norm(np.subtract(*transform(np.asarray(ends,float),m)[::-1])))
    sections=reference_sections(transform(vertices,result),faces,standard,origin[1],usable)
    mid=next(r for r in sections if r['fractionFromPommel']==.5)
    differences={'depth':mid['depth']/target['depth']-1,'visibleFaceWidth':mid['visibleFaceWidth']/target['visibleFaceWidth']-1}
    if ends is not None:differences['usableLength']=usable/standard['usableLength']-1
    report={'reference':standard['id'],'standardDigest':digest(standard),'fitMatrix':result.tolist(),
            'sizingAuthority':'usable-length-round','usableLength':usable,'nativeGripOrigin':origin.tolist(),
            'sourceSection':measured.tolist(),'transverseScale':[k,1.,k],'measuredFittedSections':sections,'midpointRelativeDifferences':differences,
            'roundSectionPreserved':True,'bothBodyVisualReviewRequired':True,**({'chosenLength':True} if ends is not None else {})}
    report['measurementDigest']=digest(report);bind_departure(report,review)
    return result,report


def fitted_grip_length(fit, native, report):
    """The length the fitted grip endpoints must match in the fit stage: the native hand, or for a chosen-length round
    fit the reviewed handle itself, as its bound grip report measured it."""
    if not fit.get('chosenLength'): return float(native['gripLength'])
    require(isinstance(report, dict) and report.get('chosenLength') is True and report.get('sizingAuthority') == 'usable-length-round',
            'A chosen-length fit needs its round grip report')
    return float(report['usableLength'])


def melee_fit(family, fit, standard, vertices, faces, matrix):
    """The melee grip correction of the fit stage, by the fit's sizing authority: (final matrix, grip report).

    Shared by blender_worker.grip_fit and opening_probes.fitted_shell, so the probes measure the shell exactly where
    the fit stage places it and refuse what it refuses. Whole-native firearms are placed by firearm_grip instead."""
    from .routes import ROUTES, WHOLE_NATIVE_FAMILIES
    route = ROUTES[family['family']]; native = family['native']; authority = fit.get('sizingAuthority'); review = fit.get('gripDeparture')
    require(family['family'] not in WHOLE_NATIVE_FAMILIES, 'A whole-native firearm is placed by firearm_grip.measured_fit, not the melee grip')
    if authority == 'midpoint-depth-two-hand':
        require(route.hold == 'two' and route.carrier is not None and native['baseItem'] == route.carrier.base_item,
                'Explicit two-handed carrier required for the length departure')
        return two_hand_uniform(vertices, faces, matrix, fit['gripEndpoints'], native['gripOrigin'], standard, review)
    require(abs(native['gripLength'] - standard['usableLength']) < 1e-9, 'Native target length differs from the approved grip standard')
    if authority == 'usable-length-round':
        ends = fit['gripEndpoints'] if fit.get('chosenLength') else None
        return one_hand_round(vertices, faces, matrix, native['gripOrigin'], standard, review, ends)
    if authority == 'midpoint-depth-uniform':
        require(route.section == 'uniform', 'midpoint-depth-uniform needs a section="uniform" route')
        return transverse_uniform(vertices, faces, matrix, native['gripOrigin'], standard, review, fit.get('sectionBasis', 'depth'))
    # A staff manifest from before section="uniform" would rebuild the flattened staff (user, 2026-11-12).
    # Any other authority (none, or the older usable-length-uniform) takes the per-axis hilt calibration.
    require(route.section != 'uniform', 'A section="uniform" route is never sized by the per-axis hilt calibration; refit it')
    return calibration(vertices, faces, matrix, native['gripOrigin'], standard)
