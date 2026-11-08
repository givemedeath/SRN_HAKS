"""Hash-bound external reference intake. A record is evidence, never a visual approval."""
from pathlib import Path
import guards
from head_files import sha
FEATURES = ('face','ears','brows','horns','tusks','hair','beard','cyberware','piercings','tattoo','scars')

def load(path, head, design=None):
    path = Path(path).resolve()
    data = guards.read(path)
    if data.get('kind') != 'headbatch-reference-v1' or data.get('head') != head:
        raise guards.Refused('External reference record must name this head')
    for key in ('generator', 'prompt'):
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise guards.Refused('External reference record needs '+key)
    features = data.get('features', {})
    if not isinstance(features, dict) or any(not isinstance(features.get(k), str) or not features[k].strip() for k in FEATURES):
        raise guards.Refused('Explicit feature inventory required, including absent features, counts and anatomical sides')
    def pinned(row):
        if not isinstance(row, dict) or not isinstance(row.get('path'), str):
            raise guards.Refused('Reference image needs path and sha256')
        image = (path.parent/row['path']).resolve()
        if not image.is_file() or sha(image) != row.get('sha256'):
            raise guards.Refused('Reference image missing or changed: '+str(image))
        return image
    selected = pinned(data.get('design'))
    if design is not None and selected != Path(design).resolve():
        raise guards.Refused('Selected design differs from external reference record')
    pair = data.get('conditioning')
    paths = {}
    if pair is not None:
        if not isinstance(pair, dict) or set(pair) != {'clay','detail','alignment'}:
            raise guards.Refused('Conditioning needs clay, detail and measured alignment')
        paths = {k:pinned(pair[k]) for k in ('clay','detail')}
        if sha(paths['clay']) == sha(paths['detail']):
            raise guards.Refused('Paired conditioning must not collapse clay and detail to the same image')
        if not isinstance(pair['alignment'], dict) or len(pair['alignment'].get('landmarks', [])) < 3:
            raise guards.Refused('Conditioning needs at least three measured paired landmarks')
    return data, paths

def check(path, head, output):
    """Read-only intake plus numerical pair check; outputs remain pending visual review."""
    from headkit.images import prepare
    from head_files import write_json
    data, paths = load(path, head)
    output = Path(output)
    if output.exists():
        raise guards.Refused('Reference check output must be fresh')
    output.mkdir(parents=True)
    result = {'referenceRecord':{'path':str(Path(path).resolve()),'sha256':sha(path)},
              'head':head,'visualReviewRequired':True,'approved':False,
              'visualChecks': [
                  'Open eyes and matching clay/detail identity, framing and anatomy.',
                  'No anatomical neck; preserve the complete chin and jaw.',
                  'Long hair: coherent rear volume behind the jaw and side locks, covering the rear skull. '
                  'Do not require empty background between side curtains when rear hair belongs there. '
                  'Inspect native alpha; silhouette IoU alone cannot approve rear volume.']}
    if paths:
        result['pair'] = prepare(paths['clay'], paths['detail'], data['conditioning']['alignment'], output/'pair')
    else:
        result['conditioning'] = 'bootstrap only; no clay/detail pair supplied'
    write_json(output/'reference-check.json', result)
    return result
