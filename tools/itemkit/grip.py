"""Measured native grip calibration and UV-preserving corner transforms."""
import numpy as np
from tools.headkit.common import require,digest
from .geometry import transform


class GripDeparture(ValueError):
    def __init__(self, report):
        super().__init__('Grip width/depth departs from standard; review the retained measurement instead of distorting the pistol')
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
    require(not depth_departs or (review or {}).get('depthDepartureApproved') is True,
            'Two-hand grip must match approved midpoint thickness')
    report={'reference':standard['id'],'standardDigest':digest(standard),'fitMatrix':m.tolist(),
            'sizingAuthority':'midpoint-depth-two-hand','usableLength':float(length),'nativeGripOrigin':origin.tolist(),
            'measuredFittedSections':sections,'midpointRelativeDifferences':{
                'depth':mid['depth']/target['depth']-1,'visibleFaceWidth':mid['visibleFaceWidth']/target['visibleFaceWidth']-1,
                'usableLength':float(length)/standard['usableLength']-1},
            'proportionsAndAnglesPreserved':True,'bothBodyVisualReviewRequired':True}
    report['measurementDigest']=digest(report)
    # Length is the intended departure; width over 5% needs the same bound review as firearms.
    if depth_departs or abs(report['midpointRelativeDifferences']['visibleFaceWidth'])>.05:bind_departure(report,review)
    return m,report
