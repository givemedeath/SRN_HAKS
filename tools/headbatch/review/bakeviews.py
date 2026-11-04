"""bakeviews.py HEAD_DIR [ATTEMPT]: bake review evidence in one call, for the named bake or the newest complete one: fit-matrix-ATTEMPT.json,
four textured views (bake-tex-ATTEMPT.png, 2K basecolor on the unwrap mesh that bake consumed) and the bbox-relative iso-line grid used to write ownership rules
(bake-grid-ATTEMPT.png). Sheets for two attempts can run at once, so nothing here is shared between attempts."""
import json, subprocess, sys
from pathlib import Path
from headbatch.head_files import complete, consumed, fit_matrix

head = sys.argv[1]; evidence = Path(head)/'review-evidence'; evidence.mkdir(exist_ok=True); here = Path(__file__).parent
bake = Path(head)/'run'/'bake'/sys.argv[2] if len(sys.argv) > 2 else complete(head, 'bake')
if bake is None: sys.exit('No complete bake attempt')
unwrap = consumed(head, bake, 'unwrap')
if unwrap is None: sys.exit(f'{bake.name} of bake consumed no unwrap stage')
uv = str(unwrap/'uv.glb'); texture = str(bake/'maps'/'basecolor-2048.png')
matrix = evidence/f'fit-matrix-{bake.name}.json'; matrix.write_text(json.dumps(fit_matrix(head)))
jobs = [[sys.executable, '-B', str(here/'clay.py'), str(evidence/f'bake-tex-{bake.name}.png'), f'bake={uv}', '--matrix', str(matrix), '--tex', texture, '--lit', '.35', '--views', 'front,left,back,right', '--size', '450'],
        [sys.executable, '-B', str(here/'grid.py'), uv, str(matrix), texture, str(evidence/f'bake-grid-{bake.name}.png')]]
running = [subprocess.Popen(job, stdout=subprocess.DEVNULL) for job in jobs]
sys.exit(max(process.wait() for process in running))
