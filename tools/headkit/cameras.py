"""Measured-bounds camera set, expressed in the retained glTF anatomical frame."""
import math
import numpy as np
from .common import require


def review_cameras(points, front_angle_degrees):
    points=np.asarray(points,float);require(points.ndim==2 and points.shape[1]==3 and np.isfinite(points).all(),'Finite head points required')
    require(type(front_angle_degrees) in (int,float) and math.isfinite(front_angle_degrees),'Reviewed front angle required')
    lower,upper=points.min(0),points.max(0);center=(lower+upper)/2;extent=upper-lower;size=float(np.linalg.norm(extent));require(size>0,'Nonzero head extent required')
    specs=[('front',0,0,False),('left-profile',90,0,False),('right-profile',-90,0,False),
        ('left-three-quarter',45,0,False),('right-three-quarter',-45,0,False),('back',180,0,False),
        ('crown',0,85,False),('jaw-underside',0,-80,False),('face-closeup',0,0,True),
        ('left-ear-closeup',65,0,True),('right-ear-closeup',-65,0,True),('cyberware-closeup',45,0,True)]
    rows=[]
    for name,yaw,elevation,close in specs:
        angle,tilt=math.radians(front_angle_degrees+yaw),math.radians(elevation)
        toward=np.array([math.cos(angle)*math.cos(tilt),math.sin(tilt),-math.sin(angle)*math.cos(tilt)])
        target=center.copy()
        if close:target[1]=lower[1]+extent[1]*.65
        scale=size*1.10 if not close else extent[1]*.63
        rows.append({'name':name,'eye':(target+toward*size*3).tolist(),'target':target.tolist(),'orthoScale':float(scale)})
    return rows
