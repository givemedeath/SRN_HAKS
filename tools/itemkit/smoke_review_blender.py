"""Small CPU render integration smoke; no generated weapon inputs or GPU."""
import sys
from pathlib import Path
import bpy
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.headkit.common import pin, read, write, require
from tools.itemkit import blender_worker as worker
from tools.itemkit.review import render_variants
from tools.itemkit.parts import FIREARM_VIEWS


def main():
    out = Path(sys.argv[sys.argv.index('--')+1]).resolve(); out.mkdir(parents=True, exist_ok=False)
    worker.reset(); bpy.ops.mesh.primitive_cube_add(size=.1)
    obj = bpy.context.object; obj.name = 'item_b'
    bpy.context.scene.world = bpy.data.worlds.new('smoke-world')
    scene = out/'source.blend'; bpy.ops.wm.save_as_mainfile(filepath=str(scene))
    textures = {}
    for name, colour in [('base', (1,0,0,1)), ('alternate', (0,0,1,1))]:
        image = bpy.data.images.new(name, width=8, height=8)
        image.generated_color = colour; image.filepath_raw = str(out/(name+'.png')); image.file_format = 'PNG'; image.save()
        textures[name] = image.filepath_raw
    views = {name: {'direction': [1,.2,.3], 'target': [0,0,0], 'up': [0,1,0], 'scale': 1.1} for name in FIREARM_VIEWS}
    cfg = {'scene': str(scene), 'family': {'family':'firearm-sling', 'firearm': {'subtype':'pistol'},
           'native': {'iconDimensions': {'b':[32,64]}}}, 'render': {'firearmViews':views}}
    # The production renderer stays fixed at 1024/16. Only this synthetic smoke
    # reduces pixel work, exercising real scene setup, materials, cameras and IO.
    original = worker.render_still; calls = []
    def small_render():
        scene = bpy.context.scene; scene.cycles.samples = 1
        scene.render.resolution_x = scene.render.resolution_y = 32
        calls.append(scene.render.filepath)
        return original()
    worker.render_still = small_render
    try:
        report = render_variants(cfg, textures, out/'batch')
    finally:
        worker.render_still = original
    first = read(report['variants']['base']['path']); second = read(report['variants']['alternate']['path'])
    require(len(calls) == 42, 'Expected 24+16 views plus two icons')
    require(len(first['frames']) == len(second['frames']) == 24, 'Missing review frames')
    require(first['cameras'] == second['cameras'], 'Finish cameras differ')
    require(second['reusedClayFrames'] == 8, 'Clay not reused')
    for name in FIREARM_VIEWS:
        require(pin(out/'batch/base'/('clay-'+name+'.png'))['sha256'] == pin(out/'batch/alternate'/('clay-'+name+'.png'))['sha256'], 'Clay differs')
    require(pin(out/'batch/base/unlit-left.png')['sha256'] != pin(out/'batch/alternate/unlit-left.png')['sha256'], 'Finish texture was incorrectly reused')
    write(out/'smoke.json', {'passed':True,'renderCalls':len(calls),'independentRenderCalls':50,
          'savedRenderCalls':8,'seconds':report['elapsedSeconds'],'threads':4,'gpuUsed':False},fresh=True)


if __name__ == '__main__': main()
