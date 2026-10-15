"""Seam coverage and penetration diagnostics, v16 (additive to v15, which stays unchanged).

Changes from v15:
* Penetration needs a closed, consistently oriented surface, not a 2-manifold: every geometric
  edge's directed uses must cancel. Non-manifold seams where submeshes meet (female pelvis, feet)
  keep a well-defined winding number, so the same solid-angle test applies.
* Neck links: chest-neck and neck-head, measured on the assembly's own frames.
* A mesh lineage or topology difference makes only the affected link unavailable.
Diagnostic only: no anatomy, motion, native or client approval.
"""
import numpy as np
from .check_terminal_connectivity_v13 import LINKS
from .check_terminal_connectivity_v13b import source_controls, clipped_terminal_geometry
from .check_terminal_connectivity_v13c import triangle_minimum_distance
from .check_connector_surfaces_v15 import closest_surface, directional_coverage, inside_closed, quadrature, weighted_distribution

NECK_LINKS = (('chest', 'neck'), ('neck', 'head'))


def controls(left, right, frames):
    """Terminal bands: (start, end, distal) per part. Neck links use torso_g > neck_g > head_g."""
    p = lambda key: np.asarray(frames[key], float)[:3, 3]
    if (left, right) == ('chest', 'neck'):
        return (p('torso_g'), p('neck_g'), True), (p('neck_g'), p('head_g'), False), False
    if (left, right) == ('neck', 'head'):
        return (p('neck_g'), p('head_g'), True), (p('neck_g'), p('head_g'), False), False
    return source_controls(left, right, frames)


def closed_oriented_triangles(meshes, part):
    """Rendered triangles of a part when every geometric edge's directed uses cancel; else None.

    Returns (triangles, report). Exact coincident positions across UV splits share an edge; this is
    a read-only test and never welds topology."""
    triangles = []; edges = {}
    for m in meshes:
        if m['part'] != part or not m.get('render', True):
            continue
        tri = np.asarray(m['position'], float)[np.asarray(m['faces'], int)]; triangles.extend(tri)
        for t in tri:
            for i, j in ((0, 1), (1, 2), (2, 0)):
                a = tuple(t[i]); b = tuple(t[j]); key = tuple(sorted((a, b)))
                edges.setdefault(key, []).append(1 if a <= b else -1)
    if not triangles:
        return None, {'part': part, 'status': 'absent'}
    open_edges = sum(1 for v in edges.values() if sum(v) != 0)
    non_manifold = sum(1 for v in edges.values() if len(v) != 2)
    report = {'part': part, 'edges': len(edges), 'unbalancedEdges': open_edges, 'nonManifoldEdges': non_manifold,
              'surface': 'open' if open_edges else ('closed-manifold' if not non_manifold else 'closed-oriented-nonmanifold')}
    return (None if open_edges else np.asarray(triangles, float)), report


def penetration(source_points, candidate_points, weights, source_closed, candidate_closed, scale, epsilon=1e-8):
    (s_tri, s_report), (c_tri, c_report) = source_closed, candidate_closed
    surfaces = {'source': s_report, 'candidate': c_report}
    if s_tri is None or c_tri is None:
        return {'status': 'unavailable', 'surfaces': surfaces,
                'reason': 'Opposite owning part has unbalanced (open) edges; solid penetration is undefined'}
    sd, _, _ = closest_surface(source_points, s_tri); cd, _, _ = closest_surface(candidate_points, c_tri)
    si = inside_closed(source_points, s_tri) & (sd > epsilon); ci = inside_closed(candidate_points, c_tri) & (cd > epsilon)
    source_depth = np.where(si, sd, 0.); candidate_depth = np.where(ci, cd, 0.); new = candidate_depth > scale*source_depth + epsilon
    return {'status': 'measured', 'surfaces': surfaces,
            'sourceInsideAreaFraction': float(weights[si].sum()/weights.sum()), 'candidateInsideAreaFraction': float(weights[ci].sum()/weights.sum()),
            'sourceCalibratedWorsenedPenetrationAreaFraction': float(weights[new].sum()/weights.sum()),
            'sourceDepthMeters': weighted_distribution(source_depth, weights), 'candidateDepthMeters': weighted_distribution(candidate_depth, weights),
            'limitations': 'Finite source surface samples inside the opposite closed oriented part (winding number); not collision resolution or anatomy approval'}


def lineage(source, candidate, parts):
    """Source and candidate meshes of these parts must match in name, render flag, vertex count and faces."""
    s = [m for m in source if m['part'] in parts]; c = [m for m in candidate if m['part'] in parts]
    if len(s) != len(c):
        raise ValueError('Mesh count differs for ' + '/'.join(parts))
    for a, b in zip(s, c):
        if (a['part'], a['name'], a.get('render', True)) != (b['part'], b['name'], b.get('render', True)) \
                or np.asarray(a['position']).shape != np.asarray(b['position']).shape or not np.array_equal(a['faces'], b['faces']):
            raise ValueError('Source-owned mesh/topology lineage differs for ' + a['part'])


def audit(source, candidate, source_frames, candidate_frames, part_scales=None, links=LINKS + NECK_LINKS):
    rows = []; scales = part_scales or {}; closed = {}
    for left, right in links:
        try:
            lineage(source, candidate, (left, right))
            ac, bc, fallback = controls(left, right, source_frames)
            sa, ca = clipped_terminal_geometry(source, candidate, left, ac); sb, cb = clipped_terminal_geometry(source, candidate, right, bc)
            scale = min(float(scales.get(left, 1.)), float(scales.get(right, 1.)))
            if not np.isfinite(scale) or scale <= 0:
                raise ValueError('Positive adjacent part scale required')
            directions = []
            for name, s, c, other_s, other_c, other_part in ((left, sa, ca, sb, cb, right), (right, sb, cb, sa, ca, left)):
                row = directional_coverage(s, c, other_s, other_c, scale); row['sampleOwner'] = name
                sp, cp, w = quadrature(s, c)
                if other_part not in closed:
                    closed[other_part] = (closed_oriented_triangles(source, other_part), closed_oriented_triangles(candidate, other_part))
                row['penetration'] = penetration(sp, cp, w, *closed[other_part], scale)
                directions.append(row)
            rows.append({'parts': [left, right], 'status': 'measured', 'sourceMinimumClearanceMeters': triangle_minimum_distance(sa, sb),
                         'candidateMinimumClearanceMeters': triangle_minimum_distance(ca, cb), 'directions': directions,
                         'coincidentTorsoPivotFallbackApplied': fallback, 'minimumContactAloneCertifiesCoverage': False})
        except (KeyError, ValueError) as error:
            rows.append({'parts': [left, right], 'status': 'unavailable', 'reason': str(error)})
    return {'kind': 'source-owned-area-seam-and-penetration-diagnostic-v16', 'connectors': rows,
            'links': [list(link) for link in links],
            'allRequestedConnectorsMeasured': all(r['status'] == 'measured' for r in rows),
            'sourceTerminalAuthority': 'Exact source native proximal/distal 25% clipped triangles with identical candidate barycentric transport; no candidate re-detection',
            'penetrationSurfacePolicy': 'closed oriented surface (directed edge uses cancel); non-manifold edges allowed',
            'candidateFramesUsedToRedetectTerminals': False, 'coverageAcceptanceThresholdInvented': False, 'rasterAllowanceAdded': False,
            'assetApprovalCreated': False, 'anatomyAcceptance': False, 'motionAcceptance': False, 'nativeValidated': False,
            'clientValidated': False, 'productionAccepted': False}
