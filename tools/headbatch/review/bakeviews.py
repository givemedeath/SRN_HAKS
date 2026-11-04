"""bakeviews.py HEAD_DIR: bake review evidence in one call: fit-matrix.json, four textured views (bake-tex.png, 2K basecolor on the
unwrap mesh) and the bbox-relative iso-line grid used to write ownership rules (bake-grid.png)."""
import glob, json, subprocess, sys
from pathlib import Path

head = sys.argv[1]; evidence = Path(head)/'review-evidence'; evidence.mkdir(exist_ok=True); here = Path(__file__).parent
uv = sorted(glob.glob(f'{head}/run/unwrap/attempt-*/uv.glb'))[-1]; texture = sorted(glob.glob(f'{head}/run/bake/attempt-*/maps/basecolor-2048.png'))[-1]
fit = json.load(open(head+'/manifest.json'))['fit']  # the reviewed explicit matrix first (RUNBOOK 100)
matrix = fit['matrix'] if 'matrix' in fit else json.load(open(json.load(open(head+'/run/state.json'))['stages']['fit']['path']))['result']['matrix']
(evidence/'fit-matrix.json').write_text(json.dumps(matrix))
jobs = [[sys.executable, '-B', str(here/'clay.py'), str(evidence/'bake-tex.png'), f'bake={uv}', '--matrix', str(evidence/'fit-matrix.json'), '--tex', texture, '--lit', '.35', '--views', 'front,left,back,right', '--size', '450'],
        [sys.executable, '-B', str(here/'grid.py'), uv, str(evidence/'fit-matrix.json'), texture, str(evidence/'bake-grid.png')]]
running = [subprocess.Popen(job, stdout=subprocess.DEVNULL) for job in jobs]
sys.exit(max(process.wait() for process in running))
