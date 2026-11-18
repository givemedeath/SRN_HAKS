"""How far a fitted firearm leans sideways in the hand.

A firearm is, to a close approximation, mirror-symmetric about the plane its barrel and grip lie in. In the native
weapon frame that plane should be x = constant: x is across the gun, y up, the barrel down -z. A generated model can
arrive rolled about its barrel or toed to one side, and a fit that only levels the gun keeps that tilt (the wave-1
Fichetti leaned 6 degrees in the hand before anyone measured it).

The measure needs only numpy, so the fit worker can take it inside Blender. The surface is sampled evenly, binned
into cells seen from the side (y, z), and each cell's middle between its leftmost and rightmost sample is taken as a
point of the gun's middle surface. A plane x = a*y + b*z + c is fitted to those middles by least absolute deviation,
so a charging handle, a cheek piece or a one-sided lever (few cells, far off) does not turn the answer. atan(a) is
the roll about the barrel, atan(b) the toe to one side, and the lean is the angle between that plane and x = constant.
"""
import numpy as np
from tools.headkit.common import require

LIMIT_DEGREES = 1.5
CELL = .004
SAMPLES = 200_000
MINIMUM_CELLS = 150


def middle_surface(vertices, faces, cell=CELL, samples=SAMPLES):
    """(y, z, x middle) for each side-view cell that holds both faces of the gun."""
    vertices = np.asarray(vertices, float); faces = np.asarray(faces)
    require(vertices.ndim == 2 and vertices.shape[1] == 3 and faces.ndim == 2 and faces.shape[1] == 3 and len(faces) >= 4,
            'A triangle mesh is required to measure a sideways lean')
    a, b, c = (vertices[faces[:, i]] for i in range(3))
    area = np.linalg.norm(np.cross(b - a, c - a), axis=1) / 2
    require(area.sum() > 0, 'A mesh with area is required to measure a sideways lean')
    rng = np.random.default_rng(0)                       # the same samples for the same mesh
    pick = rng.choice(len(faces), samples, p=area / area.sum()); u, v = rng.random(samples), rng.random(samples)
    over = u + v > 1; u[over], v[over] = 1 - u[over], 1 - v[over]
    points = a[pick] + u[:, None] * (b[pick] - a[pick]) + v[:, None] * (c[pick] - a[pick])
    keys = np.floor(points[:, 1:] / cell).astype(np.int64); keys -= keys.min(0)
    flat = keys[:, 0] * (keys[:, 1].max() + 1) + keys[:, 1]
    order = np.argsort(flat, kind='stable'); flat, points = flat[order], points[order]
    starts = np.flatnonzero(np.r_[True, flat[1:] != flat[:-1]]); counts = np.diff(np.r_[starts, len(flat)])
    low = np.minimum.reduceat(points[:, 0], starts); high = np.maximum.reduceat(points[:, 0], starts)
    centre = np.add.reduceat(points[:, 1:], starts) / counts[:, None]
    both = (counts >= 4) & (high - low > cell / 2)       # one skin alone has no middle
    return np.column_stack((centre[both], (low[both] + high[both]) / 2))


def sideways_lean(vertices, faces, cell=CELL, samples=SAMPLES):
    """The tilt of a native-frame firearm's middle plane from x = constant, in degrees."""
    middle = middle_surface(vertices, faces, cell, samples)
    require(len(middle) >= MINIMUM_CELLS, 'Too little of the firearm has two sides to measure a sideways lean')
    design = np.column_stack((middle[:, 0], middle[:, 1], np.ones(len(middle)))); x = middle[:, 2]
    weights = np.ones(len(x))
    for _ in range(60):                                  # least absolute deviation by reweighting
        root = np.sqrt(weights); solution = np.linalg.lstsq(design * root[:, None], x * root, rcond=None)[0]
        weights = 1 / np.maximum(np.abs(x - design @ solution), 1e-5)
    roll, toe = (float(np.degrees(np.arctan(value))) for value in solution[:2])
    lean = float(np.degrees(np.arctan(np.hypot(solution[0], solution[1]))))
    return {'rollDegrees': roll, 'toeDegrees': toe, 'leanDegrees': lean, 'middleOffset': float(solution[2]),
            'cells': int(len(middle)), 'medianResidual': float(np.median(np.abs(x - design @ solution))),
            'limitDegrees': LIMIT_DEGREES}


