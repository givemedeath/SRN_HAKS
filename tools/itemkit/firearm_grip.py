"""Measure a pistol's grip along its own axis without deforming its proportions."""
import numpy as np
from tools.headkit.common import digest, require
from .geometry import similarity_matrix, transform
from .grip import section_dimensions


class GripDeparture(ValueError):
    def __init__(self, report):
        super().__init__('Grip width/depth departs from standard; review the retained measurement instead of distorting the pistol')
        self.report = report


# The Colt reference supersedes Cougar for firearms. Pre-Colt fits (the Colt L36
# itself) replay only by declaring that historical authority explicitly.
FIREARM_GRIP_STANDARD = 'colt-l36-approved-firearm-grip-v1'
HISTORICAL_FIREARM_GRIP_STANDARDS = ('cougar-approved-grip-v1',)


def measured_fit(vertices, faces, config, donor_sha, working_sha, standard, native_origin):
    matrix = similarity_matrix(config, donor_sha)
    historical = config.get('historicalGripStandard')
    require(historical is None or historical in HISTORICAL_FIREARM_GRIP_STANDARDS,
            'Unsupported historical firearm grip standard declaration')
    require(standard.get('id') == (historical or FIREARM_GRIP_STANDARD)
            and standard.get('approval', {}).get('gripSizingApproved') is True,
            'Approved grip standard required: new firearm fits use '+FIREARM_GRIP_STANDARD)
    require(config.get('workingSourceSha256') == working_sha, 'Grip surface selection belongs to another working mesh')
    endpoints = np.asarray(config['gripEndpoints'], float)
    require(endpoints.shape == (2,3) and np.isfinite(endpoints).all(), 'Finite usable grip endpoints required')
    fitted_ends = transform(endpoints, matrix); center = fitted_ends.mean(axis=0)
    length = float(np.linalg.norm(fitted_ends[1]-fitted_ends[0]))
    require(abs(length/standard['usableLength']-1) <= 1e-5, 'Scale from the approved usable grip length')
    require(np.linalg.norm(center-np.asarray(native_origin)) <= .002, 'Grip midpoint differs from native hand attachment')
    axis = (fitted_ends[1]-fitted_ends[0])/length
    depth = np.asarray(config['nativeGripDepthAxis'], float)
    require(depth.shape == (3,) and np.isfinite(depth).all() and abs(np.linalg.norm(depth)-1)<1e-7
            and abs(np.dot(depth,axis))<1e-7, 'Reviewed depth axis must be unit and perpendicular to the grip')
    basis = np.column_stack((depth, axis, np.cross(depth,axis)))
    selected = np.asarray(config['gripSurfaceFaces'])
    require(selected.ndim == 1 and np.issubdtype(selected.dtype,np.integer) and len(selected)>=4
            and len(np.unique(selected))==len(selected) and selected.min()>=0 and selected.max()<len(faces),
            'Unique measured grip surface faces required')
    fitted = transform(vertices,matrix)
    local = (fitted-center)@basis
    sections = []
    for row in standard['referenceSections']:
        fraction=row['fractionFromPommel']
        depth_value,width_value=section_dimensions(local,np.asarray(faces)[selected],(fraction-.5)*length)
        sections.append({'fractionFromPommel':fraction,'depth':float(depth_value),'visibleFaceWidth':float(width_value)})
    middle=next(row for row in sections if row['fractionFromPommel']==.5)
    target=standard['targetMidpointSection']
    differences={name:middle[name]/target[name]-1 for name in ('depth','visibleFaceWidth')}
    report={'reference':standard['id'],'standardDigest':digest(standard),'workingSourceSha256':working_sha,
            'fitMatrix':matrix.tolist(),'usableLength':length,'nativeGripOrigin':center.tolist(),
            'nativeGripAxis':axis.tolist(),'nativeGripDepthAxis':depth.tolist(),
            'gripSurfaceFaceDigest':digest(selected.tolist()),'measuredFittedSections':sections,
            'midpointRelativeDifferences':differences,'uniformScale':float(np.linalg.norm(matrix[:3,0])),
            'proportionsAndAnglesPreserved':True}
    report['measurementDigest']=digest(report)
    if any(abs(v)>.05 for v in differences.values()):
        review=config.get('gripDeparture',{})
        if not (review.get('decision')=='approved' and review.get('measurementDigest')==report['measurementDigest']
                and isinstance(review.get('notes'),str) and review['notes'].strip()):
            raise GripDeparture(report)
        report['departureReview']=review
    return matrix,report
