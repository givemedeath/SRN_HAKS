"""Annotated reference masks and measurements; no inferred/approved anatomy."""
import numpy as np
from PIL import Image, ImageDraw

from .measurement_common import require

VIEWS = ('front', 'left', 'back', 'right')


def foreground(image):
    rgb = np.asarray(image.convert('RGB')).astype(np.int16)
    cyan = (rgb[:, :, 1] > rgb[:, :, 0] + 3) & (rgb[:, :, 2] > rgb[:, :, 0] + 3)
    # Faint antialiased blue label specks must not extend stature past the sole.
    return (rgb.max(axis=2) > 32) & ~cyan


def fill_holes(mask):
    # Flood the exterior of a padded canvas. Preserve disconnected fingers.
    # Pillow's fromarray may expose read-only memory; floodfill otherwise silently
    # returns without painting its exterior. Copy before taking PixelAccess.
    padded = Image.fromarray(np.pad(mask.astype(np.uint8) * 255, 1)).copy()
    ImageDraw.floodfill(padded, (0, 0), 128, thresh=0)
    value = np.asarray(padded)[1:-1, 1:-1]
    return value != 128


def annotated_masks(image, annotation):
    require(annotation['coordinateSystem'] == 'source-sheet-pixels', 'Unknown annotation coordinates')
    box = annotation['crop']
    require(len(box) == 4 and 0 <= box[0] < box[2] <= image.width
            and 0 <= box[1] < box[3] <= image.height, 'Invalid annotated crop')
    full = fill_holes(foreground(image.crop(tuple(box))))
    body = Image.fromarray(full.astype(np.uint8) * 255)
    draw = ImageDraw.Draw(body)
    for polygon in annotation['exclusions']:
        require(len(polygon) >= 3 and all(0 <= x < image.width and 0 <= y < image.height for x, y in polygon),
                'Invalid exclusion polygon')
        draw.polygon([(x - box[0], y - box[1]) for x, y in polygon], fill=0)
    body_mask = np.asarray(body) > 0
    require(full.any() and body_mask.any(), 'Empty reference mask')
    return full, body_mask


def runs(row):
    x = np.flatnonzero(row)
    if not len(x):
        return []
    cuts = np.flatnonzero(np.diff(x) > 1) + 1
    return [(int(values[0]), int(values[-1]) + 1) for values in np.split(x, cuts)]


def width_at(mask, y, center, region='central'):
    intervals = runs(mask[y])
    if region == 'central':
        intervals = [pair for pair in intervals if pair[0] <= center < pair[1]]
    if not intervals:
        return None
    if region == 'largest':
        pair=max(intervals,key=lambda p:p[1]-p[0])
        return float(pair[1]-pair[0])
    if region == 'left-limb':
        intervals = [pair for pair in intervals if pair[1] <= center]
    elif region == 'right-limb':
        intervals = [pair for pair in intervals if pair[0] > center]
    if not intervals:
        return None
    if region == 'all':
        return float(intervals[-1][1] - intervals[0][0])
    pair = min(intervals, key=lambda p: abs((p[0] + p[1]) / 2 - center))
    return float(pair[1] - pair[0])


def foot_envelopes(mask, annotation):
    """Visible projection inside explicit foot regions, never a hidden rig join."""
    region=annotation.get('footRegion')
    if not region:
        return []
    x0,y0,x1,y1=annotation['crop']
    top,bottom=region['topY']-y0,region['bottomY']-y0
    require(0<=top<bottom<=mask.shape[0],'Invalid foot measurement region')
    center=annotation['midlineX']-x0
    windows=[('combined-side',0,mask.shape[1])] if annotation['view'] in ('left','right') else [
        ('image-left',0,center),('image-right',center,mask.shape[1])]
    output=[]
    for name,left,right in windows:
        yy,xx=np.nonzero(mask[top:bottom,left:right])
        if not len(xx):
            continue
        output.append({'scope':name,'boundsPixels':[int(xx.min()+left+x0),int(yy.min()+top+y0),
                      int(xx.max()+left+x0+1),int(yy.max()+top+y0+1)],
                      'extentPixels':int(xx.max()-xx.min()+1),
                      'ownership':'overlapping side-view feet unresolved' if name=='combined-side' else 'image-space foot; anatomical side unassigned'})
    return output


