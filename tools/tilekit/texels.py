"""How finely the rooms draw their pictures, and which are too coarse.

A room's furniture comes from many hands, some of it with a 64-pixel picture stretched over a bunk. `measure` gives,
for every picture the built rooms draw, the pixels it has to a metre (the median by drawn area) and the area it
covers; `weak` picks the ones to redraw or enlarge (user, 2026-11-25: any low-quality texture met is upscaled or
redrawn): a small picture drawn coarsely, or a very small one, over more than a scrap of the room and not one plain
colour. `docs/placeables/materials.json` says what was made anew; its `left` says, with the reason, which are kept."""
import collections
from pathlib import Path

import numpy as np

from . import geometry, pictures, roomlights

SMALL, TINY = 512, 128  # pixels of the longer side: above the first a picture is not weak, at the second it always is
COARSE = 170  # pixels a metre: eye level in a room shows fewer as blur
SCRAP = 2.0  # square metres drawn over all rooms
PLAIN = 4.0  # mean spread of the channels under which a picture is one colour


def size(path):
    """(width, height) of a TGA, a DDS or a BioWare DDS."""
    with open(path, 'rb') as file:
        head = file.read(20)
    if path.suffix.lower() == '.tga':
        return int.from_bytes(head[12:14], 'little'), int.from_bytes(head[14:16], 'little')
    return (int.from_bytes(head[16:20], 'little'), int.from_bytes(head[12:16], 'little')) if head[:4] == b'DDS ' else (int.from_bytes(head[0:4], 'little'), int.from_bytes(head[4:8], 'little'))


def held(repo):
    """{name: picture file} of the packs; a DDS is drawn before a TGA."""
    found = {}
    for pack in sorted(Path(repo).glob('srn_*')):
        for path in sorted(pack.iterdir()):
            if path.suffix.lower() in ('.dds', '.tga') and path.stem.lower() not in found:
                found[path.stem.lower()] = path
    return found


def measure(models, sizes):
    """{picture: {density, area, models}} of `models` ({name: ASCII text, or a compiled model's nodes as `rooms.pieces_of` reads
    them}); sizes: {picture: (width, height)}, and only those are measured."""
    drawn, where = collections.defaultdict(list), collections.defaultdict(set)
    for name, text in models.items():
        nodes = geometry.parse(text)[2] if isinstance(text, str) else text
        lit = {(getattr(node, 'name', '') or '').lower() for node in nodes}
        for node in nodes:
            picture = (node.material or '').lower()[:16]
            called = (getattr(node, 'name', '') or '').lower()
            if called.endswith(roomlights.SUFFIX) and called[:-len(roomlights.SUFFIX)] in lit:
                continue  # a switched light's unlit copy: drawn in place of its lit mesh, never beside it
            if not node.rendered or picture not in sizes or not node.tverts:
                continue
            points = np.array(node.verts, float); over = np.array([one[:2] for one in node.tverts], float) * sizes[picture]
            corners = np.array([one[:3] for one in node.faces]); laid = np.array([one[4:7] for one in node.faces])
            areas = np.linalg.norm(np.cross(points[corners[:, 1]] - points[corners[:, 0]], points[corners[:, 2]] - points[corners[:, 0]]), axis=1) / 2
            first, second = over[laid[:, 1]] - over[laid[:, 0]], over[laid[:, 2]] - over[laid[:, 0]]
            pixels = np.abs(first[:, 0] * second[:, 1] - first[:, 1] * second[:, 0]) / 2; real = areas > 1e-6
            drawn[picture].append((np.sqrt(pixels[real] / areas[real]), areas[real])); where[picture].add(name)
    out = {}
    for picture, parts in drawn.items():
        density, area = (np.concatenate(column) for column in zip(*parts))
        if not len(area):
            continue
        order = np.argsort(density); total = np.cumsum(area[order])
        out[picture] = {'density': float(density[order][np.searchsorted(total, total[-1] / 2)]), 'area': float(total[-1]), 'models': sorted(where[picture])}
    return out


def plain(path):
    """Is the picture one colour?"""
    from PIL import Image
    if path.suffix.lower() == '.tga':
        with Image.open(path) as opened:
            shown = np.asarray(opened.convert('RGB'), float)
    else:
        shown = np.asarray(pictures.read(path), float)[..., :3]
    return float(shown.std(axis=(0, 1)).mean()) <= PLAIN


def weak(measured, sizes, files):
    """The pictures of `measured` that are too coarse, coarsest first."""
    def coarse(name):
        one, longer = measured[name], max(sizes[name])
        return longer <= SMALL and one['area'] > SCRAP and (one['density'] < COARSE or longer <= TINY) and not plain(files[name])
    return sorted((name for name in measured if coarse(name)), key=lambda name: measured[name]['density'])


def of_rooms(repo, pattern='srx02_*f_*.mdl'):
    """(measured, sizes, files) of the built furnished rooms."""
    files = held(repo); sizes = {name: size(path) for name, path in files.items()}
    return measure({path.stem: path.read_text(encoding='cp1252') for path in sorted((Path(repo) / 'sources' / 'srn_t_srx02').glob(pattern))}, sizes), sizes, files
