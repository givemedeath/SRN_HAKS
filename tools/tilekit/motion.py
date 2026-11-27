"""Screens that move (user, 2026-11-25: all the display screens animated if possible).

A flipbook (`proceduretype cycle`) plays a whole picture from an uncompressed TGA, so a screen that is a corner of a
device's picture would cost the device's picture once a frame: 12 MB for sixteen frames of 512 pixels, in a pack 350 MB
from the game's limit. So the still pictures stay and a shader moves what is on them: a material of the picture's own
name (the game takes `<bitmap>.mtr` before the bitmap) names `srn_screen_fs` and says where the screens are and what
moves. Every placeable and every tile that draws the picture then moves, with no model changed. A material that has an
illumination map (envkit) keeps its lines and takes `srn_screenp_fs`, which moves the blue and green light of the map.

The list is docs/placeables/screen-motion.json. A picture that is a flipbook already is refused."""
import json
from pathlib import Path

from . import require

SPEC, SCREENS, PACK, GLOWING = 'docs/placeables/screen-motion.json', 'docs/placeables/screens.json', 'srn_placeable', 'srn_envprop'
MOST = 4  # screens on one picture
MARK = '// screens move: tools/tilekit/motion.py'
SPEEDS = (1.0, 0.83, 1.19, 0.91)  # no two neighbours in step


def started(name, number):
    """Where in its run a screen starts, in seconds: a name's own, so no row of monitors is in step."""
    return sum(ord(letter) * (place + 3) for place, letter in enumerate(name)) % 61 + 7.3 * number


def parts(spec, screens):
    """{texture: [(box, kind)]} of the list and of the screens laid by `screens`."""
    found = {}
    for name, how in screens['textures'].items():
        made = [(part['box'], spec['contents'].get(part['picture'])) for part in how['screen'] if 'picture' in part]
        require(all(kind for _, kind in made), f'{name}: {SPEC} does not say what moves on each of its pictures')
        if made:
            found[name] = made
    for name, made in spec['textures'].items():
        require(name not in found, f'{name} is in {SCREENS}: its boxes are there'); found[name] = [(part['box'], part['kind']) for part in made]
    for name, made in found.items():
        require(len(made) <= MOST, f'{name}: at most {MOST} screens move on one picture')
        for box, kind in made:
            require(kind in spec['kinds'], f'{name}: what moves is one of ' + ', '.join(spec['kinds'])); require(len(box) == 4 and 0 <= box[0] < box[2] <= 1 and 0 <= box[1] < box[3] <= 1, f'{name}: a box is [left, top, right, bottom] in shares of the picture')
    return found


def material(name, made, spec):
    """A plain picture's material. The shader counts up from the picture's foot."""
    lines = [MARK, 'customshaderVS vslit', 'customshaderFS srn_screen_fs', f'texture0 {name}']
    for number, (box, kind) in enumerate(made):
        lines += [f'parameter float ScreenBox{number} {box[0]:.4f} {1 - box[3]:.4f} {box[2]:.4f} {1 - box[1]:.4f}',
                  f'parameter float ScreenHow{number} {spec["kinds"].index(kind) + 1:.1f} {SPEEDS[(len(name) + number) % len(SPEEDS)]:.2f} {started(name, number):.1f} {spec["glow"]:.2f}']
    return '\n'.join(lines) + '\n'


def glowing(name, text):
    """An envkit material's text with the moving light's shader."""
    lines = [line for line in text.replace('\r\n', '\n').rstrip('\n').split('\n') if not line.startswith((MARK, 'customshader', 'parameter float Screen'))]
    require(any(line.split()[:1] == ['texture5'] and line.split()[1].lower() != 'null' for line in lines), f'{name} has no illumination map')
    return '\n'.join(lines + [MARK, 'customshaderVS vslit_sm_nm', 'customshaderFS srn_screenp_fs', f'parameter float ScreenHow0 1.0 {SPEEDS[len(name) % len(SPEEDS)]:.2f} {started(name, 0):.1f} 1.0']) + '\n'


def files(repo):
    """{path in the repository: text} of every material of the list."""
    repo = Path(repo); spec, screens = (json.loads((repo / path).read_text(encoding='utf-8')) for path in (SPEC, SCREENS)); made = {}
    for name, screen in parts(spec, screens).items():
        folder = next((pack for pack in (PACK, 'srn_t_udp2', 'srn_t_udp1') if any((repo / pack / f'{name}{end}').is_file() for end in ('.dds', '.tga'))), None)
        require(folder, f'{name}: no pack holds the picture'); txi = repo / folder / f'{name}.txi'
        require(not txi.is_file() or 'cycle' not in txi.read_text(encoding='ascii').lower(), f'{name} is a flipbook: it moves already')
        path = repo / folder / f'{name}.mtr'
        require(not path.is_file() or path.read_text(encoding='ascii').startswith(MARK), f'{path.name} is a material of its own already')
        made[f'{folder}/{name}.mtr'] = material(name, screen, spec)
    for name in spec['glowing']:
        path = repo / GLOWING / f'{name}.mtr'; require(path.is_file(), f'{GLOWING} has no material {name}'); made[f'{GLOWING}/{name}.mtr'] = glowing(name, path.read_text(encoding='ascii'))
    return made


def build(repo):
    made = files(repo)
    for path, text in made.items():
        (Path(repo) / path).write_text(text, encoding='ascii', newline='\n')
    return len(made)
