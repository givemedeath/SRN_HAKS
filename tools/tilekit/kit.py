"""The detail kit: pieces made from code, and the one atlas texture they all draw.

Every piece is an uncompiled model of one trimesh node, its origin where it is fixed. A wall piece's back lies on the
plane y = 0 and it stands out toward +y, so `detail`'s turn points +y away from the wall; a roof piece stands on z = 0.
Each face takes its picture from one cell of the atlas, by projecting the face onto its own plane: 1 m of surface is
`METRE` of a cell, and a larger face is shrunk to fit its cell. The atlas is a grid of `CELLS` x `CELLS` cells made from
the CC0 scans of the shared tool root (`material.master`), toned to a colour of the cell's own, and written with
`material.write` as one material and its maps.

Pieces that stand on a roof are blocks: walled, and cut out of a walkable roof as cover (`cuts`). Pieces on a wall
are thin or high: they never stand where a player walks."""
import math
from pathlib import Path

import numpy as np

from . import material, require

ATLAS = 'dgt04_kit'  # the material and its maps' stem
SIZE = 2048
CELLS = 4
METRE = 0.45  # of a cell's side per metre of surface
MARGIN = 0.03  # of a cell's side kept clear round its edge, so a mip level does not bleed the next cell in

# cell: (scan folder or None, tone [r, g, b] or None, roughness, metal) — None scan: flat colour
LOOKS = {
    'casing': (None, (168, 170, 164), 0.55, 0.2),  # painted sheet metal: an appliance's case
    'grille': (None, (46, 48, 50), 0.6, 0.6),
    'rust': ('Rust009', None, None, None),
    'corrugated': ('CorrugatedSteel009', (140, 142, 138), None, None),
    'planks': ('Planks023A', (120, 98, 72), None, None),
    'galvanised': (None, (132, 138, 142), 0.45, 0.7),
    'paint': (None, (196, 196, 188), 0.5, 0.1),
    'rubber': (None, (24, 24, 26), 0.85, 0.0),
    'iron': ('MetalPlates013', (44, 42, 40), None, None),
    'concrete': ('Concrete034', (122, 120, 116), None, None),
    'red': (None, (210, 26, 18), 0.4, 0.0),  # a warning light: glows
    'steel': (None, (150, 155, 160), 0.32, 0.85),  # clean brushed steel: the corporate towers' pieces
    'white': (None, (236, 240, 244), 0.5, 0.0),  # a lit sign's face: glows
    'yellow': (None, (222, 178, 24), 0.55, 0.0),  # hazard yellow
    'ember': (None, (255, 120, 30), 0.9, 0.0),  # embers in a burn barrel: glows
    'grating': (None, (74, 72, 68), 0.65, 0.6),  # a steel grating: square holes between bars
}
ORDER = list(LOOKS)
GRIMY = {'casing': 0.16, 'galvanised': 0.14, 'paint': 0.18, 'steel': 0.08, 'grating': 0.2}  # flat looks given light weathering: soft blotches and faint streaks, this strong
GLOWS = {'red': (255, 48, 36), 'white': (210, 220, 230), 'ember': (255, 110, 24)}  # cells that glow whole


def cell_of(look):
    index = ORDER.index(look); return index % CELLS, index // CELLS


def _grime(side, seed):
    """[0, 1] weathering of a cell, `side` square: soft blotches and faint streaks running down, the same each build."""
    from PIL import Image, ImageFilter
    rng = np.random.default_rng(seed)
    blotch = np.asarray(Image.fromarray(np.uint8(rng.random((8, 8)) * 255)).resize((side, side), Image.BICUBIC), np.float64) / 255
    streaks = np.asarray(Image.fromarray(np.uint8(rng.random((1, 48)) * 255)).resize((side, side), Image.BILINEAR), np.float64) / 255
    fine = np.asarray(Image.fromarray(np.uint8(rng.random((side, side)) * 255)).filter(ImageFilter.GaussianBlur(1.2)), np.float64) / 255
    return np.clip(0.5 * blotch + 0.35 * streaks ** 3 + 0.15 * fine, 0, 1)


def atlas(masters):
    """{colour, normal, roughness, metal} of the kit's atlas, `SIZE` square."""
    side = SIZE // CELLS; colour = np.zeros((SIZE, SIZE, 3), np.uint8); normal = np.zeros((SIZE, SIZE, 3), np.uint8)
    roughness = np.zeros((SIZE, SIZE)); metal = np.zeros((SIZE, SIZE)); glow = np.zeros((SIZE, SIZE, 3), np.uint8)
    for look, (scan, tone, rough, metallic) in LOOKS.items():
        column, row = cell_of(look); box = (slice(row * side, (row + 1) * side), slice(column * side, (column + 1) * side))
        if scan:
            maps = material.master(Path(masters) / scan); size = (side, side)
            made = {'colour': material._sized(maps['colour'], size), 'normal': material._renormal(material._sized(maps['normal'], size)),
                    'roughness': material._sized(maps['roughness'], size), 'metal': material._sized(maps['metal'], size)}
            if tone is not None:
                mean = made['colour'].reshape(-1, 3).mean(0); made['colour'] = np.uint8(np.clip(made['colour'] * (np.array(tone) / np.maximum(mean, 1)), 0, 255))
        else:
            made = {'colour': np.full((side, side, 3), tone, np.uint8), 'normal': np.full((side, side, 3), (128, 128, 255), np.uint8),
                    'roughness': np.full((side, side), rough), 'metal': np.full((side, side), metallic)}
            if look in GRIMY:
                made['colour'] = np.uint8(np.clip(made['colour'] * (1 - GRIMY[look] * _grime(side, ORDER.index(look)))[..., None], 0, 255))
            if look == 'grating':  # a hole every 16 pixels, about 7 cm, its bars' edges lit
                rows = np.arange(side) % 16; hole = (rows[:, None] >= 4) & (rows[None, :] >= 4); made['colour'][hole] = (14, 14, 16)
                made['normal'][(rows == 3)[:, None] & ~hole] = (128, 200, 220)
            if look == 'grille':  # slats across: a dark gap every 24 pixels, lit tops
                rows = np.arange(side) % 24; made['colour'][rows < 6] = (18, 18, 20)
                made['normal'][rows == 6] = (128, 200, 220); made['normal'][rows == 23] = (128, 56, 220)
        if rough is not None:
            made['roughness'] = np.full((side, side), rough)
        if metallic is not None:
            made['metal'] = np.full((side, side), metallic)
        colour[box], normal[box], roughness[box], metal[box] = made['colour'], made['normal'], made['roughness'], made['metal']
        if look in GLOWS:
            colour[box] = GLOWS[look]; glow[box] = GLOWS[look]
    return {'colour': colour, 'normal': normal, 'roughness': roughness, 'metal': metal, 'glow': glow}


