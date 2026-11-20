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
    'casing': ('MetalPlates013', (178, 174, 160), None, None),
    'grille': (None, (46, 48, 50), 0.6, 0.6),
    'rust': ('Rust009', None, None, None),
    'corrugated': ('CorrugatedSteel009', (140, 142, 138), None, None),
    'planks': ('Planks023A', (120, 98, 72), None, None),
    'galvanised': ('MetalPlates013', (128, 132, 134), None, None),
    'paint': ('MetalPlates013', (214, 214, 206), 0.45, 0.1),
    'rubber': (None, (24, 24, 26), 0.85, 0.0),
    'iron': ('MetalPlates013', (44, 42, 40), None, None),
    'concrete': ('Concrete034', (122, 120, 116), None, None),
}
ORDER = list(LOOKS)


def cell_of(look):
    index = ORDER.index(look); return index % CELLS, index // CELLS


def atlas(masters):
    """{colour, normal, roughness, metal} of the kit's atlas, `SIZE` square."""
    side = SIZE // CELLS; colour = np.zeros((SIZE, SIZE, 3), np.uint8); normal = np.zeros((SIZE, SIZE, 3), np.uint8)
    roughness = np.zeros((SIZE, SIZE)); metal = np.zeros((SIZE, SIZE))
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
            if look == 'grille':  # slats across: a dark gap every 24 pixels, lit tops
                rows = np.arange(side) % 24; made['colour'][rows < 6] = (18, 18, 20)
                made['normal'][rows == 6] = (128, 200, 220); made['normal'][rows == 23] = (128, 56, 220)
        if rough is not None:
            made['roughness'] = np.full((side, side), rough)
        if metallic is not None:
            made['metal'] = np.full((side, side), metallic)
        colour[box], normal[box], roughness[box], metal[box] = made['colour'], made['normal'], made['roughness'], made['metal']
    return {'colour': colour, 'normal': normal, 'roughness': roughness, 'metal': metal}


class Mesh:
    """Vertices, texture vertices and faces of one piece, faces textured from their atlas cell."""

    def __init__(self):
        self.verts, self.tverts, self.faces = [], [], []

    def triangle(self, a, b, c, look):
        """A face a→b→c (counter-clockwise seen from its front), its picture projected from its own plane."""
        u = [b[axis] - a[axis] for axis in range(3)]; v = [c[axis] - a[axis] for axis in range(3)]
        normal = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        if math.hypot(*normal) < 1e-12:
            return
        drop = max(range(3), key=lambda axis: abs(normal[axis])); keep = [axis for axis in range(3) if axis != drop]
        flat = [(point[keep[0]], point[keep[1]]) for point in (a, b, c)]
        low = [min(point[0] for point in flat), min(point[1] for point in flat)]; span = max(max(point[k] for point in flat) - low[k] for k in (0, 1))
        scale = min(METRE, (1 - 2 * MARGIN) / max(span, 1e-6)); column, row = cell_of(look)
        base = len(self.verts); tbase = len(self.tverts)
        self.verts += [a, b, c]
        for x, y in flat:  # a texture vertex's v runs up the picture: rows from the bottom
            self.tverts.append(((column + MARGIN + (x - low[0]) * scale) / CELLS, 1 - (row + MARGIN + (y - low[1]) * scale) / CELLS))
        self.faces.append((base, base + 1, base + 2, 1, tbase, tbase + 1, tbase + 2, 1))

    def quad(self, a, b, c, d, look):
        self.triangle(a, b, c, look); self.triangle(a, c, d, look)

    def box(self, low, high, look, *, front=None, skip=()):
        """An axis-aligned box from `low` to `high`; `front` the look of its +y face; `skip` the faces left off
        ('-y' against a wall, '-z' on a roof)."""
        (x0, y0, z0), (x1, y1, z1) = low, high
        sides = {'+x': ((x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)), '-x': ((x0, y1, z0), (x0, y0, z0), (x0, y0, z1), (x0, y1, z1)),
                 '+y': ((x1, y1, z0), (x0, y1, z0), (x0, y1, z1), (x1, y1, z1)), '-y': ((x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)),
                 '+z': ((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)), '-z': ((x0, y1, z0), (x1, y1, z0), (x1, y0, z0), (x0, y0, z0))}
        for name, corners in sides.items():
            if name not in skip:
                self.quad(*corners, front if name == '+y' and front else look)

    def cylinder(self, centre, radius, height, look, *, sides=10, top=True, bottom=False, axis='z'):
        """A cylinder up from `centre` (along `axis`, 'z' or 'x'); `bottom` closes its foot, which a shadow caster
        held off the ground needs: an open end lets the engine's shadow volume through and darkens the near wall."""
        def at(angle, h):
            c, s = math.cos(angle) * radius, math.sin(angle) * radius
            return (centre[0] + c, centre[1] + s, centre[2] + h) if axis == 'z' else (centre[0] + h, centre[1] + c, centre[2] + s)
        for index in range(sides):
            one, other = 2 * math.pi * index / sides, 2 * math.pi * (index + 1) / sides
            self.quad(at(one, 0), at(other, 0), at(other, height), at(one, height), look)
            if top:
                tip = (centre[0], centre[1], centre[2] + height) if axis == 'z' else (centre[0] + height, centre[1], centre[2])
                self.triangle(at(one, height), at(other, height), tip, look)
            if bottom:
                self.triangle(at(other, 0), at(one, 0), tuple(centre), look)

    def text(self, name, *, shadow=False):
        lines = [f'newmodel {name}', f'setsupermodel {name} null', 'classification TILE', f'beginmodelgeom {name}', f'node dummy {name}', '  parent null', 'endnode',
                 'node trimesh body', f'  parent {name}', '  position 0.0 0.0 0.0', '  orientation 0.0 0.0 0.0 0.0', '  ambient 1.0 1.0 1.0', '  diffuse 1.0 1.0 1.0',
                 '  specular 0.0 0.0 0.0', f'  bitmap {ATLAS}', '  render 1', f'  shadow {1 if shadow else 0}', '  tilefade 0', f'  verts {len(self.verts)}']
        lines += [f'    {x:.4f} {y:.4f} {z:.4f}' for x, y, z in self.verts] + [f'  tverts {len(self.tverts)}'] + [f'    {u:.5f} {v:.5f} 0' for u, v in self.tverts]
        lines += [f'  faces {len(self.faces)}'] + ['    ' + ' '.join(map(str, face)) for face in self.faces] + ['endnode', f'endmodelgeom {name}', f'donemodel {name}', '']
        return '\n'.join(lines)


