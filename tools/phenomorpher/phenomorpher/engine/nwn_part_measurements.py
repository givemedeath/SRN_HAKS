"""NWN part-owned measurements; reference proxies never redefine mesh joins."""
import numpy as np
from .target_contract import PART_JOINTS
from .silhouette_model import cross_section

# Explicit correspondence to existing NWN attachment names, not new rig joints.
END_JOINTS = {'chest':('neck_g',), 'pelvis':('lthigh_g','rthigh_g'),
 'neck':('head_g',), 'bicepl':('lforearm_g',), 'bicepr':('rforearm_g',),
 'forel':('lhand_g',), 'forer':('rhand_g',), 'legl':('lshin_g',),
 'legr':('rshin_g',), 'shinl':('lfoot_g',), 'shinr':('rfoot_g',)}
REFERENCE_KEYS = {'chest':('chestWidth','chestDepth','waistWidth','waistDepth'),
 'pelvis':('waistWidth','waistDepth'), 'neck':(), 'head':(),
 'bicepl':('upperArmProjectedLength',), 'bicepr':('upperArmProjectedLength',),
 'forel':('forearmProjectedLength',), 'forer':('forearmProjectedLength',),
 'handl':('handLength',), 'handr':('handLength',),
 'legl':('midThighWidth','midThighDepth'), 'legr':('midThighWidth','midThighDepth'),
 'shinl':('kneeWidth','kneeDepth','calfWidth','calfDepth','ankleWidth','ankleDepth'),
 'shinr':('kneeWidth','kneeDepth','calfWidth','calfDepth','ankleWidth','ankleDepth'),
 'footl':('footLength','footWidth'), 'footr':('footLength','footWidth')}


def model_parts(meshes, joints):
    result = {}
    for part, joint in PART_JOINTS.items():
        selected = [m for m in meshes if m['part']==part and m.get('render',True)]
        if not selected:
            result[part] = {'attachmentJoint':joint,'status':'unavailable'}
            continue
        frame = np.asarray(selected[0]['attachmentFrame'])
        inverse = np.linalg.inv(frame)
        local = [{**m,'position':m['position'] @ inverse[:3,:3].T + inverse[:3,3]} for m in selected]
        points = np.concatenate([m['position'] for m in local])
        entry = {'attachmentJoint':joint,'attachmentFrameMeters':frame.tolist(),
                 'localBoundsMeters':[points.min(0).tolist(),points.max(0).tolist()],
                 'localExtentMeters':np.ptp(points,axis=0).tolist(),
                 'meshNodes':[m['name'] for m in selected], 'referenceKeys':list(REFERENCE_KEYS[part]),
                 'surfaceBasis':'all rendered meshes owned by this NWN part; garment contours remain diagnostic',
                 'approval':False}
        end = END_JOINTS.get(part)
        if end and all(k in joints for k in (joint,*end)):
            delta = np.mean([joints[k] for k in end],axis=0)-np.asarray(joints[joint])
            distance = np.linalg.norm(delta)
            if distance>1e-12:
                axis = inverse[:3,:3] @ (delta/distance)
                axis /= np.linalg.norm(axis)
                x = np.array([1.,0,0]);x -= axis*np.dot(x,axis)
                if np.linalg.norm(x)<1e-6:
                    x=np.array([0.,1,0]);x-=axis*np.dot(x,axis)
                x/=np.linalg.norm(x);y=np.cross(axis,x)
                basis=np.column_stack((x,y,axis))
                projected=[{**m,'position':m['position'] @ basis} for m in local]
                all_points=np.concatenate([m['position'] for m in projected])
                low,high=all_points[:,2].min(),all_points[:,2].max()
                entry.update({'jointDistanceMeters':float(distance),'boneAxisLocal':axis.tolist(),
                    'axialExtentMeters':float(high-low),'axisBasis':'attachment X projected perpendicular to joint axis; depth is its orthogonal companion',
                    'sections':{str(f):{'axisPositionMeters':float(low+(high-low)*f),
                        'widthMeters':cross_section(projected,low+(high-low)*f,0),
                        'depthMeters':cross_section(projected,low+(high-low)*f,1)} for f in (.05,.25,.5,.75,.95)},
                    'connectorLimit':'Near-end sections are samples, not proof of actual connector contour or acceptance'})
        result[part]=entry
    return result


def reference_parts(measurements):
    return {part:{'attachmentJoint':joint,'sourceMeasurements':{k:measurements.get(k,{'value':None,'status':'unavailable'}) for k in REFERENCE_KEYS[part]},
                  'boundaryStatus':'reference anatomy proxy; NWN mesh ownership/overlap measured separately',
                  'unavailable':'hidden hip joins, head/neck and hand endpoints are not inferred',
                  'approval':False} for part,joint in PART_JOINTS.items()}