def measure(mask, annotation):
    x0, y0, _, _ = annotation['crop']
    crown, sole = annotation['crownY'], annotation['soleY']
    height = sole - crown
    require(height > 0, 'Invalid crown-to-sole annotation')
    center = annotation['midlineX'] - x0
    output = {}
    for label, landmark in annotation['landmarks'].items():
        if landmark is None:
            output[label] = {'value': None, 'status': 'unavailable'}
            continue
        y = landmark['y'] - y0
        require(0 <= y < mask.shape[0], 'Landmark outside crop: ' + label)
        output[label + 'Height'] = {'value': (sole - landmark['y']) / height,
                                    'uncertainty': landmark.get('uncertaintyPixels', 3) / height,
                                    'basis': 'fraction-of-stature', 'status': 'provisional-annotation'}
        region = landmark.get('region', 'central')
        width = width_at(mask, y, center, region)
        mirror_spread = None
        if region == 'left-limb':
            right = width_at(mask, y, center, 'right-limb')
            if width is not None and right is not None:
                mirror_spread = abs(width - right) / height
                width = (width + right) / 2
        output[label + ('Depth' if annotation['view'] in ('left', 'right') else 'Width')] = {
            'value': width / height if width is not None else None,
            'mirrorSpread': mirror_spread,
            'uncertainty': (2 / height + (width / height) * annotation.get('crownUncertaintyPixels', 0) / height)
                           if width is not None else None,
            'basis': 'fraction-of-stature', 'status': 'provisional-mask' if width is not None else 'unavailable'}
    for label, endpoints in annotation.get('segments', {}).items():
        if endpoints is None:
            output[label] = {'value': None, 'status': 'unavailable'}
        else:
            output[label] = {'value': float(np.linalg.norm(np.array(endpoints[1]) - endpoints[0])) / height,
                             'uncertainty': 6 / height, 'basis': 'fraction-of-stature',
                             'status': 'provisional-projected-segment'}
    feet=foot_envelopes(mask,annotation)
    if annotation.get('footRegion'):
        key='footLength' if annotation['view'] in ('left','right') else 'footWidth'
        values=[f['extentPixels'] for f in feet]
        available=bool(values) and (len(values)==1 if key=='footLength' else len(values)==2)
        value=float(np.mean(values))/height if available else None
        output[key]={'value':value,'uncertainty':(4/height+value*annotation.get('crownUncertaintyPixels',0)/height) if available else None,
                     'basis':'fraction-of-stature','status':'provisional-visible-foot-envelope' if available else 'unavailable',
                     'scope':'combined side-view silhouette; overlapping feet unresolved' if key=='footLength' else 'mean of two image-space foot widths',
                     'mirrorSpread':(max(values)-min(values))/height if len(values)==2 else None}
    elif annotation['view'] in ('left', 'right'):
        band = mask[max(0, annotation['soleY'] - y0 - 30):annotation['soleY'] - y0 + 1]
        _, xx = np.nonzero(band)
        if len(xx):
            output['footLength'] = {'value': float(xx.max() - xx.min() + 1) / height,
                                    'uncertainty': 4 / height, 'basis': 'fraction-of-stature',
                                    'status': 'provisional-visible-foot-envelope'}
    pose = annotation.get('pose', {})
    return {'staturePixels': height, 'crownY': crown, 'soleY': sole,
            'statureUncertaintyPixels': annotation.get('crownUncertaintyPixels', 0) + 1,
            'crownStatus': annotation['crownStatus'], 'measurements': output, 'pose': pose,
            'footEnvelopes':feet,'referenceApproval': False}


