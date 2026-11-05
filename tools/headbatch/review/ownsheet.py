"""ownsheet.py HEAD_DIR ATTEMPT OUT.png: review sheet of one finished ownership attempt: its saved atlas on the UV mesh it consumed,
under the bake colour when it consumed one. Prints the channel texel counts. own_draft previews rules alone; this shows what palette
and export actually read, face-mask channels included."""
import sys
from pathlib import Path
import numpy as np
from PIL import Image
from headkit.gltf import mesh
from headkit.paint import PREVIEW
from headkit.preview import splat, sheet
from headbatch.head_files import consumed

head, attempt, out = Path(sys.argv[1]), sys.argv[2], sys.argv[3]; folder = head/'run'/'ownership'/attempt
unwrap, bake = consumed(head, folder, 'unwrap'), consumed(head, folder, 'bake')
if unwrap is None: sys.exit(f'{attempt} of ownership consumed no unwrap stage')
labels = np.asarray(Image.open(folder/'ownership-4096.png'))
layers = [PREVIEW[labels]]
if bake is not None: layers.insert(0, np.asarray(Image.open(bake/'maps'/'basecolor-4096.png').convert('RGB')))
channels = {int(key): int(count) for key, count in zip(*np.unique(labels, return_counts=True))}
sheet(splat(mesh(str(unwrap/'uv.glb')), layers, size=400, samples=2500000), len(layers), f'{head.name} {attempt}: saved ownership {channels}', 400).save(out)
print(head.name, attempt, channels)