def ac_unit():
    mesh = Mesh(); mesh.box((-0.38, 0.12, 0.0), (0.38, 0.62, 0.48), 'casing', front='grille', skip=('-y',))  # on a bracket off the wall
    for x in (-0.3, 0.3):
        mesh.box((x - 0.02, 0.0, -0.08), (x + 0.02, 0.62, -0.04), 'iron', skip=('-y',))
    mesh.cylinder((0.2, 0.06, 0.1), 0.02, 0.3, 'rubber', sides=6, top=False)  # its pipe into the wall
    return mesh, False


def downpipe():  # 3 m of pipe on brackets, its foot at the origin
    mesh = Mesh(); mesh.cylinder((0.0, 0.12, 0.0), 0.055, 3.0, 'galvanised', top=False)
    for z in (0.4, 2.4):
        mesh.box((-0.07, 0.0, z), (0.07, 0.07, z + 0.05), 'galvanised', skip=('-y',))
    return mesh, False


STOREY = 4.8  # metres between the Slums' window rows


def fire_escape(stair=True):  # one storey: a grated platform at z = 0 with railing, and a stair up to the next, a storey above
    mesh = Mesh(); width, depth = 2.6, 1.1
    mesh.box((-width / 2, 0.0, -0.06), (width / 2, depth, 0.0), 'iron', skip=('-y',))
    for x in (-width / 2, width / 2):
        mesh.box((x - 0.025, depth - 0.05, -0.06), (x + 0.025, depth, 1.0), 'iron')
    mesh.box((-width / 2, depth - 0.04, 0.95), (width / 2, depth, 1.0), 'iron')  # top rail
    mesh.box((-width / 2, depth - 0.03, 0.45), (width / 2, depth, 0.48), 'iron')  # mid rail
    for x in (-width / 2, width / 2):
        mesh.box((x - 0.02, 0.0, 0.95), (x + 0.02, depth, 1.0), 'iron', skip=('-y',))  # end rails back to the wall
    if not stair:  # the top platform: nothing climbs past it into the cornice
        return mesh, False
    steps = 14; rise = STOREY / steps; run = (width - 0.4) / steps
    for step in range(steps):  # a stair rising along the platform toward +x, under the next platform
        x = -width / 2 + 0.2 + step * run
        mesh.box((x, 0.15, rise * (step + 1) - 0.03), (x + run, 0.75, rise * (step + 1)), 'iron')
    mesh.quad((-width / 2 + 0.2, 0.76, 0.0), (width / 2 - 0.2, 0.76, STOREY), (width / 2 - 0.2, 0.78, STOREY), (-width / 2 + 0.2, 0.78, 0.0), 'iron')  # stringer
    return mesh, False


def boards():  # three planks over a window, 1.1 by 1.5 m, flush to the wall
    mesh = Mesh()
    for index, (z, tilt) in enumerate(((0.15, 0.04), (0.65, -0.03), (1.15, 0.02))):
        mesh.quad((-0.55, 0.03, z - tilt), (0.55, 0.03, z + tilt), (0.55, 0.03, z + 0.28 + tilt), (-0.55, 0.03, z + 0.28 - tilt), 'planks')
        mesh.quad((-0.55, 0.0, z - tilt), (-0.55, 0.03, z - tilt), (-0.55, 0.03, z + 0.28 - tilt), (-0.55, 0.0, z + 0.28 - tilt), 'planks')
    return mesh, False


