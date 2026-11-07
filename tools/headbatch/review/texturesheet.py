"""texturesheet.py HEAD STAGE ATTEMPT OUT.png: labeled diagnostic atlas/mask contact sheet; no approval."""
import sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from headbatch.head_files import read, sha

def projected_iris_pixels(alpha, circles):
    """Count strong rendered atlas samples per eye so a unilateral parser dropout is visible."""
    xs = np.arange(alpha.shape[1]) + .5
    right_x = circles['R'][0][0]
    left_x = circles['L'][0][0]
    nearest_right = np.abs(xs-right_x) <= np.abs(xs-left_x)
    strong = alpha >= .5
    return {'R': int(strong[:, nearest_right].sum()), 'L': int(strong[:, ~nearest_right].sum())}


def iris_counts(receipt):
    from headkit.common import verify
    from headkit.face_masks import sample
    from headkit.gltf import mesh
    result = receipt.get('result', {})
    files = result.get('files', {})
    if not all(key in files for key in ('iris', 'frontView')) or 'iris' not in result:
        return None
    source, atlas, camera = result['source'], files['iris'], files['frontView']
    verify([source, atlas, camera], fresh=True)
    with np.load(camera['path'], allow_pickle=False) as view, Image.open(atlas['path']) as image:
        # Reproject exact texture bytes. Sampling only needs hit, barycentrics and face indices.
        data = {key: view[key] for key in ('hit', 'bary', 'face')}
        pixels = sample(data, np.asarray(image.convert('L'))[..., None], mesh(source['path'])['uv'])
    return projected_iris_pixels(pixels[:, :, 0]/255, result['iris'])


def eye_pair(overlay, landmarks):
    import numpy as np
    # Both halves of review-masks share the baked front camera.
    pts = np.load(landmarks, allow_pickle=False)
    corners = pts[[33, 263]]
    span = abs(corners[1, 0] - corners[0, 0])
    if span < 1 or not np.isfinite(corners).all():
        raise ValueError('Degenerate eye landmarks')
    with Image.open(overlay) as image:
        width = image.width // 2
        left = max(0, int(min(corners[:, 0]) - .17 * span))
        right = min(width, int(max(corners[:, 0]) + .17 * span) + 1)
        top = max(0, int(min(corners[:, 1]) - .38 * span))
        bottom = min(image.height, int(max(corners[:, 1]) + .19 * span) + 1)
        pair = Image.new('RGB', (2 * (right-left), bottom-top))
        for n in range(2):
            offset = n * width
            pair.paste(image.crop((left+offset, top, right+offset, bottom)), (n*(right-left), 0))
    return pair


def tone_eye_pair(receipt):
    from headkit.common import verify
    from headkit.face_masks import sample
    from headkit.gltf import mesh
    dep = receipt.get('dependencies', {}).get('masks')
    if dep is None:
        return None
    verify([dep], fresh=True)
    result = read(dep['path'])['result']
    files = result['files']
    tone = receipt['result']['output']
    verify([result['source'], tone, files['frontView'], files['frontRender'], files['frontLandmarks']], fresh=True)
    pts = np.load(files['frontLandmarks']['path'], allow_pickle=False)[[33,263],:2]
    span = float(np.ptp(pts[:,0]))
    with Image.open(files['frontRender']['path']) as bake:
        left,top = np.floor(pts.min(0)-[.17*span,.30*span]).astype(int).clip(0)
        right,bottom = np.minimum(bake.size,np.ceil(pts.max(0)+[.17*span,.19*span]).astype(int)+1)
        box = (left,top,right,bottom)
        original = bake.crop(box).convert('RGB')
    crop = np.s_[top:bottom,left:right]
    with np.load(files['frontView']['path'], allow_pickle=False) as saved:
        view = {key:saved[key][crop] for key in ('hit','face','bary')}
    with Image.open(tone['path']) as image:
        rgb = np.asarray(image.convert('RGB'))
        rendered = sample(view,rgb,mesh(result['source']['path'])['uv']).clip(0,255).astype(np.uint8)
    pair = Image.new('RGB',(original.width*2,original.height))
    pair.paste(original,(0,0))
    pair.paste(Image.fromarray(rendered),(original.width,0))
    return pair


def draw(head, stage, attempt, output):
    if stage not in ('paint','masks','tone') or not attempt.startswith('attempt-') or Path(attempt).name!=attempt:
        raise ValueError('Explicit paint/masks/tone attempt required')
    folder=Path(head)/'run'/stage/attempt
    receipt=read(folder/'receipt.json')
    if receipt.get('state')!='complete':raise ValueError('Complete attempt required')
    rows=[]
    for row in receipt.get('outputs',[]):
        path=Path(row['path'])
        if path.suffix.lower()=='.png' and path.is_relative_to(folder.resolve()):
            if sha(path)!=row['sha256']:raise ValueError('Attempt image changed: '+str(path))
            rows.append((path,row))
    if not rows:raise ValueError('No pinned attempt images')
    columns=min(3,len(rows));size=512;label=44
    eyes = None
    if stage == 'masks':
        overlay = next((path for path, _ in rows if path.name == 'review-masks.png'), None)
        if overlay is not None:
            landmarks = overlay.with_name('front-landmarks.npy')
            source = next((r for r in receipt['outputs'] if Path(r['path']) == landmarks), None)
            if source is None or sha(landmarks) != source['sha256']:
                raise ValueError('Missing or changed eye landmarks')
            eyes = eye_pair(overlay, landmarks)
            eyes.thumbnail((columns*size, size), Image.Resampling.LANCZOS)
    if stage == 'tone':
        eyes = tone_eye_pair(receipt)
        if eyes is not None:
            eyes.thumbnail((columns*size,size),Image.Resampling.LANCZOS)
    header = label + eyes.height if eyes is not None else 0
    sheet=Image.new('RGB',(columns*size,((len(rows)+columns-1)//columns)*(size+label)+header),(30,30,30))
    pen=ImageDraw.Draw(sheet)
    if eyes is not None:
        legend = 'baked eyes | tone sampled on mesh' if stage == 'tone' else 'baked eyes | projected eyes (blue brow, green opening, magenta iris)'
        pen.text((6, 8), f'{Path(head).name} {stage} {attempt}: {legend}', fill='white')
        counts = iris_counts(receipt) if stage == 'masks' else None
        if counts is not None:
            missing = [side for side, count in counts.items() if count == 0]
            note = 'Missing projected iris: '+', '.join(missing) if missing else 'Inspect both projected irises'
            pen.text((6, 24), f"{note} (subject R {counts['R']} px, L {counts['L']} px)", fill='orange' if missing else 'white')
        sheet.paste(eyes, (0, label))
    for i,(path,_) in enumerate(rows):
        x=i%columns*size;y=header+i//columns*(size+label)
        with Image.open(path) as source:
            dimensions=source.size
            image=source.convert('RGB');image.thumbnail((size,size),Image.Resampling.NEAREST if stage=='masks' else Image.Resampling.BOX)
            sheet.paste(image,(x,y+label))
        pen.text((x+6,y+4),f'{Path(head).name} {stage} {attempt}',fill='white')
        pen.text((x+6,y+20),f'{path.name} {dimensions} | diagnostic thumbnail',fill='white')
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    if output.exists():raise ValueError('Sheet already exists')
    sheet.save(output)
    return output

if __name__=='__main__':print(draw(*sys.argv[1:]))
