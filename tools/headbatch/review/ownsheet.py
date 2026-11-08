"""ownsheet.py HEAD_DIR ATTEMPT OUT.png: review sheet of one finished ownership attempt: its saved atlas on the UV mesh it consumed,
under the painted colour when present, otherwise the bake it consumed. Prints the channel texel counts. own_draft previews rules alone; this shows what palette
and export actually read, face-mask channels included."""
import sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageOps
from headkit.gltf import mesh
from headkit.paint import PREVIEW
from headkit.preview import splat, sheet
from headbatch.head_files import consumed

head, attempt, out = Path(sys.argv[1]), sys.argv[2], sys.argv[3]; folder = head/'run'/'ownership'/attempt
unwrap, bake = consumed(head, folder, 'unwrap'), consumed(head, folder, 'bake')
if unwrap is None: sys.exit(f'{attempt} of ownership consumed no unwrap stage')
labels = np.asarray(Image.open(folder/'ownership-4096.png'))
layers = [PREVIEW[labels]]
colour = consumed(head,folder,'paint') or bake
if colour is not None:
    layers.insert(0,np.asarray(Image.open(colour/'maps'/'basecolor-4096.png').convert('RGB')))
channels = {int(key): int(count) for key, count in zip(*np.unique(labels, return_counts=True))}
board = sheet(splat(mesh(str(unwrap/'uv.glb')), layers, size=400, samples=2500000), len(layers),
              f'{head.name} {attempt}: saved ownership {channels}', 400)
masks = consumed(head, folder, 'masks')
if masks:
    # At full-head scale the tips of tusks and the boundary of a beard can be only a few pixels wide.
    import json
    from headkit.face_masks import nearest
    from headkit.quality import LIP_POLYGON, focus_view
    mask = json.loads((masks/'receipt.json').read_text(encoding='utf8'))['result']
    with Image.open(folder/'ownership-1024.png') as saved:
        runtime = np.asarray(saved)
    view = focus_view(mask['source']['path'], mask, runtime)
    mouth = view['pts'][list(LIP_POLYGON), :2]
    width = max(float(np.ptp(mouth[:, 0])), 4)
    x, y = (mouth.max(0) + mouth.min(0)) / 2
    box = (max(0,int(x-.85*width)), max(0,int(y-.65*width)),
           min(view['render'].shape[1],int(x+.85*width)), min(view['render'].shape[0],int(y+.4*width)))
    ids = nearest(view['view'], runtime, view['uv'])
    shown = PREVIEW[ids].copy()
    shown[ids < 0] = (64,64,64)
    combined = Image.new('RGB', (board.width, board.height+184), '#202020')
    combined.paste(board)
    draw = ImageDraw.Draw(combined)
    for index,(name, pixels) in enumerate((('Baked mouth',view['render']), ('Runtime channels',shown))):
        crop = Image.fromarray(pixels).crop(box)
        tile = ImageOps.contain(crop, (380,155), method=Image.Resampling.NEAREST)
        left = index*400
        combined.paste(tile,(left,board.height+22))
        draw.text((left+5,board.height+4),name,fill='white')
    board = combined
board.save(out)
print(head.name, attempt, channels)