def bars():  # a grille over a window, 1.1 by 1.5 m
    mesh = Mesh()
    for x in np.linspace(-0.5, 0.5, 9):
        mesh.box((x - 0.012, 0.02, 0.0), (x + 0.012, 0.05, 1.5), 'iron', skip=('-y',))
    for z in (0.05, 0.75, 1.45):
        mesh.box((-0.55, 0.02, z - 0.02), (0.55, 0.06, z + 0.02), 'iron', skip=('-y',))
    return mesh, False


def hvac():  # roof plant on a plinth: cover
    mesh = Mesh(); mesh.box((-0.9, -0.6, 0.0), (0.9, 0.6, 0.15), 'concrete', skip=('-z',))
    mesh.box((-0.8, -0.5, 0.15), (0.8, 0.5, 1.15), 'casing', skip=('-z',))
    mesh.box((-0.7, -0.51, 0.3), (0.7, -0.5, 1.0), 'grille')
    mesh.cylinder((0.35, 0.0, 1.15), 0.3, 0.06, 'grille', sides=12); mesh.cylinder((-0.35, 0.0, 1.15), 0.3, 0.06, 'grille', sides=12)
    return mesh, True


def junction_box():  # a broken electrical box on a wall, its torn cable hanging below: where sparks come from
    mesh = Mesh(); mesh.box((-0.18, 0.0, 0.0), (0.18, 0.14, 0.42), 'paint', skip=('-y',))
    mesh.cylinder((0.1, 0.07, 0.42), 0.02, 0.9, 'galvanised', sides=6, top=False)  # its conduit up the wall
    mesh.cylinder((-0.06, 0.08, -0.32), 0.012, 0.32, 'rubber', sides=5, top=False)  # the torn cable
    return mesh, False


def vent():  # a roof vent: cover for a crouching man
    mesh = Mesh(); mesh.box((-0.35, -0.35, 0.0), (0.35, 0.35, 0.6), 'galvanised', skip=('-z',))
    mesh.box((-0.45, -0.45, 0.6), (0.45, 0.45, 0.7), 'galvanised', skip=())
    return mesh, True


def tank():  # a water tank on legs over a plinth
    mesh = Mesh(); mesh.box((-0.95, -0.95, 0.0), (0.95, 0.95, 0.2), 'concrete', skip=('-z',))
    for x, y in ((-0.6, -0.6), (0.6, -0.6), (0.6, 0.6), (-0.6, 0.6)):
        mesh.box((x - 0.06, y - 0.06, 0.2), (x + 0.06, y + 0.06, 0.8), 'iron', skip=('-z',))
    mesh.cylinder((0.0, 0.0, 0.8), 0.9, 1.6, 'rust', sides=14, bottom=True)
    return mesh, True


def dish():  # a satellite dish on a weighted stand
    mesh = Mesh(); mesh.box((-0.45, -0.45, 0.0), (0.45, 0.45, 0.25), 'concrete', skip=('-z',))
    mesh.cylinder((0.0, 0.0, 0.25), 0.04, 1.0, 'galvanised', sides=6, top=False)
    centre = (0.0, 0.1, 1.25); rim, deep, sides = 0.55, 0.18, 14
    for index in range(sides):  # a shallow cone facing up and toward -y
        one, other = 2 * math.pi * index / sides, 2 * math.pi * (index + 1) / sides
        at = lambda angle: (centre[0] + math.cos(angle) * rim, centre[1] - 0.25 + math.sin(angle) * rim * 0.6, centre[2] + 0.25 + math.sin(angle) * rim * 0.8)
        mesh.triangle(at(other), at(one), centre, 'paint'); mesh.triangle(at(one), at(other), (centre[0], centre[1] + deep, centre[2] - 0.05), 'paint')
    return mesh, True


def antenna():  # a mast with crossbars, on a weighted foot
    mesh = Mesh(); mesh.box((-0.3, -0.3, 0.0), (0.3, 0.3, 0.2), 'concrete', skip=('-z',))
    mesh.cylinder((0.0, 0.0, 0.2), 0.035, 3.3, 'galvanised', sides=6)
    for z, half in ((2.7, 0.6), (3.0, 0.45), (3.3, 0.3)):  # all above head height: only its foot is cover
        mesh.box((-half, -0.015, z), (half, 0.015, z + 0.03), 'galvanised')
    return mesh, True


PIECES = {'ac_unit': ac_unit, 'downpipe': downpipe, 'fire_escape': fire_escape, 'fire_escape_top': lambda: fire_escape(stair=False), 'boards': boards, 'bars': bars,
          'hvac': hvac, 'junction_box': junction_box, 'vent': vent, 'tank': tank, 'dish': dish, 'antenna': antenna}


def make(folder, masters, crunch, *, compress=None):
    """Write every piece (<piece>.mdl) and the atlas (its material and maps) into `folder`. Returns {piece: faces}."""
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True); told = {}
    for name, build in PIECES.items():
        mesh, blocks = build(); require(mesh.faces, f'{name} has no faces')
        (folder / f'{name}.mdl').write_text(mesh.text(name, shadow=blocks), encoding='ascii', newline='\n'); told[name] = len(mesh.faces)
    material.write(ATLAS, atlas(masters), folder / 'atlas', crunch, compress=compress)
    return told