class Mesh:
    """Vertices, texture vertices and faces of one piece, faces textured from their atlas cell. A face drawn with a
    `smooth` key shares its corners with the other faces of that key, so the client rounds the light across them (a
    pipe's sides); every other face has corners of its own and a hard edge."""

    def __init__(self):
        self.verts, self.tverts, self.faces = [], [], []; self.shared = {}; self.keys = 0

    def key(self):
        """A new smoothing key: one round surface."""
        self.keys += 1; return self.keys

    def _vertex(self, point, smooth):
        point = tuple(float(value) for value in point)
        if smooth is None:
            self.verts.append(point); return len(self.verts) - 1
        found = (smooth,) + tuple(round(value, 5) for value in point)
        if found not in self.shared:
            self.verts.append(point); self.shared[found] = len(self.verts) - 1
        return self.shared[found]

    def triangle(self, a, b, c, look, *, smooth=None, frame=None):
        """A face a→b→c (counter-clockwise seen from its front), its picture projected from its own plane (or from
        `frame`, (kept axes, low corner, scale), which a quad shares between its two halves so its picture runs on)."""
        u = [b[axis] - a[axis] for axis in range(3)]; v = [c[axis] - a[axis] for axis in range(3)]
        normal = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        if math.hypot(*normal) < 1e-12:
            return
        if frame is None:
            frame = _frame((a, b, c), normal)
        keep, low, scale = frame; column, row = cell_of(look)
        tbase = len(self.tverts); corners = [self._vertex(point, smooth) for point in (a, b, c)]
        for point in (a, b, c):  # a texture vertex's v runs up the picture: rows from the bottom
            x, y = point[keep[0]], point[keep[1]]
            self.tverts.append(((column + MARGIN + (x - low[0]) * scale) / CELLS, 1 - (row + MARGIN + (y - low[1]) * scale) / CELLS))
        self.faces.append((*corners, 1, tbase, tbase + 1, tbase + 2, 1))

    def quad(self, a, b, c, d, look, *, smooth=None):
        normal = np.cross(np.subtract(c, a), np.subtract(d, b))
        frame = _frame((a, b, c, d), normal) if np.linalg.norm(normal) > 1e-12 else None
        self.triangle(a, b, c, look, smooth=smooth, frame=frame); self.triangle(a, c, d, look, smooth=smooth, frame=frame)

    def facing(self, points, look, out, *, smooth=None, frame=None):
        """A triangle or a quad wound to face `out`; `frame` a picture projection shared with its neighbours."""
        normal = np.cross(np.subtract(points[1], points[0]), np.subtract(points[-1], points[0])) if len(points) == 3 else np.cross(np.subtract(points[2], points[0]), np.subtract(points[3], points[1]))
        if np.dot(normal, out) < 0:
            points = points[::-1]
        if len(points) == 3:
            self.triangle(*points, look, smooth=smooth, frame=frame)
        else:
            self.quad(*points, look, smooth=smooth)

    def box(self, low, high, look, *, front=None, skip=(), bevel=0.0):
        """An axis-aligned box from `low` to `high`; `front` the look of its +y face; `skip` the faces left off
        ('-y' against a wall, '-z' on a roof); `bevel` metres cut off its edges and corners, which catch the light as
        a real case's rounded edges do."""
        if not bevel:
            (x0, y0, z0), (x1, y1, z1) = low, high
            sides = {'+x': ((x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)), '-x': ((x0, y1, z0), (x0, y0, z0), (x0, y0, z1), (x0, y1, z1)),
                     '+y': ((x1, y1, z0), (x0, y1, z0), (x0, y1, z1), (x1, y1, z1)), '-y': ((x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)),
                     '+z': ((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)), '-z': ((x0, y1, z0), (x1, y1, z0), (x1, y0, z0), (x0, y0, z0))}
            for name, corners in sides.items():
                if name not in skip:
                    self.quad(*corners, front if name == '+y' and front else look)
            return
        centre = [(low[axis] + high[axis]) / 2 for axis in range(3)]; half = [(high[axis] - low[axis]) / 2 for axis in range(3)]
        cut = min(bevel, 0.45 * min(half))

        def at(offsets):
            return tuple(centre[axis] + offsets[axis] for axis in range(3))
        for axis in range(3):  # the faces, inset
            for sign in (-1, 1):
                name = ('+' if sign > 0 else '-') + 'xyz'[axis]
                if name in skip:
                    continue
                j, k = [other for other in range(3) if other != axis]; corners = []
                for sj, sk in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                    offsets = [0.0] * 3; offsets[axis] = sign * half[axis]; offsets[j] = sj * (half[j] - cut); offsets[k] = sk * (half[k] - cut)
                    corners.append(at(offsets))
                out = [0.0] * 3; out[axis] = sign
                self.facing(corners, front if name == '+y' and front else look, out)
        for a, b in ((0, 1), (0, 2), (1, 2)):  # the cut edges
            c = 3 - a - b
            for sa in (-1, 1):
                for sb in (-1, 1):
                    corners = []
                    for along, (ka, kb) in ((-1, (half[a], half[b] - cut)), (1, (half[a], half[b] - cut)), (1, (half[a] - cut, half[b])), (-1, (half[a] - cut, half[b]))):
                        offsets = [0.0] * 3; offsets[a] = sa * ka; offsets[b] = sb * kb; offsets[c] = along * (half[c] - cut)
                        corners.append(at(offsets))
                    out = [0.0] * 3; out[a] = sa; out[b] = sb
                    self.facing(corners, look, out)
        for sx in (-1, 1):  # the cut corners
            for sy in (-1, 1):
                for sz in (-1, 1):
                    signs = (sx, sy, sz); corners = []
                    for axis in range(3):
                        corners.append(at([signs[other] * (half[other] if other == axis else half[other] - cut) for other in range(3)]))
                    self.facing(corners, look, signs)

    def extend(self, other, move):
        """Another mesh's faces added, its vertices taken by `move` (a rigid turn: its pictures stay as they were)."""
        base, tbase = len(self.verts), len(self.tverts)
        self.verts += [move(vertex) for vertex in other.verts]; self.tverts += other.tverts
        self.faces += [(a + base, b + base, c + base, group, ta + tbase, tb + tbase, tc + tbase, material)
                       for a, b, c, group, ta, tb, tc, material in other.faces]

    def beam(self, start, end, y0, y1, depth, look):
        """A slanted beam in the x-z plane from `start` (x, z) to `end`, between y0 and y1, `depth` deep upward: a
        stair's stringer or handrail."""
        (xa, za), (xb, zb) = start, end
        a0, b0, c0, d0 = (xa, y0, za), (xb, y0, zb), (xb, y0, zb + depth), (xa, y0, za + depth)
        a1, b1, c1, d1 = (xa, y1, za), (xb, y1, zb), (xb, y1, zb + depth), (xa, y1, za + depth)
        for face in ((b1, a1, d1, c1), (a0, b0, c0, d0), (d0, c0, c1, d1), (a1, b1, b0, a0), (b0, b1, c1, c0), (a1, a0, d0, d1)):
            self.quad(*face, look)

    def tube(self, path, radius, look, *, sides=8, start=False, end=False):
        """A round pipe along `path` (points), its sides smooth, mitred at its bends; `start` and `end` close its ends."""
        points = [np.array(point, float) for point in path]; smooth = self.key()
        ways = [(points[index + 1] - points[index]) / np.linalg.norm(points[index + 1] - points[index]) for index in range(len(points) - 1)]
        side = np.cross(ways[0], (0.0, 0.0, 1.0) if abs(ways[0][2]) < 0.9 else (1.0, 0.0, 0.0)); side /= np.linalg.norm(side)
        rings = []
        for index, point in enumerate(points):
            way = ways[min(index, len(ways) - 1)]
            incoming = ways[index - 1] if index else way
            if index >= 2:  # the frame carried round the bend before this point; the ring is cut on the plane halving it below
                side = _carried(side, ways[index - 2], incoming)
            up = np.cross(incoming, side)
            ring = [point + radius * (math.cos(2 * math.pi * k / sides) * side + math.sin(2 * math.pi * k / sides) * up) for k in range(sides)]
            if 0 < index < len(ways):
                mitre = ways[index - 1] + ways[index]; mitre /= np.linalg.norm(mitre)
                ring = [corner - incoming * (np.dot(corner - point, mitre) / np.dot(incoming, mitre)) for corner in ring]
            rings.append(ring)
        for index in range(len(points) - 1):
            middle = (points[index] + points[index + 1]) / 2
            for k in range(sides):
                corners = [tuple(rings[index][k]), tuple(rings[index][(k + 1) % sides]), tuple(rings[index + 1][(k + 1) % sides]), tuple(rings[index + 1][k])]
                self.facing(corners, look, np.mean(corners, axis=0) - middle, smooth=smooth)
        for closed, index, out in ((start, 0, -ways[0]), (end, len(points) - 1, ways[-1])):
            if closed:
                for k in range(sides):
                    self.facing([tuple(rings[index][k]), tuple(rings[index][(k + 1) % sides]), tuple(points[index])], look, out)

    def cylinder(self, centre, radius, height, look, *, sides=10, top=True, bottom=False, axis='z'):
        """A cylinder up from `centre` (along `axis`, 'z', 'y' or 'x'), its sides smooth; `bottom` closes its foot,
        which a shadow caster held off the ground needs: an open end lets the engine's shadow volume through and
        darkens the near wall."""
        smooth = self.key()

        def at(angle, h):
            c, s = math.cos(angle) * radius, math.sin(angle) * radius
            return {'z': (centre[0] + c, centre[1] + s, centre[2] + h), 'x': (centre[0] + h, centre[1] + c, centre[2] + s),
                    'y': (centre[0] + s, centre[1] + h, centre[2] + c)}[axis]
        tip = at(0.0, height); tip = {'z': (centre[0], centre[1], tip[2]), 'x': (tip[0], centre[1], centre[2]), 'y': (centre[0], tip[1], centre[2])}[axis]
        ends = {'z': (0, 0, 1), 'x': (1, 0, 0), 'y': (0, 1, 0)}[axis]  # a closed end's picture runs across it whole, a grating's holes in line
        lid = _frame([at(2 * math.pi * k / sides, height) for k in range(sides)], ends); foot = _frame([at(2 * math.pi * k / sides, 0) for k in range(sides)], ends)
        for index in range(sides):
            one, other = 2 * math.pi * index / sides, 2 * math.pi * (index + 1) / sides
            corners = [at(one, 0), at(other, 0), at(other, height), at(one, height)]
            outward = np.mean(corners, axis=0) - np.mean((centre, tip), axis=0)
            self.facing(corners, look, outward, smooth=smooth)
            if top:
                self.facing([at(one, height), at(other, height), tip], look, ends if height >= 0 else np.negative(ends), frame=lid)
            if bottom:
                self.facing([at(other, 0), at(one, 0), tuple(centre)], look, np.negative(ends) if height >= 0 else ends, frame=foot)

    def text(self, name, *, shadow=False):
        lines = [f'newmodel {name}', f'setsupermodel {name} null', 'classification TILE', f'beginmodelgeom {name}', f'node dummy {name}', '  parent null', 'endnode',
                 'node trimesh body', f'  parent {name}', '  position 0.0 0.0 0.0', '  orientation 0.0 0.0 0.0 0.0', '  ambient 1.0 1.0 1.0', '  diffuse 1.0 1.0 1.0',
                 '  specular 0.0 0.0 0.0', f'  bitmap {ATLAS}', '  render 1', f'  shadow {1 if shadow else 0}', '  tilefade 0', f'  verts {len(self.verts)}']
        lines += [f'    {x:.4f} {y:.4f} {z:.4f}' for x, y, z in self.verts] + [f'  tverts {len(self.tverts)}'] + [f'    {u:.5f} {v:.5f} 0' for u, v in self.tverts]
        lines += [f'  faces {len(self.faces)}'] + ['    ' + ' '.join(map(str, face)) for face in self.faces] + ['endnode', f'endmodelgeom {name}', f'donemodel {name}', '']
        return '\n'.join(lines)


