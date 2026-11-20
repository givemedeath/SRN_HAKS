"""The sky dome: an inward-facing UV sphere as an ASCII NWN model.

u runs once round the horizon counter-clockwise from +x (0 to 1, the seam's vertices doubled so the texture
coordinate wraps), v from the nadir (0) to the zenith (1). The poles are fans of their own vertices, one per segment,
each at its segment's middle u, so no triangle spans the whole texture."""
import math

RADIUS = 675.0
SEGMENTS = 64   # round the horizon
RINGS = 32      # pole to pole


def mesh(radius=RADIUS, segments=SEGMENTS, rings=RINGS):
    """(vertices, uvs, faces): faces wind so their normals face the sphere's centre."""
    vertices, uvs, faces = [], [], []
    index = {}
    for i in range(1, rings):
        v = i / rings
        elevation = (v - 0.5) * math.pi
        for j in range(segments + 1):
            u = j / segments
            azimuth = u * 2 * math.pi
            index[i, j] = len(vertices)
            vertices.append((radius * math.cos(elevation) * math.cos(azimuth), radius * math.cos(elevation) * math.sin(azimuth),
                             radius * math.sin(elevation)))
            uvs.append((u, v))
    for i in range(1, rings - 1):
        for j in range(segments):
            a, b, c, d = index[i, j], index[i, j + 1], index[i + 1, j + 1], index[i + 1, j]
            faces += [(a, c, b), (a, d, c)]
    for j in range(segments):
        u = (j + 0.5) / segments
        bottom = len(vertices); vertices.append((0.0, 0.0, -radius)); uvs.append((u, 0.0))
        faces.append((bottom, index[1, j], index[1, j + 1]))
        top = len(vertices); vertices.append((0.0, 0.0, radius)); uvs.append((u, 1.0))
        faces.append((top, index[rings - 1, j + 1], index[rings - 1, j]))
    return vertices, uvs, faces


def ascii_model(name, bitmap, radius=RADIUS):
    """The model's ASCII MDL text: one self-lit, shadowless trimesh."""
    vertices, uvs, faces = mesh(radius)
    lines = [
        f'# SRN dynamic sky dome, written by tools/skykit',
        'filedependancy srn_skykit',
        f'newmodel {name}',
        f'setsupermodel {name} NULL',
        'classification Effect',
        'setanimationscale 1.0',
        f'beginmodelgeom {name}',
        f'node dummy {name}',
        '  parent NULL',
        'endnode',
        f'node trimesh {name}_dome',
        f'  parent {name}',
        '  position 0.0 0.0 0.0',
        '  orientation 0.0 0.0 0.0 0.0',
        '  wirecolor 1.0 1.0 1.0',
        '  ambient 1.0 1.0 1.0',
        '  diffuse 1.0 1.0 1.0',
        '  specular 0.0 0.0 0.0',
        '  shininess 1.0',
        '  selfillumcolor 1.0 1.0 1.0',
        '  shadow 0',
        '  render 1',
        '  beaming 0',
        '  inheritcolor 0',
        '  rotatetexture 0',
        '  tilefade 0',
        '  transparencyhint 0',
        '  alpha 1.0',
        f'  bitmap {bitmap}',
        f'  verts {len(vertices)}',
    ]
    lines += [f'    {x:.4f} {y:.4f} {z:.4f}' for x, y, z in vertices]
    lines.append(f'  faces {len(faces)}')
    lines += [f'    {a} {b} {c} 1 {a} {b} {c} 1' for a, b, c in faces]
    lines.append(f'  tverts {len(uvs)}')
    lines += [f'    {u:.6f} {v:.6f} 0' for u, v in uvs]
    lines += ['endnode', f'endmodelgeom {name}', f'donemodel {name}', '']
    return '\n'.join(lines)
