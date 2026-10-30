"""Colour-space helpers shared by the face-mask stages and the palette, kept apart so palette code changes do not stale masks."""
import numpy as np


def lab(rgb):
    """CIE Lab (D65) of sRGB rows."""
    c=np.asarray(rgb,float).reshape(-1,3)/255;c=np.where(c>.04045,((c+.055)/1.055)**2.4,c/12.92)
    xyz=c@np.array([[.4124,.3576,.1805],[.2126,.7152,.0722],[.0193,.1192,.9505]]).T/np.array([.95047,1,1.08883])
    f=np.where(xyz>.008856,np.cbrt(xyz),7.787*xyz+16/116);return np.c_[116*f[:,1]-16,500*(f[:,0]-f[:,1]),200*(f[:,1]-f[:,2])]
