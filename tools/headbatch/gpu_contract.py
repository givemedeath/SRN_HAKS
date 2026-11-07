"""Calibration/shape lineage and exact-submission visual gates. No implicit approvals."""
from pathlib import Path
import re
from headkit.common import digest, pin, read, require, verify, write
from head_files import write_json

ORDER=('calibrate','geometry','appearance')

def calibration_evidence(head, attempt):
    """Show both normalized images and their independent FOVs from one retained prompt."""
    from PIL import Image, ImageDraw
    require(re.fullmatch(r'calibrate(?:-[0-9]+)?', attempt), 'Explicit calibration attempt required')
    folder = Path(head)/'gpu'/attempt
    target = folder/'camera-review.json'
    if target.exists():
        report = read(target)
        verify(report['inputs'] + [report['sheet']], fresh=True)
        return report
    history = read(folder/'history.json')
    require(history['status'].get('completed') and history['status'].get('status_str') == 'success',
            'Completed calibration prompt required')
    require(history['prompt'][2] == read(folder/'prompt.json'), 'Calibration graph differs from history')
    inputs = [pin(folder/'history.json'), pin(folder/'prompt.json')]
    canvas = Image.new('RGB', (1024, 552), (32, 32, 32))
    pen = ImageDraw.Draw(canvas)
    fov = {}
    for i, (role, image_node, camera_node) in enumerate((('geometry','12','16'), ('detail','13','10'))):
        images = history['outputs'][image_node]['images']
        require(len(images) == 1, 'Expected one normalized image per role')
        name = images[0]['filename']
        require(Path(name).name == name, 'Expected a calibration image filename')
        path = folder/f'node-{image_node}-{name}'
        inputs.append(pin(path))
        fov[role] = float(history['outputs'][camera_node]['text'][0])
        with Image.open(path) as image:
            image.thumbnail((512,512))
            canvas.paste(image.convert('RGB'), (512*i+(512-image.width)//2, 40))
        pen.text((512*i+10, 12), f'{role}  {fov[role]:.2f} degrees  |  {attempt}', fill='white')
    verify(inputs, fresh=True)
    sheet = folder/'camera-sheet.png'
    canvas.save(sheet)
    report = {'attempt': attempt, 'promptId': history['prompt'][1], 'fov': fov,
              'inputs': inputs, 'sheet': pin(sheet)}
    write(target, report, fresh=True)
    return report


def camera_review_pins(head, attempt):
    require(re.fullmatch(r'calibrate(?:-[0-9]+)?', attempt), 'Explicit calibration attempt required')
    folder = Path(head)/'gpu'/attempt
    evidence = pin(folder/'camera-review.json')
    report = read(evidence['path'])
    require(report['attempt'] == attempt and Path(report['sheet']['path']) == folder/'camera-sheet.png',
            'Camera sheet does not belong to the requested attempt')
    pins = [evidence, report['sheet'], *report['inputs']]
    verify(pins, fresh=True)
    return pins


def checked_detail_camera(head, attempt, approval, graph, files, fov):
    from PIL import Image, ImageChops
    require(approval.strip(), 'The reviewer must supply camera approval words')
    pins = camera_review_pins(head, attempt)
    evidence = read(pins[0]['path'])
    folder = Path(head)/'gpu'/attempt
    history = read(folder/'history.json')
    require(pin(folder/'history.json') in evidence['inputs'] and pin(folder/'prompt.json') in evidence['inputs']
            and 25 <= evidence['fov']['detail'] <= 70 and 25 <= fov['detail'] <= 70 and history['prompt'][2] == graph
            and history['prompt'][1] == evidence['promptId'], 'Reviewed camera graph or detail angle changed')
    for role, node, estimate in [('geometry', '12', '16'), ('detail', '13', '10')]:
        value = float(history['outputs'][estimate]['text'][0])
        require(evidence['fov'][role] == value and abs(fov[role] - value) < .001,
                'Camera measurements differ from the reviewed attempt')
        name = history['outputs'][node]['images'][0]['filename']
        prior = folder/f'node-{node}-{name}'
        require(pin(prior) in evidence['inputs'], 'Reviewed crop is missing from the evidence')
        actual = next(item for key, item in files.items() if key.startswith(node+':'))
        with Image.open(prior) as original, Image.open(actual['path']) as current:
            require(original.size == current.size and ImageChops.difference(
                    original.convert('RGB'), current.convert('RGB')).getbbox() is None,
                    'Normalized calibration pixels differ from the reviewed crop')
    return {'attempts': {Path(head).name: attempt}, 'approval': approval, 'role': 'detail',
            'value': evidence['fov']['detail'], 'pins': pins}


def geometry_options(parser):
    parser.add_argument('--detail-camera-attempt', help='exact reviewed calibration directory for a detail-camera replay')
    parser.add_argument('--camera-approval', help='exact user approval of that measured detail angle')
    parser.add_argument('--shape-grid', type=int, choices=range(1024, 2049, 128),
                        help='override only the Trellis geometry upsample grid')
    parser.add_argument('--single-submission', action='store_true',
                        help='stop after one geometry submission, including an OOM')


def stages(value):
    selected=value.split(',')
    require(selected and len(set(selected))==len(selected) and all(s in ORDER for s in selected)
            and selected==sorted(selected,key=ORDER.index),'GPU stages must be unique and in pipeline order')
    require(not ('calibrate' in selected and 'appearance' in selected and 'geometry' not in selected),
            'Recalibration requires new geometry before appearance')
    return selected

def calibration_id(row):
    require(isinstance(row.get('prepared'),dict) and isinstance(row.get('conditioning'),dict),'Legacy calibration has no verified conditioning lineage; recalibrate')
    return digest({'prepared':row['prepared'],'fov':row['fov'],'sharedFov':row['sharedFov'],
                   **({'cameraReview': row['cameraReview']} if 'cameraReview' in row else {}),
                   'conditioning':{k:v['sha256'] for k,v in row['conditioning'].items()}})

def identical_multiview_prepares(head, calibrated, current):
    """Allow appearance to use a reviewed re-prepare only for identical camera inputs."""
    original = calibrated['prepared']
    require(calibrated.get('mode') == 'multiview' and calibrated.get('sharedFov') == 20
            and calibrated.get('fov') == {'geometry':20, 'detail':20}, 'Expected the fixed multiview rig')
    roles = [(role, view) for view in ('Front','Left','Back','Right') for role in ('geometry','detail')]
    receipts = []
    consumed = []
    for snapshot in (original, current):
        item = snapshot['receipt']
        path = Path(item['path']).resolve()
        require(path.parent.parent == (Path(head)/'run'/'prepare').resolve()
                and re.fullmatch(r'attempt-\d+', path.parent.name) and path.name == 'receipt.json',
                'Prepared receipt belongs to another head or stage')
        verify([item], fresh=True)
        data = read(path)
        receipts.append(data)
        result = data['result']
        require(data['stage'] == 'prepare' and data['state'] == 'complete'
                and result['rigFovDegrees'] == 20 and result['independentCropping'] is False,
                'Prepare replay changed the rig or crop')
        require(set(snapshot['images']) == {role+view for role,view in roles}, 'Incomplete prepared roles')
        for role, view in roles:
            image = snapshot['images'][role+view]
            require(image == result['views'][view.lower()]['images'][role+'-pair.png']
                    and image in data['outputs'] and Path(image['path']).resolve() ==
                    path.parent/'images'/view.lower()/(role+'-pair.png'), 'Prepare replay role pin mismatch')
        pins = list(snapshot['images'].values())
        verify(pins, fresh=True)
        consumed.extend([item, *pins])
    require(all(receipts[0][key] == receipts[1][key] for key in ('manifestHash','bindingsHash','runtimeIdentity'))
            and all(original['images'][key]['sha256'] == current['images'][key]['sha256']
                    for key in original['images']), 'Saved-shape replay requires byte-identical conditioning and bindings')
    return consumed


def cardinal_horn_pins(head, preparation):
    """Check a measured symmetric horn pair on the prepared 20-degree cardinal canvases."""
    import math
    from PIL import Image
    path = Path(head)/'review-evidence'/'cardinal-horns.json'
    require(path.is_file(), 'Measure the two horns on the prepared front and true profile views in cardinal-horns.json before geometry')
    evidence = pin(path)
    review = read(path)
    verify([evidence], fresh=True)
    roles = [role+view for view in ('Front','Left','Right') for role in ('detail','geometry')]
    require(review['images'] == {role:preparation['images'][role] for role in roles},
            'Horn measurements must bind the current prepared front and side image pairs')
    for role in ('geometry','detail'):
        with Image.open(review['images'][role+'Front']['path']) as image:
            size = image.size
        def point(value):
            require(isinstance(value,list) and len(value)==2 and all(type(n) in (float,int) and
                    0 <= n < limit for n,limit in zip(value,size)), 'Invalid horn tip pixel coordinates')
            return value
        measurements = review[role]
        a,b = map(point,measurements['frontTips'])
        span = abs(a[0]-b[0])
        require(span > 0, 'Mark both distinct front horn tips')
        focal = size[0]/(2*math.tan(math.radians(10)))
        for view in ('Left','Right'):
            with Image.open(review['images'][role+view]['path']) as image:
                require(image.size == size, 'Profile canvas changed dimensions')
            side = measurements[view.lower()]
            near = point(side['nearTip'])
            far = side['farTip']
            if far is None:
                continue  # explicitly recorded as occluded
            far = point(far)
            # Parallax scales each coordinate about the principal point. A tip high
            # in the image can shift vertically without gaining horizontal allowance.
            tolerance = [0.05*span + 1.5*abs(n-(limit-1)/2)*span/focal for n,limit in zip(near,size)]
            require(all(abs(a-b) <= t for a,b,t in zip(near,far,tolerance)),
                    f'{role} {view} depicts separated profile horns; correct the cardinal reference before GPU submission')
    return [evidence]


def validate_geometry(ledger):
    row=ledger['stages']['geometry']
    require(row.get('conditioningDigest')==calibration_id(ledger['stages']['calibrate']),
            'Saved geometry differs from current conditioning/camera; regenerate geometry')
    require(row.get('fov')==ledger['stages']['calibrate']['sharedFov'],'Saved geometry camera changed')
    verify(list(row['files'].values()),fresh=True)
    return row

def geometry_id(row):
    return digest({key:row[key] for key in ('files','fov','conditioningDigest','submission')})

def evidence_path(head,row):
    return Path(head)/'gpu'/'geometry-review'/f"geometry-{row['submission']:04d}"/'evidence.json'

def review_geometry(head,attempt,approval):
    require(isinstance(approval,str) and approval.strip(),'Pass the user review words as --approval')
    head=Path(head);ledger=read(head/'gpu'/'gpu.json');row=validate_geometry(ledger)
    expected=f"geometry-{row['submission']:04d}"
    require(attempt==expected,'Geometry approval must name the current exact submission')
    evidence=evidence_path(head,row);data=read(evidence)
    require(data['geometryDigest']==geometry_id(row),'Geometry review sheet is stale')
    verify(data['inputs']+[data['sheet']],fresh=True)
    folder=head/'gpu'/'reviews';folder.mkdir(exist_ok=True)
    target=folder/(attempt+'-approval.json')
    record={'attempts':{head.name:attempt},'geometryDigest':geometry_id(row),'evidence':pin(evidence),
            'decision':'approved','approval':approval,'productionAccepted':False}
    write(target,record,fresh=True)
    ledger['geometryReview']=pin(target);write_json(head/'gpu'/'gpu.json',ledger)
    return record

def require_geometry_review(head,ledger):
    row=validate_geometry(ledger);review=ledger.get('geometryReview')
    require(review is not None,'WAITING ON REVIEW: raw geometry sheet before appearance')
    verify([review],fresh=True);data=read(review['path']);attempt=f"geometry-{row['submission']:04d}"
    require(data.get('attempts')=={Path(head).name:attempt} and data.get('geometryDigest')==geometry_id(row)
            and data.get('decision')=='approved' and bool(data.get('approval','').strip()),
            'WAITING ON REVIEW: approval does not name current geometry')
    verify([data['evidence']],fresh=True);evidence=read(data['evidence']['path'])
    require(evidence.get('geometryDigest')==geometry_id(row),'Geometry sheet names another submission')
    verify(evidence['inputs']+[evidence['sheet']],fresh=True)
    return row

def evidence_geometry(ledger, rejected_attempt):
    if rejected_attempt is None:
        return validate_geometry(ledger)
    require(re.fullmatch(r'geometry-[0-9]{4,}', rejected_attempt), 'Name the exact rejected submission')
    rows = [row for row in ledger.get('rejectedGeometry', []) if row.get('occiput', {}).get('open') is True
            and type(row.get('submission')) is int and f"geometry-{row['submission']:04d}" == rejected_attempt]
    require(len(rows) == 1, 'Expected one rejected open-occiput geometry with that submission')
    return rows[0]


def make_geometry_evidence(head,ledger,rejected_attempt=None):
    from headkit.diagnostics import geometry_sheet
    head=Path(head);row=evidence_geometry(ledger,rejected_attempt);target=evidence_path(head,row)
    require(not target.exists(),'Geometry evidence is immutable; use the saved sheet')
    source=next(v for k,v in row['files'].items() if k.startswith('961:'))
    bindings=read(head/'bindings.json');embree=bindings['embree'];verify([embree,source],fresh=True)
    target.parent.mkdir(parents=True,exist_ok=True)
    sheet=geometry_sheet(source['path'],embree['path'],target.parent/'sheet.png')
    data={'geometryDigest':geometry_id(row),'attempt':target.parent.name,'inputs':[source,embree],
          'sheet':sheet,'visualReviewRequired':True,'checks':['horn counts and curves','one attached ear per temple in profile and three-quarter','jaw and chin','neck absence','rear skull','stray shells']}
    verify(data['inputs'],fresh=True)
    if rejected_attempt is not None:
        data['rejectedOcciput'] = row['occiput']
    require(geometry_id(evidence_geometry(read(head/'gpu'/'gpu.json'),rejected_attempt))==data['geometryDigest'],
            'Geometry changed during evidence generation')
    write(target,data,fresh=True)
    return target