def _frame(points, normal):
    """(kept axes, low corner, scale) projecting `points` onto the plane their normal leans to least, shrunk to fit a cell."""
    drop = max(range(3), key=lambda axis: abs(normal[axis])); keep = [axis for axis in range(3) if axis != drop]
    flat = [(point[keep[0]], point[keep[1]]) for point in points]
    low = [min(point[0] for point in flat), min(point[1] for point in flat)]; span = max(max(point[k] for point in flat) - low[k] for k in (0, 1))
    return keep, low, min(METRE, (1 - 2 * MARGIN) / max(span, 1e-6))


def _carried(vector, before, after):
    """`vector` turned as the direction `before` turns to `after`: a pipe's frame round a bend."""
    axis = np.cross(before, after); s = np.linalg.norm(axis); c = float(np.dot(before, after))
    if s < 1e-9:
        return vector
    k = axis / s
    return vector * c + np.cross(k, vector) * s + k * np.dot(k, vector) * (1 - c)


def turning(angle, axis, offset=(0.0, 0.0, 0.0)):
    """The move turning a point `angle` radians about the axis 'x', 'y' or 'z' through the origin, then by `offset`."""
    c, s = math.cos(angle), math.sin(angle)

    def move(point):
        x, y, z = point
        if axis == 'x':
            y, z = y * c - z * s, y * s + z * c
        elif axis == 'y':
            z, x = z * c - x * s, z * s + x * c
        else:
            x, y = x * c - y * s, x * s + y * c
        return (x + offset[0], y + offset[1], z + offset[2])
    return move


