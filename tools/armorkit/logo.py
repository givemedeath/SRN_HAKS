"""The shared logo: one strip texture of every logo, one material, one small vertex shader.

A part that shows a logo carries a badge mesh naming the material `MATERIAL` (docs/armorkit/plan.md, revision
"logos use the shader value"; proof in docs/armorkit/spikes.md, section 18). The material reads the strip
`STRIP`, and its parameter `PARAMETER` picks the cell: SR_NWN sets it on the wearing creature with
`SetMaterialShaderUniformVec4(creature, MATERIAL, PARAMETER, cell)`. Cell 0 is blank and is what an unset
creature shows.

The cells' pictures are `logos/<name>.png`, 128 texels square. Ares, Renraku, Saeder-Krupp, Wuxing and Mitsuhama
are cut from the corporate security concept sheet, Aztechnology and Lone Star from the battle armour and magical
response sheets (user, 2026-11-17: the major corporations' logos are in the concept sheets). Evo, Horizon, NeoNET
and Shiawase are on no sheet: they are cut from one image drawn in the sheets' header style (user, 2026-11-17:
the rest of the major corporations' logos). Adding a logo replaces the strip; no part changes, and a cell once
given keeps its number, since SR_NWN stores it.
"""
from pathlib import Path

import numpy as np
from PIL import Image

from . import texture
from .registry import require

MATERIAL, SHADER, STRIP, PARAMETER = 'srn_logo', 'srn_vslogo', 'srn_logos', 'LogoCell'
FILES = (MATERIAL + '.mtr', SHADER + '.shd', STRIP + '.tga')  # what `write` writes: one set serves every part with a badge
CELL = 128  # texels a side of one logo
CELLS = (None, 'ares', 'renraku', 'saeder-krupp', 'wuxing', 'mitsuhama', 'aztechnology', 'evo', 'horizon', 'neonet', 'shiawase',
         'lone-star', None, None, None, None)  # the strip, cell by cell; None is blank
BLANK = (0.09, 0.09, 0.1)
PICTURES = Path(__file__).resolve().parent / 'logos'
MATERIAL_TEXT = f'customshaderVS {SHADER}\ncustomshaderFS fslit\ntexture0 {STRIP}\nparameter float {PARAMETER} 0.0\n'
# the stock `vslit` with one line more, which moves the badge's 0-1 texture coordinate into the chosen cell
SHADER_TEXT = ('#define SHADER_TYPE 1\n#define FOG 1\n#define KEYHOLING 1\n#define NORMAL_MAP 0\n#define ENVIRONMENT_MAP 0\n#define LIGHTING 1\n'
               '#include "inc_standard"\n' + f'uniform float {PARAMETER};\n' + 'void main ()\n{\n    ApplyStandardShader();\n'
               + f'    vVertexTexCoords.x = (vVertexTexCoords.x + {PARAMETER}) / {len(CELLS)}.0;\n' + '}\n')


def cells():
    """{logo name: cell} of the strip, for the handoff."""
    return {name: index for index, name in enumerate(CELLS) if name is not None}


def record():
    """What a part with a badge records of the logo, and the handoff hands on: the material, its parameter, the strip and the cells."""
    return {'material': MATERIAL, 'parameter': PARAMETER, 'strip': STRIP, 'cells': cells()}


def strip(pictures=PICTURES):
    """The strip as 0-1 RGB rows running down from the picture's top: every cell side by side, cell 0 first."""
    row = np.empty((CELL, CELL * len(CELLS), 3))
    row[:] = BLANK
    for index, name in enumerate(CELLS):
        if name is not None:
            picture = Image.open(Path(pictures) / (name + '.png')).convert('RGB')
            require(picture.size == (CELL, CELL), f'{name}: a logo is {CELL} texels square')
            row[:, index * CELL:(index + 1) * CELL] = np.asarray(picture, float) / 255
    return row


def write(folder, pictures=PICTURES):
    """Write the material, the shader and the strip into `folder`: the names written."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / (MATERIAL + '.mtr')).write_text(MATERIAL_TEXT, encoding='ascii', newline='\n')
    (folder / (SHADER + '.shd')).write_text(SHADER_TEXT, encoding='ascii', newline='\n')
    # `texture.tga` takes rows from v = 0, the picture's bottom: a badge's v runs up its picture
    (folder / (STRIP + '.tga')).write_bytes(texture.tga(strip(pictures)[::-1]))
    return list(FILES)


def reads_right(vertices, faces, uvs, outward, up):
    """Why a badge would not read the right way round, as a list of reasons; empty when it does.

    `vertices`, `faces` and `uvs` are the badge's, `outward` the way it faces (away from the wearer) and `up`
    the way its picture's top points. Seen from outside, every face must face the viewer, u must run to the
    viewer's right and v up the picture: a badge mapped mirrored showed a reversed letter through two proofs
    before it was noticed (docs/armorkit/spikes.md, section 18), which a symmetric test logo would never show."""
    vertices, faces, uvs = np.asarray(vertices, float), np.asarray(faces, int), np.asarray(uvs, float)
    outward, up = (np.asarray(way, float) / np.linalg.norm(way) for way in (outward, up))
    right = np.cross(-outward, up)  # the viewer looks along -outward
    reasons = []
    a, b, c = (vertices[faces[:, k]] for k in range(3))
    normal = np.cross(b - a, c - a)
    if (normal @ outward <= 0).any():
        reasons.append(f'{int((normal @ outward <= 0).sum())} faces turned away from the viewer')
    ua, ub, uc = (uvs[faces[:, k]] for k in range(3))
    # per face, the way u and v grow over the surface
    e1, e2, d1, d2 = b - a, c - a, ub - ua, uc - ua
    den = d1[:, 0] * d2[:, 1] - d2[:, 0] * d1[:, 1]
    if (np.abs(den) < 1e-12).any():
        return reasons + ['a face with no area in the texture']
    along_u = (e1 * d2[:, 1:2] - e2 * d1[:, 1:2]) / den[:, None]
    along_v = (e2 * d1[:, 0:1] - e1 * d2[:, 0:1]) / den[:, None]
    if (along_u @ right <= 0).any():
        reasons.append('u runs to the viewer\'s left: the logo is mirrored')
    if (along_v @ up <= 0).any():
        reasons.append('v runs down the picture: the logo is upside down')
    if uvs.min() < -1e-6 or uvs.max() > 1 + 1e-6:
        reasons.append('texture coordinates outside 0-1: the badge would read into the next cell')
    return reasons
