"""Read-only topology of explicitly named fresh retexture receipt outputs."""
import argparse
import gc
import hashlib
import json
import sys
from pathlib import Path

P = Path(__file__).resolve().parent
R = P.parents[2]
sys.path.insert(0, str(R / 'tools/phenotypes'))
from inspect_generated_part_topology import inspect
from place_purposebuilt_pelvis import require


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while block := stream.read(4 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


parser = argparse.ArgumentParser()
parser.add_argument('--generation', type=Path, required=True)
parser.add_argument('--master', action='append', required=True,
    help='Actual output basename, including the server assigned counter')
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
generation = args.generation.resolve()
job = json.loads(generation.read_text())
require(job.get('state') == 'success' and job.get('promptId'), 'Collected success receipt required')
out = args.output.resolve()
require(out.parent == P.resolve() and not out.exists(), 'Fresh owned output directory required')
sources = []
for name in args.master:
    require(Path(name).name == name and name.endswith('.glb'), 'Explicit actual GLB basenames required')
    rows = [row for row in job['outputs'] if Path(row['localPath']).name == name]
    require(len(rows) == 1, 'Exact unique receipt association required for ' + name)
    source = Path(rows[0]['localPath']).resolve()
    require(sha(source) == rows[0]['sha256'], 'Collected master changed')
    sources.append((source, rows[0]['sha256']))
require(len({source for source, _ in sources}) == len(sources), 'Duplicate master names rejected')
before = sha(generation)
out.mkdir()
reports = []
for source, digest in sources:
    print(json.dumps({'started': source.name}), flush=True)
    result = inspect(source, ray_samples=[], vertical_samples=[])
    result.update(readOnly=True, sourceGeometryChanged=False, generation=str(generation),
        generationSha256=before, jobPromptId=job['promptId'])
    path = out / (source.name + '.json')
    path.write_text(json.dumps(result, indent=2) + '\n')
    row = {'source': str(source), 'sourceSha256': digest, 'report': str(path), 'reportSha256': sha(path),
        'faces': result['triangleCount'], 'components': result['componentCountByExactCoordinateEdges'],
        'boundary': result['boundaryEdgeCount'], 'nonmanifold': result['nonmanifoldEdgeCount'],
        'badWinding': result['inconsistentWindingManifoldEdgeCount'], 'signedVolume': result['signedVolume'],
        'aabbVolumeFraction': result['volumeFractionOfAxisAlignedBox']}
    reports.append(row)
    require(sha(source) == digest, 'Read-only source changed')
    print(json.dumps(row), flush=True)
    del result
    gc.collect()
require(sha(generation) == before, 'Receipt changed during audit')
(out / 'index.json').write_text(json.dumps({'schemaVersion': 1, 'readOnly': True,
    'generation': str(generation), 'generationSha256': before, 'jobPromptId': job['promptId'],
    'reports': reports, 'helpers': {str(Path(__file__)): sha(__file__),
        str(R / 'tools/phenotypes/inspect_generated_part_topology.py'):
        sha(R / 'tools/phenotypes/inspect_generated_part_topology.py')},
    'scope': 'Explicit actual fresh retexture outputs only; no adoption or topology modifications.'}, indent=2) + '\n')