def ac_unit():  # a split air conditioner's outdoor unit on wall brackets: a fan behind a round guard, louvred sides, its pipes into the wall
    mesh = Mesh(); mesh.box((-0.38, 0.12, 0.0), (0.38, 0.62, 0.48), 'casing', bevel=0.02)
    mesh.cylinder((-0.1, 0.62, 0.24), 0.19, 0.012, 'grating', sides=16, axis='y')  # the fan guard, a little proud
    mesh.cylinder((-0.1, 0.632, 0.24), 0.04, 0.008, 'rubber', sides=8, axis='y')  # its hub
    mesh.box((0.16, 0.62, 0.06), (0.34, 0.625, 0.42), 'grille')  # the louvred panel beside it
    mesh.box((0.38, 0.18, 0.06), (0.385, 0.56, 0.42), 'grille'); mesh.box((-0.385, 0.18, 0.06), (-0.38, 0.56, 0.42), 'grille')
    for x in (-0.3, 0.3):  # L-brackets: an arm under the unit and a strut back up the wall
        mesh.box((x - 0.02, 0.0, -0.06), (x + 0.02, 0.62, -0.02), 'iron', skip=('-y',))
        strut = Mesh(); strut.box((-0.015, 0.0, -0.015), (0.015, 0.62, 0.015), 'iron')
        mesh.extend(strut, turning(math.atan2(0.34, 0.5), 'x', (x, 0.0, -0.4)))
        mesh.box((x - 0.03, 0.0, -0.44), (x + 0.03, 0.01, -0.36), 'iron', skip=('-y',))  # its foot plate
    mesh.tube(((0.3, 0.3, 0.12), (0.43, 0.3, 0.12), (0.43, 0.05, 0.12), (0.43, 0.0, 0.12)), 0.018, 'rubber', sides=6)  # insulated pipes
    mesh.tube(((0.3, 0.26, 0.2), (0.45, 0.26, 0.2), (0.45, 0.05, 0.2), (0.45, 0.0, 0.2)), 0.012, 'rubber', sides=6)
    return mesh, False


def downpipe():  # 3 m of rainwater pipe on ring clamps, a shoe at its foot, its foot at the origin
    mesh = Mesh(); mesh.tube(((0.0, 0.12, 0.25), (0.0, 0.12, 3.0)), 0.05, 'galvanised', sides=8)
    mesh.tube(((0.0, 0.12, 0.25), (0.0, 0.15, 0.05)), 0.05, 'galvanised', sides=8)  # the shoe throwing water off the wall
    for z in (0.4, 2.4):
        mesh.cylinder((0.0, 0.12, z), 0.058, 0.04, 'galvanised', sides=8, top=False, bottom=False)  # a clamp
        mesh.box((-0.012, 0.0, z + 0.005), (0.012, 0.07, z + 0.035), 'galvanised', skip=('-y',))  # its stem into the wall
    mesh.cylinder((0.0, 0.12, 1.5), 0.055, 0.06, 'galvanised', sides=8, top=False, bottom=False)  # a socket joint
    return mesh, False


STOREY = 4.8  # metres between the Slums' window rows


