"""Early, read-only geometry and runtime-UV checks before expensive finishing."""
import hashlib
import numpy as np
from tools.headkit.common import require
from tools.headkit.uv import raster_audit, chart_ids
from .geometry import topology, protected_checks
from .atlas import region_gutters


def geometry_report(vertices, faces, processing, *, budget=None):
    p = np.asarray(vertices, float); f = np.asarray(faces)
    report = topology(p, f)
    euler = report['eulerCharacteristic']; genus = report['totalGenus']
    blockers = []
    if not report['closedWound']: blockers.append('nonclosed-or-invalid-winding')
    if budget is not None and len(f) > budget: blockers.append('triangle-budget')
    try: probes = protected_checks(p, f, processing)
    except ValueError as exc:
        probes = {'error': str(exc)}; blockers.append('protected-feature')
    return {'passed': not blockers, 'blockers': blockers, 'topology': report,
            'eulerCharacteristic': euler, 'totalGenus': genus, 'probes': probes,
            'shadowRecommendation': 'measured-proxy' if genus is not None and genus > 8 else 'bounded-decimation-or-measured-proxy',
            'visualReviewRequired': True}


def target_hash(corners, uv):
    digest = hashlib.sha256()
    for array in (corners, uv):
        values = np.ascontiguousarray(array, dtype='<f8')
        digest.update(str(values.shape).encode()); digest.update(values.tobytes())
    return digest.hexdigest()


def uv_report(corners, uv, caps, size, *, minimum_coverage=.30, maximum_unmapped=.001, regions=None):
    corners = np.asarray(corners, float); uv = np.asarray(uv, float); caps = np.asarray(caps)
    require(corners.shape == (len(uv),3,3) and uv.shape == (len(corners),3,2)
            and caps.shape == (len(uv),) and caps.dtype == bool, 'Exact UV/corner/cap correspondence required')
    require(np.isfinite(corners).all() and np.isfinite(uv).all(), 'Finite geometry and UVs required')
    require(type(size) is int and 32 <= size <= 4096, 'Bounded UV preflight size required')
    visible = np.flatnonzero(~caps); require(len(visible)>0, 'No visible UV surface')
    if np.any((uv<0)|(uv>1)):
        return {'passed':False,'blockers':['uv-outside-atlas'],'size':size,'targetHash':target_hash(corners,uv)}
    atlas = uv[visible]; audit, owners = raster_audit(atlas, size)
    if regions is None: charts = chart_ids(atlas)
    else:
        regions=np.asarray(regions)
        require(regions.shape==(len(uv),) and np.issubdtype(regions.dtype,np.integer) and np.all(regions>=0), 'Invalid retained UV regions')
        charts=regions[visible]
    mapped = np.unique(owners[owners>=0])
    missing = np.setdiff1d(np.arange(len(atlas)), mapped)
    area = np.linalg.norm(np.cross(corners[visible,1]-corners[visible,0],corners[visible,2]-corners[visible,0]),axis=1)
    require(area.sum()>0, 'Empty visible surface')
    fraction = float(area[missing].sum()/area.sum())
    missing_charts = np.setdiff1d(np.unique(charts), np.unique(charts[mapped]))
    # Hidden caps may intentionally share one palette, but cannot overlap or
    # bleed into visible charts. All cap triangles share one ownership region.
    if caps.any():
        cap_audit, cap_owners = raster_audit(uv[caps], size)
        cap_pixels = cap_owners >= 0
    else: cap_pixels = np.zeros_like(owners, dtype=bool)
    overlap = int(np.count_nonzero(cap_pixels & (owners>=0)))
    labels = owners.copy(); labels[cap_pixels] = len(atlas)
    gutters = region_gutters(labels, np.r_[charts, charts.max()+1])
    blockers = []
    if audit['overlapFaces'] or audit['degenerateUvFaces']: blockers.append('overlap-or-degenerate-uv')
    if overlap: blockers.append('cap-visible-overlap')
    if caps.any() and cap_audit['degenerateUvFaces']: blockers.append('degenerate-cap-uv')
    if audit['coverageFraction'] < minimum_coverage: blockers.append('low-coverage')
    if len(missing_charts) or fraction >= maximum_unmapped: blockers.append('unsampled-surface')
    if gutters['nearbyChartPixelsByRadius']['2']: blockers.append('insufficient-gutter')
    return {'passed': not blockers, 'blockers': blockers, 'size':size, 'raster':audit,
            'regionAuthority':'bound-atlas-lineage' if regions is not None else 'reconstructed-uv-connectivity',
            'unmappedSurfaceFraction':fraction, 'missingCharts':missing_charts.tolist(),
            'capVisibleOverlapPixels':overlap, 'gutters':gutters,
            'targetHash':target_hash(corners,uv)}


def region_hash(corners, uv, regions):
    digest=hashlib.sha256(target_hash(corners,uv).encode())
    digest.update(np.asarray(regions,dtype='<i8').tobytes())
    return digest.hexdigest()
