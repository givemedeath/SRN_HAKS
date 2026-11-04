"""bakeviews.py HEAD_DIR [ATTEMPT]: bake review evidence in one call, for the named bake or the newest complete one: fit-matrix.json,
four textured views (bake-tex.png, 2K basecolor on the unwrap mesh that bake consumed) and the bbox-relative iso-line grid used to write ownership rules (bake-grid.png)."""
import json, subprocess, sys
from pathlib import Path
from headbatch.head_files import complete, consumed, fit_matrix

head = sys.argv[1]; evidence = Path(head)/'review-evidence'; evidence.mkdir(exist_ok=True); here = Path(__file__).parent
bake = Path(head)/'run'/'bake'/sys.argv[2] if len(sys.argv) > 2 else complete(head, 'bake')
if bake is None: sys.exit('No complete bake attempt')
unwrap = consumed(head, bake, 'unwrap')
if unwrap is None: sys.exit(f'{bake.name} of bake consumed no unwrap stage')
uv = str(unwrap/'uv.glb'); texture = str(bake/'maps'/'basecolor-2048.png')
(evidence/'fit-matrix.json').write_text(json.dumps(fit_matrix(head)))
jobs = [[sys.executable, '-B', str(here/'clay.py'), str(evidence/'bake-tex.png'), f'bake={uv}', '--matrix', str(evidence/'fit-matrix.json'), '--tex', texture, '--lit', '.35', '--views', 'front,left,back,right', '--size', '450'],
        [sys.executable, '-B', str(here/'grid.py'), uv, str(evidence/'fit-matrix.json'), texture, str(evidence/'bake-grid.png')]]
running = [subprocess.Popen(job, stdout=subprocess.DEVNULL) for job in jobs]
sys.exit(max(process.wait() for process in running))