def fire_escape(stair=True):  # one storey: a grated platform at z = 0 on wall brackets, a railing of rails and pickets, a stair up to the next
    mesh = Mesh(); width, depth = 2.6, 1.1
    mesh.box((-width / 2 + 0.03, 0.0, -0.035), (width / 2 - 0.03, depth - 0.03, -0.005), 'grating', skip=('-y',))
    for y0, y1 in ((depth - 0.04, depth), ):  # the frame's angle iron along the front
        mesh.box((-width / 2, y0, -0.08), (width / 2, y1, 0.0), 'iron')
    for x in (-width / 2, width / 2):  # and its ends
        mesh.box((x - 0.02, 0.0, -0.08), (x + 0.02, depth, 0.0), 'iron', skip=('-y',))
        brace = Mesh(); brace.box((-0.015, 0.0, -0.015), (0.015, 1.15, 0.015), 'iron')  # a bracket strut from the wall below
        mesh.extend(brace, turning(math.atan2(0.75, 0.85), 'x', (x * 0.85, 0.0, -0.75)))
    for x in (-width / 2, width / 2):
        mesh.tube(((x, depth - 0.02, -0.06), (x, depth - 0.02, 1.0)), 0.022, 'iron', sides=6)  # posts
    mesh.tube(((-width / 2, 0.0, 1.0), (-width / 2, depth - 0.02, 1.0), (width / 2, depth - 0.02, 1.0), (width / 2, 0.0, 1.0)), 0.02, 'iron', sides=6)  # top rail
    mesh.tube(((-width / 2, depth - 0.02, 0.1), (width / 2, depth - 0.02, 0.1)), 0.012, 'iron', sides=6)  # the bottom rail the pickets stand on
    for x in np.linspace(-width / 2 + 0.13, width / 2 - 0.13, 11):
        mesh.box((x - 0.008, depth - 0.028, 0.1), (x + 0.008, depth - 0.012, 1.0), 'iron')
    if not stair:  # the top platform: nothing climbs past it into the cornice
        return mesh, False
    steps = 14; rise = STOREY / steps; run = (width - 0.4) / steps; foot, head = -width / 2 + 0.2, width / 2 - 0.2
    for step in range(steps):  # grated treads rising along the platform toward +x, under the next platform
        x = foot + step * run
        mesh.box((x, 0.17, rise * (step + 1) - 0.03), (x + run * 0.9, 0.73, rise * (step + 1)), 'grating')
    for y0, y1 in ((0.13, 0.17), (0.73, 0.77)):  # the two stringers the treads hang between
        mesh.beam((foot, -0.12), (head, STOREY - 0.12), y0, y1, 0.16, 'iron')
    mesh.tube(((foot, 0.765, 0.9), (head, 0.765, STOREY + 0.9)), 0.018, 'iron', sides=6)  # the handrail
    for x in (foot + 0.3, (foot + head) / 2, head - 0.3):  # its posts
        z = (x - foot) / (head - foot) * STOREY
        mesh.tube(((x, 0.765, z + 0.02), (x, 0.765, z + 0.9)), 0.014, 'iron', sides=6)
    return mesh, False


def boards():  # four rough planks of mixed widths nailed over a window, 1.1 by 1.5 m, standing a little off the wall
    mesh = Mesh()
    for z, width, tilt in ((0.06, 0.27, 0.035), (0.43, 0.22, -0.05), (0.76, 0.29, 0.02), (1.16, 0.25, -0.03)):
        plank = Mesh(); plank.box((-0.55, 0.0, -width / 2), (0.55, 0.024, width / 2), 'planks', skip=('-y',))
        for x in (-0.49, 0.49):  # two nails at each end
            for dz in (-width / 4, width / 4):
                plank.box((x - 0.007, 0.024, dz - 0.007), (x + 0.007, 0.027, dz + 0.007), 'iron', skip=('-y', '-x', '+x', '-z', '+z'))
        mesh.extend(plank, turning(tilt, 'y', (0.0, 0.004, z + width / 2)))
    return mesh, False


def bars():  # a welded security grille over a window, 1.1 by 1.5 m: a flat-bar frame, round bars, lugs into the wall
    mesh = Mesh()
    for z0, z1 in ((0.0, 0.04), (0.73, 0.77), (1.46, 1.5)):  # flat bars across
        mesh.box((-0.55, 0.02, z0), (0.55, 0.05, z1), 'iron', skip=('-y',))
    for x0, x1 in ((-0.55, -0.51), (0.51, 0.55)):  # and up its sides
        mesh.box((x0, 0.02, 0.0), (x1, 0.05, 1.5), 'iron', skip=('-y',))
    for x in np.linspace(-0.4, 0.4, 7):
        mesh.tube(((x, 0.035, 0.04), (x, 0.035, 1.46)), 0.011, 'iron', sides=6)
    for x in (-0.53, 0.53):  # lugs bolted into the wall
        for z in (0.2, 1.3):
            mesh.box((x - 0.02, 0.0, z - 0.03), (x + 0.02, 0.02, z + 0.03), 'iron', skip=('-y',))
    return mesh, False


def hvac():  # a packaged rooftop unit on a plinth: louvred coils along its sides, two fans on top behind guards: cover
    mesh = Mesh(); mesh.box((-0.9, -0.6, 0.0), (0.9, 0.6, 0.15), 'concrete', skip=('-z',), bevel=0.02)
    mesh.box((-0.8, -0.5, 0.15), (0.8, 0.5, 1.15), 'casing', skip=('-z',), bevel=0.025)
    for y0, y1 in ((-0.505, -0.5), (0.5, 0.505)):  # the coils behind louvres, both long sides
        mesh.box((-0.7, y0, 0.28), (0.7, y1, 1.0), 'grille')
    for x in (-0.35, 0.35):  # the fans: a shroud ring, its guard, a motor hub
        mesh.cylinder((x, 0.0, 1.15), 0.3, 0.08, 'casing', sides=16, top=False)
        mesh.cylinder((x, 0.0, 1.21), 0.28, 0.0, 'grating', sides=16)
        mesh.cylinder((x, 0.0, 1.21), 0.06, 0.03, 'rubber', sides=8)
    mesh.box((0.55, -0.51, 0.35), (0.75, -0.49, 0.6), 'casing', bevel=0.005)  # a service panel
    mesh.tube(((-0.82, 0.2, 0.75), (-0.86, 0.2, 0.75), (-0.86, 0.2, 0.15)), 0.025, 'galvanised', sides=6)  # its conduit down to the plinth
    return mesh, True