def reviewed_lean(vertices, faces, review=None):
    """The fitted firearm's lean; beyond LIMIT_DEGREES it needs an approved review of this very measurement.

    The review is for a gun whose own shape is lopsided, or a published fit replayed as it shipped:
    {'decision': 'approved', 'leanDegrees': the measured lean (to 0.05), 'notes': why it stands}."""
    report = sideways_lean(vertices, faces)
    if report['leanDegrees'] <= LIMIT_DEGREES: return report
    review = review or {}
    stands = (review.get('decision') == 'approved' and isinstance(review.get('leanDegrees'), (int, float))
              and abs(review['leanDegrees'] - report['leanDegrees']) <= .05 and isinstance(review.get('notes'), str) and review['notes'].strip())
    require(stands, f"The firearm leans {report['leanDegrees']:.2f} degrees sideways in the hand (roll {report['rollDegrees']:.2f}, "
                    f"toe {report['toeDegrees']:.2f}; limit {LIMIT_DEGREES}): square its frame to its own middle plane before fitting, "
                    'or bind fit.sidewaysLeanReview to this measurement')
    return {**report, 'review': review}


def squaring_turn(vertices, faces, pivot=(0, 0, 0), passes=3):
    """The rotation about `pivot` that stands a native-frame firearm's middle plane at x = constant by the smallest
    turn. It is rigid: size, proportions, the grip-to-barrel angle and the texture mapping are untouched."""
    vertices = np.asarray(vertices, float); pivot = np.asarray(pivot, float); total = np.eye(3); moved = vertices
    for _ in range(passes):
        report = sideways_lean(moved, faces)
        normal = np.array([1, -np.tan(np.radians(report['rollDegrees'])), -np.tan(np.radians(report['toeDegrees']))])
        normal /= np.linalg.norm(normal); axis = np.cross(normal, [1, 0, 0]); sine = np.linalg.norm(axis)
        if sine < 1e-6: break
        k = axis / sine; cross = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
        total = (np.eye(3) + sine * cross + (1 - normal[0]) * cross @ cross) @ total
        moved = (vertices - pivot) @ total.T + pivot
    return total


def straightened_model(text, pivot=(0, 0, 0)):
    """An ASCII model of one firearm part with every mesh turned by its visible mesh's squaring turn.

    For a published gun whose fit can no longer be rerun: the first trimesh is measured, and all `verts` blocks (the
    shadow too) take the same turn. Returns (text, record); the record's matrix moves hand-placed points with it."""
    import re
    blocks = list(re.finditer(r'(?m)^(\s*)verts\s+(\d+)[^\n]*\n', text)); require(blocks, 'No mesh to straighten')
    def rows(match, count): return text[match.end():].split('\n', count)[:count]
    first = blocks[0]; vertices = np.array([[float(v) for v in row.split()[:3]] for row in rows(first, int(first[2]))])
    faces = re.search(r'(?m)^\s*faces\s+(\d+)[^\n]*\n', text[first.end():]); start = first.end() + faces.end()
    triangles = np.array([[int(v) for v in row.split()[:3]] for row in text[start:].split('\n', int(faces[1]))[:int(faces[1])]])
    pivot = np.asarray(pivot, float); turn = squaring_turn(vertices, triangles, pivot); before = sideways_lean(vertices, triangles)
    after = sideways_lean((vertices - pivot) @ turn.T + pivot, triangles)
    require(after['leanDegrees'] <= .3, 'The squaring turn did not stand the firearm upright')
    out, at = [], 0
    for match in blocks:
        count = int(match[2]); lines = rows(match, count); end = match.end() + sum(len(line) + 1 for line in lines)
        points = np.array([[float(v) for v in line.split()[:3]] for line in lines]); points = (points - pivot) @ turn.T + pivot
        tail = '\r' if lines and lines[0].endswith('\r') else ''
        out += [text[at:match.end()], ''.join(f'{match[1]}    {x: .7f} {y: .7f} {z: .7f}{tail}\n' for x, y, z in points)]; at = end
    out.append(text[at:])
    return ''.join(out), {'before': before, 'after': after, 'matrix': turn.tolist(), 'pivot': pivot.tolist()}
