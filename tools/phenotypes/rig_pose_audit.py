"""Pure sampled rigid-pose measurements for offline rig audits, not client evidence."""
import copy
import re
import numpy as np

from retarget import NODE, transforms
from rig_controller_audit import CLIP, arrays
from target_contract import require


def quaternion(axis_angle):
    axis = np.asarray(axis_angle[:3],float)
    length = np.linalg.norm(axis)
    if length < 1e-14:
        return np.array([0.,0.,0.,1.])
    angle = float(axis_angle[3])/2
    return np.r_[axis/length*np.sin(angle), np.cos(angle)]


def axis_angle(q):
    q = np.asarray(q,float)/np.linalg.norm(q)
    angle = 2*np.arctan2(np.linalg.norm(q[:3]), q[3])
    length = np.linalg.norm(q[:3])
    return [*(q[:3]/length if length > 1e-14 else np.zeros(3)), angle]


def slerp(left, right, amount):
    left, right = quaternion(left), quaternion(right)
    dot = float(np.dot(left,right))
    if dot < 0:
        right = -right
        dot = -dot
    dot = np.clip(dot,-1,1)
    if dot > .9995:
        return axis_angle(left + amount*(right-left))
    angle = np.arccos(dot)
    return axis_angle((np.sin((1-amount)*angle)*left + np.sin(amount*angle)*right)/np.sin(angle))


def interpolate(rows, time, rotation=False):
    values = np.asarray(rows,float)
    require(values.ndim == 2 and len(values) and
            np.all(np.diff(values[:,0]) >= 0), 'Invalid key times')
    if time <= values[0,0]:
        return values[0,1:].tolist()
    if time >= values[-1,0]:
        return values[-1,1:].tolist()
    index = int(np.searchsorted(values[:,0],time,side='right'))
    left,right = values[index-1],values[index]
    amount = (time-left[0])/(right[0]-left[0])
    return (slerp(left[1:],right[1:],amount) if rotation
            else (left[1:] + amount*(right[1:]-left[1:])).tolist())


def sample(skeleton, clip_body, time):
    result = copy.deepcopy(skeleton)
    for match in NODE.finditer(clip_body):
        key,body = match[2].lower(),match[3]
        if key not in result:
            continue
        keyed = {label:values for label,values,_,_ in arrays(body)}
        require('positionbezierkey' not in keyed and 'orientationbezierkey' not in keyed,
                'Offline audit sampler does not establish Bezier engine semantics')
        for field,rotation in [('position',False),('orientation',True)]:
            if field+'key' in keyed:
                value=interpolate(keyed[field+'key'],time,rotation)
            else:
                static=re.search(r'(?mi)^\s*'+field+r'\s+([^\n]+)',body)
                if not static:
                    continue
                value=[float(v) for v in static[1].split()]
            result[key][field]=np.asarray(value,float) if field=='position' else value
    return transforms(result)


def inherited_clips(chain, texts):
    output={}
    for owner in chain:
        for match in CLIP.finditer(texts[owner]):
            output.setdefault(match[1].lower(),{'owner':owner,'text':match[0],
                'body':match[2], 'length':float(re.search(r'(?mi)^\s*length\s+(\S+)',match[2])[1])})
    return output