def junction_box():  # a broken electrical box on a wall, its torn cable hanging below: where sparks come from
    mesh = Mesh(); mesh.box((-0.18, 0.0, 0.0), (0.18, 0.13, 0.42), 'paint', skip=('-y',), bevel=0.012)
    mesh.box((-0.165, 0.12, 0.02), (0.165, 0.145, 0.4), 'paint', skip=('-y',), bevel=0.006)  # its door, a little proud
    for z in (0.08, 0.31):
        mesh.cylinder((-0.172, 0.135, z), 0.01, 0.05, 'iron', sides=6, bottom=True)  # hinges
    mesh.box((0.11, 0.145, 0.17), (0.13, 0.165, 0.25), 'iron', skip=('-y',), bevel=0.004)  # handle
    mesh.box((-0.07, 0.145, 0.27), (0.07, 0.148, 0.35), 'yellow', skip=('-y', '-x', '+x', '-z', '+z'))  # warning sticker
    mesh.cylinder((0.1, 0.065, 0.42), 0.03, 0.03, 'iron', sides=8)  # a gland, and the conduit up the wall from it
    mesh.tube(((0.1, 0.065, 0.45), (0.1, 0.065, 1.32)), 0.02, 'galvanised', sides=8)
    mesh.box((0.07, 0.0, 0.86), (0.13, 0.09, 0.89), 'galvanised', skip=('-y',))  # its saddle clip
    mesh.tube(((-0.06, 0.07, 0.0), (-0.055, 0.1, -0.12), (-0.08, 0.13, -0.24), (-0.05, 0.14, -0.34)), 0.016, 'rubber', sides=6, end=True)  # the torn cable
    return mesh, False


def vent():  # a mushroom roof vent on a flashing: cover for a crouching man
    mesh = Mesh(); mesh.box((-0.45, -0.45, 0.0), (0.45, 0.45, 0.08), 'galvanised', skip=('-z',), bevel=0.03)
    mesh.cylinder((0.0, 0.0, 0.08), 0.26, 0.5, 'galvanised', sides=14, top=False)
    mesh.cylinder((0.0, 0.0, 0.08), 0.29, 0.06, 'galvanised', sides=14, top=False)  # its collar on the flashing
    for x, y in ((-0.2, 0.0), (0.2, 0.0), (0.0, -0.2), (0.0, 0.2)):  # stays holding the cowl over the pipe
        mesh.box((x - 0.015, y - 0.015, 0.55), (x + 0.015, y + 0.015, 0.68), 'iron')
    mesh.cylinder((0.0, 0.0, 0.66), 0.42, 0.05, 'galvanised', sides=16, top=False, bottom=True)  # the cowl's rim
    for index in range(16):  # and its low cone
        one, other = 2 * math.pi * index / 16, 2 * math.pi * (index + 1) / 16
        mesh.triangle((math.cos(one) * 0.42, math.sin(one) * 0.42, 0.71), (math.cos(other) * 0.42, math.sin(other) * 0.42, 0.71), (0.0, 0.0, 0.86), 'galvanised', smooth=-1)
    return mesh, True


def tank():  # a riveted water tank on braced legs over a plinth: hoops, a low conical lid with a hatch, a ladder, an outlet
    mesh = Mesh(); mesh.box((-0.95, -0.95, 0.0), (0.95, 0.95, 0.2), 'concrete', skip=('-z',), bevel=0.03)
    legs = ((-0.6, -0.6), (0.6, -0.6), (0.6, 0.6), (-0.6, 0.6))
    for x, y in legs:
        mesh.box((x - 0.06, y - 0.06, 0.2), (x + 0.06, y + 0.06, 0.8), 'iron', skip=('-z',))
    for (xa, ya), (xb, yb) in zip(legs, legs[1:] + legs[:1]):  # cross braces between the legs
        mesh.tube(((xa, ya, 0.25), (xb, yb, 0.75)), 0.015, 'iron', sides=4)
    mesh.cylinder((0.0, 0.0, 0.8), 0.9, 1.6, 'rust', sides=20, top=False, bottom=True)
    for index in range(20):  # the low conical lid
        one, other = 2 * math.pi * index / 20, 2 * math.pi * (index + 1) / 20
        mesh.triangle((math.cos(one) * 0.9, math.sin(one) * 0.9, 2.4), (math.cos(other) * 0.9, math.sin(other) * 0.9, 2.4), (0.0, 0.0, 2.6), 'rust', smooth=-2)
    for z in (0.95, 1.6, 2.25):  # hoops round it
        mesh.cylinder((0.0, 0.0, z), 0.915, 0.05, 'iron', sides=20, top=False)
    mesh.box((0.15, -0.2, 2.45), (0.45, 0.1, 2.53), 'iron', bevel=0.01)  # the hatch
    ladder = Mesh()  # up the tank's side toward -x, -y
    for y in (-0.18, 0.18):
        ladder.tube(((0.0, y, 0.2), (0.0, y, 2.5)), 0.015, 'iron', sides=4)
    for z in np.arange(0.95, 2.45, 0.28):
        ladder.tube(((0.0, -0.18, z), (0.0, 0.18, z)), 0.01, 'iron', sides=4)
    mesh.extend(ladder, turning(math.radians(225), 'z', (math.cos(math.radians(225)) * 0.98, math.sin(math.radians(225)) * 0.98, 0.0)))
    mesh.tube(((0.3, 0.3, 0.8), (0.3, 0.3, 0.5), (0.6, 0.75, 0.5), (0.6, 0.75, 0.2)), 0.04, 'galvanised', sides=8)  # the outlet down to the plinth
    return mesh, True


