"""Review gates for detailed-only inputs and explicitly selected clay fallback."""
import math
from PIL import Image
from tools.headkit.common import asset, require
from tools.headkit.reference_background import require_conditioning_review as require_single


def validate_pair(data):
    review=data.get('approval',{}).get('referencePair',{})
    inputs=data['inputs']
    require(review.get('decision')=='approved' and bool(review.get('notes','').strip()),
            'Review the clay/detail reference pair')
    for role in ('reference','geometry','detail','geometryForegroundMask','foregroundMask'):
        require(role in inputs and review.get(role+'Sha256')==inputs[role]['sha256'], 'Stale clay/detail pair review')
    landmarks=review.get('landmarks',[])
    require(isinstance(landmarks,list) and len(landmarks)>=4 and
            len({row.get('name') for row in landmarks})==len(landmarks), 'Review at least four paired landmarks')
    for row in landmarks:
        require(isinstance(row.get('name'),str) and bool(row['name']), 'Named paired landmarks required')
        for role in ('geometry','detail'):
            point=row.get(role,[])
            require(isinstance(point,list) and len(point)==2 and
                    all(type(v) in (float,int) and math.isfinite(v) and 0<=v<=1 for v in point),
                    'Paired landmarks must use normalized image coordinates')
        require(math.dist(row['geometry'],row['detail'])<=.02, 'Clay/detail landmark alignment exceeds 2% of the frame')
    return review


def require_conditioning_review(manifest_path,data):
    if data.get('conditioning','detailed-v1')=='detailed-v1':return require_single(manifest_path,data)
    require(data.get('conditioning')=='clay-detail-v1','Unsupported conditioning mode')
    validate_pair(data)
    sizes=[];reports={}
    for role,mask,review in (('geometry','geometryForegroundMask','geometryBackground'),
                             ('detail','foregroundMask','background')):
        # A separately retained clay source can have alpha even when the detailed
        # original is opaque. Bind its own source bytes and background decision.
        source=data['inputs'].get('clayReference',data['inputs']['reference']) if role=='geometry' else data['inputs']['reference']
        inputs={**data['inputs'],'reference':source,'geometry':data['inputs'][role],'detail':data['inputs'][role],
                'foregroundMask':data['inputs'][mask]}
        view={**data,'inputs':inputs,'approval':{'background':data.get('approval',{}).get(review,{})}}
        reports[role]=require_single(manifest_path,view)
        with Image.open(asset(manifest_path,inputs['geometry'])['path']) as image:sizes.append(image.size)
    require(sizes[0]==sizes[1], 'Clay/detail images must share the same canvas and framing')
    return reports