def summarize(views):
    heights = [v['staturePixels'] for v in views.values()]
    disagreement = (max(heights) - min(heights)) / float(np.mean(heights))
    measurements = {}
    keys = set().union(*(v['measurements'] for v in views.values()))
    for key in sorted(keys):
        entries = [(view, row['measurements'][key]) for view, row in views.items()
                   if key in row['measurements'] and row['measurements'][key]['value'] is not None]
        if not entries:
            measurements[key] = {'value': None, 'status': 'unavailable'}
            continue
        values = [row['value'] for _, row in entries]
        measurements[key] = {'value': float(np.mean(values)), 'spread': max(values) - min(values),
                             'annotationUncertainty': max(row.get('uncertainty', 0) for _, row in entries),
                             'mirrorSpread': max((row.get('mirrorSpread') or 0) for _, row in entries),
                             'views': [view for view, _ in entries], 'status': 'proposed-not-approved'}
        if key in ('footWidth','footLength'):
            measurements[key]['projectionScopes']=sorted({row.get('scope','legacy visible envelope') for _,row in entries})
    return {'measurements': measurements, 'viewStatureDisagreement': disagreement,
            'flags': ['view-stature-disagreement-over-2-percent'] if disagreement > .02 else [],
            'referenceApproval': False,
            'limitations': ['Projected segment lengths are not 3D bone lengths.',
                            'Clothing-covered anatomy is unavailable; clothed contours are labelled separately.',
                            'Crown annotations may be provisional when hair hides the skull.']}


def overlay(image, annotation, body_mask):
    result = image.crop(tuple(annotation['crop'])).convert('RGBA')
    tint = Image.new('RGBA', result.size, (65, 230, 140, 0))
    alpha = Image.fromarray(body_mask.astype(np.uint8) * 70)
    tint.putalpha(alpha)
    result = Image.alpha_composite(result, tint)
    draw = ImageDraw.Draw(result)
    x0, y0, _, _ = annotation['crop']
    for polygon in annotation['exclusions']:
        draw.line([(x - x0, y - y0) for x, y in polygon] + [(polygon[0][0] - x0, polygon[0][1] - y0)], fill='red', width=2)
    for label, landmark in annotation['landmarks'].items():
        if landmark:
            y = landmark['y'] - y0
            names={'waist':'chest / pelvis section','chest':'chest section','midThigh':'leg section',
                   'knee':'leg / shin proxy','calf':'shin section','ankle':'shin / foot proxy'}
            intervals=runs(body_mask[y]) if 0<=y<body_mask.shape[0] else []
            center=annotation['midlineX']-x0
            if landmark.get('region')=='left-limb' and annotation['view'] in ('front','back'):
                intervals=[p for p in intervals if p[1]<=center or p[0]>center]
            elif landmark.get('region')=='largest':
                intervals=sorted(intervals,key=lambda p:p[1]-p[0],reverse=True)[:1]
            else:
                intervals=[p for p in intervals if p[0]<=center<p[1]]
            for left,right in intervals:
                draw.line((left,y,right-1,y),fill=(250,220,65),width=2)
            draw.text((4,y+2),names.get(label,label),fill='white')
    if annotation['view']=='front':
        center=annotation['midlineX']
        for key,name in (('upperArmProjectedLength','bicep'),('forearmProjectedLength','forearm')):
            endpoints=annotation.get('segments',{}).get(key)
            if not endpoints:continue
            for side in ('l','r'):
                points=[(x if side=='l' else 2*center-x,y) for x,y in endpoints]
                points=[(x-x0,y-y0) for x,y in points]
                draw.line(points,fill=(85,180,245),width=2)
                for x,y in points:draw.ellipse((x-3,y-3,x+3,y+3),outline=(85,180,245),width=1)
                x,y=points[0];draw.text((x+5,(y+points[1][1])/2),name+side,fill='white')
    for y in (annotation['crownY'], annotation['soleY']):
        draw.line((0, y - y0, result.width, y - y0), fill='cyan', width=2)
    feet=foot_envelopes(body_mask,annotation)
    if feet:
        y=annotation['soleY']-y0+8
        for foot in feet:
            left,_,right,_=foot['boundsPixels'];left-=x0;right-=x0+1
            draw.line((left,y,right,y),fill=(245,120,235),width=2)
            for x in (left,right):draw.line((x,y-4,x,y+4),fill=(245,120,235),width=2)
        label='foot length: visible projection' if annotation['view'] in ('left','right') else 'foot width: each visible foot'
        draw.text((4,annotation['footRegion']['topY']-y0+12),label,fill='white')
    return result.convert('RGB')