def dish():  # a satellite dish on a weighted stand: a smooth bowl, its feed held out on three struts
    mesh = Mesh(); mesh.box((-0.45, -0.45, 0.0), (0.45, 0.45, 0.25), 'concrete', skip=('-z',), bevel=0.02)
    mesh.tube(((0.0, 0.0, 0.25), (0.0, 0.0, 1.25)), 0.04, 'galvanised', sides=8)
    axis = np.array((0.0, -0.6, 0.8)); u = np.array((1.0, 0.0, 0.0)); v = np.cross(axis, u)  # it looks up and toward -y
    middle = np.array((0.0, 0.0, 1.35)); rings, sides, rim = (0.0, 0.14, 0.28, 0.42, 0.55), 20, 0.55
    face, back = mesh.key(), mesh.key()

    def point(r, angle):  # on the bowl
        return tuple(middle + u * math.cos(angle) * r + v * math.sin(angle) * r + axis * 0.35 * (r / rim) ** 2)
    for inner, outer in zip(rings, rings[1:]):
        for index in range(sides):
            one, other = 2 * math.pi * index / sides, 2 * math.pi * (index + 1) / sides
            quad = [point(inner, one), point(outer, one), point(outer, other), point(inner, other)]
            mesh.facing(quad, 'paint', axis, smooth=face); mesh.facing(quad, 'paint', -axis, smooth=back)  # its dished face and its back
    mesh.box((-0.03, -0.03, 1.2), (0.03, 0.03, 1.38), 'galvanised')  # the bracket holding it on the pole
    tip = middle + axis * 0.55
    for angle in (0.0, 2.1, 4.2):  # three struts out to the feed
        mesh.tube((point(rim * 0.9, angle), tuple(tip)), 0.01, 'galvanised', sides=4)
    mesh.tube((tuple(tip - axis * 0.05), tuple(tip + axis * 0.07)), 0.035, 'rubber', sides=8, start=True, end=True)  # the feed
    return mesh, True


def antenna():  # a mast on a weighted foot, two aerials on it
    mesh = Mesh(); mesh.box((-0.3, -0.3, 0.0), (0.3, 0.3, 0.2), 'concrete', skip=('-z',), bevel=0.02)
    mesh.tube(((0.0, 0.0, 0.2), (0.0, 0.0, 3.4)), 0.03, 'galvanised', sides=6, end=True)
    for z, length in ((2.75, 1.1), (3.25, 0.8)):  # all above head height: only its foot is cover
        mesh.tube(((0.0, -length / 2, z), (0.0, length / 2, z)), 0.012, 'galvanised', sides=4)  # a boom
        for y in np.linspace(-length / 2 + 0.05, length / 2 - 0.05, 5):
            half = 0.28 - 0.04 * abs(y) / (length / 2) * 3
            mesh.tube(((-half, y, z), (half, y, z)), 0.006, 'galvanised', sides=4)  # its elements
        mesh.box((-0.035, -0.035, z - 0.04), (0.035, 0.035, z + 0.04), 'iron')  # the clamp
    return mesh, True


def canopy():  # a steel canopy over a door: a fascia lip, a lit strip under it, two tie rods up to wall plates
    mesh = Mesh(); mesh.box((-1.6, 0.0, 0.0), (1.6, 1.5, 0.1), 'steel', skip=('-y',), bevel=0.015)
    mesh.box((-1.6, 1.42, -0.06), (1.6, 1.5, 0.14), 'steel', bevel=0.01)  # the fascia
    mesh.box((-0.6, 0.6, -0.012), (0.6, 0.7, 0.0), 'white', skip=('+z',))  # the lit strip
    for x in (-1.4, 1.4):
        mesh.tube(((x, 1.38, 0.12), (x, 0.03, 1.3)), 0.014, 'iron', sides=6)
        mesh.box((x - 0.05, 0.0, 1.22), (x + 0.05, 0.03, 1.38), 'iron', skip=('-y',), bevel=0.005)  # its wall plate
    return mesh, False


def ledge():  # 2.5 m of a steel ledge along a facade, its nose rounded and a drip under it
    mesh = Mesh(); mesh.box((-1.25, 0.0, 0.0), (1.25, 0.45, 0.12), 'steel', skip=('-y',), bevel=0.02)
    mesh.box((-1.25, 0.4, -0.03), (1.25, 0.42, 0.0), 'steel', skip=('-y',))  # the drip
    return mesh, False


CAMERA_TILT, CAMERA_TURN = 20.0, 25.0  # degrees the camera's head looks down, and aside, from straight out of the wall
CAMERA_PIVOT = (0.0, 0.23, 0.03)  # where its head turns on the arm
# a piece whose head turns: the head's piece, the point on the piece it turns about, how far it sweeps each side of
# straight out (degrees) and how long one sweep there and back takes (seconds), in the tile's always-on animation (`detail`)
SWEEPS = {'camera': {'head': 'camera_head', 'pivot': CAMERA_PIVOT, 'sweep': 35.0, 'period': 24.0}}


def camera():  # a security camera's wall mount: a plate screwed to the wall, an arm, the swivel its head turns on
    mesh = Mesh(); mesh.box((-0.06, 0.0, -0.03), (0.06, 0.02, 0.15), 'paint', skip=('-y',), bevel=0.006)
    for x, z in ((-0.04, -0.01), (0.04, -0.01), (-0.04, 0.13), (0.04, 0.13)):
        mesh.box((x - 0.006, 0.02, z - 0.006), (x + 0.006, 0.024, z + 0.006), 'iron', skip=('-y', '-x', '+x', '-z', '+z'))  # screws
    mesh.tube(((0.0, 0.02, 0.09), (0.0, 0.19, 0.09), (0.0, 0.23, 0.06)), 0.018, 'paint', sides=8, end=True)  # the arm
    mesh.cylinder(CAMERA_PIVOT, 0.024, 0.035, 'iron', sides=8, bottom=True)  # the swivel
    return mesh, False


def camera_head():  # a camera's head, about its pivot: a hooded housing looking down CAMERA_TILT, a dark lens, its red light on
    head = Mesh()
    head.box((-0.06, -0.05, -0.13), (0.06, 0.22, -0.03), 'paint', bevel=0.018)  # housing
    head.box((-0.075, -0.07, -0.03), (0.075, 0.27, -0.012), 'paint', bevel=0.006)  # sun hood
    for x0, x1 in ((-0.075, -0.068), (0.068, 0.075)):
        head.box((x0, 0.12, -0.075), (x1, 0.27, -0.03), 'paint')  # its cheeks down beside the lens
    head.cylinder((0.0, 0.22, -0.08), 0.038, 0.012, 'rubber', sides=12, axis='y')  # the lens ring and glass
    head.cylinder((0.035, 0.22, -0.115), 0.006, 0.006, 'red', sides=6, axis='y')  # its light
    head.cylinder((0.0, 0.0, -0.03), 0.018, 0.03, 'iron', sides=8)  # the knuckle onto the swivel
    made = Mesh(); made.extend(head, turning(-math.radians(CAMERA_TILT), 'x')); return made, False


def camera_whole(turn=CAMERA_TURN):
    """The mount and its head together, the head turned `turn` degrees aside: what a still camera looks like."""
    mesh, _ = camera(); head, _ = camera_head(); mesh.extend(head, turning(math.radians(turn), 'z', CAMERA_PIVOT)); return mesh, False


def cross_sign():  # a lit hospital sign out from the wall on a bracket: a steel-framed light box, a red cross each side
    mesh = Mesh(); mesh.box((-0.07, 0.0, 0.55), (0.07, 0.015, 0.75), 'iron', skip=('-y',), bevel=0.004)  # its wall plate
    mesh.tube(((0.0, 0.015, 0.65), (0.0, 0.2, 0.65)), 0.022, 'iron', sides=6)  # and arm
    mesh.box((-0.06, 0.22, 0.02), (0.06, 0.98, 0.78), 'white')
    for y0, y1, z0, z1 in ((0.2, 1.0, 0.0, 0.03), (0.2, 1.0, 0.77, 0.8), (0.2, 0.23, 0.0, 0.8), (0.97, 1.0, 0.0, 0.8)):  # the frame
        mesh.box((-0.075, y0, z0), (0.075, y1, z1), 'steel')
    for side in (-1, 1):
        x0, x1 = sorted((side * 0.06, side * 0.065))
        mesh.box((x0, 0.52, 0.12), (x1, 0.68, 0.68), 'red'); mesh.box((x0, 0.32, 0.32), (x1, 0.88, 0.48), 'red')
    return mesh, False


def hazard_sign():  # a yellow warning plate on the wall: a rolled edge, three slanted black stripes, a bolt in each corner
    mesh = Mesh(); mesh.box((-0.45, 0.0, 0.0), (0.45, 0.02, 0.6), 'yellow', skip=('-y',), bevel=0.008)
    for left in (-0.38, -0.1, 0.18):  # parallelograms on the face, wound to face +y
        mesh.quad((left + 0.12, 0.021, 0.05), (left, 0.021, 0.05), (left + 0.15, 0.021, 0.55), (left + 0.27, 0.021, 0.55), 'rubber')
    for x, z in ((-0.42, 0.03), (0.42, 0.03), (-0.42, 0.57), (0.42, 0.57)):
        mesh.cylinder((x, 0.02, z), 0.009, 0.003, 'iron', sides=6, axis='y')
    return mesh, False


def barrel():  # a rusted oil drum burning: rolling hoops, a rolled rim, a heap of embers and charred wood in its top
    mesh = Mesh(); mesh.cylinder((0.0, 0.0, 0.0), 0.29, 0.88, 'rust', sides=16, top=False, bottom=True)
    for z in (0.28, 0.58):  # rolling hoops
        mesh.cylinder((0.0, 0.0, z), 0.3, 0.03, 'rust', sides=16, top=False)
    mesh.cylinder((0.0, 0.0, 0.86), 0.3, 0.03, 'rust', sides=16, top=False)  # the rolled rim
    for index in range(10):  # the ember heap, a low mound
        one, other = 2 * math.pi * index / 10, 2 * math.pi * (index + 1) / 10
        mesh.triangle((math.cos(one) * 0.28, math.sin(one) * 0.28, 0.76), (math.cos(other) * 0.28, math.sin(other) * 0.28, 0.76), (0.03, -0.02, 0.84), 'ember')
    for angle, lean in ((0.4, 0.5), (2.3, -0.4), (4.2, 0.3)):  # charred sticks across it
        mesh.tube(((math.cos(angle) * 0.25, math.sin(angle) * 0.25, 0.78), (-math.cos(angle + lean) * 0.2, -math.sin(angle + lean) * 0.2, 0.9)), 0.022, 'rubber', sides=5, start=True, end=True)
    return mesh, True


def mast():  # a tall antenna mast on a weighted foot, crossarms with whips, a red warning light on top
    mesh = Mesh(); mesh.box((-0.4, -0.4, 0.0), (0.4, 0.4, 0.3), 'concrete', skip=('-z',), bevel=0.02)
    mesh.tube(((0.0, 0.0, 0.3), (0.0, 0.0, 7.8)), 0.08, 'steel', sides=8)
    for z, half in ((4.5, 0.9), (5.6, 0.7), (6.6, 0.5)):
        mesh.tube(((-half, 0.0, z), (half, 0.0, z)), 0.02, 'steel', sides=4); mesh.tube(((0.0, -half, z), (0.0, half, z)), 0.02, 'steel', sides=4)
        for x, y in ((-half, 0.0), (half, 0.0), (0.0, -half), (0.0, half)):
            mesh.tube(((x, y, z), (x, y, z + 0.5)), 0.01, 'steel', sides=4)  # a whip
    mesh.cylinder((0.0, 0.0, 7.8), 0.07, 0.05, 'iron', sides=8)
    mesh.cylinder((0.0, 0.0, 7.85), 0.06, 0.12, 'red', sides=8)  # the light
    return mesh, True


PIECES = {'ac_unit': ac_unit, 'downpipe': downpipe, 'fire_escape': fire_escape, 'fire_escape_top': lambda: fire_escape(stair=False), 'boards': boards, 'bars': bars,
          'hvac': hvac, 'junction_box': junction_box, 'vent': vent, 'tank': tank, 'dish': dish, 'antenna': antenna,
          'canopy': canopy, 'ledge': ledge, 'camera': camera, 'camera_head': camera_head, 'mast': mast, 'cross_sign': cross_sign, 'hazard_sign': hazard_sign, 'barrel': barrel}


def make(folder, masters, crunch, *, compress=None):
    """Write every piece (<piece>.mdl) and the atlas (its material and maps) into `folder`. Returns {piece: faces}."""
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True); told = {}
    for name, build in PIECES.items():
        mesh, blocks = build(); require(mesh.faces, f'{name} has no faces')
        (folder / f'{name}.mdl').write_text(mesh.text(name, shadow=blocks), encoding='ascii', newline='\n'); told[name] = len(mesh.faces)
    material.write(ATLAS, atlas(masters), folder / 'atlas', crunch, compress=compress)
    return told
