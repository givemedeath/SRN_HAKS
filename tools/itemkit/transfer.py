"""Colour-only donor sampling for explicitly bounded projection-miss correction."""
import numpy as np
import hashlib
from tools.headkit.common import require


def validate_texture_patch(corners,patch,*,maximum_distance=.0021):
    require(patch.get('reviewed') is True and patch.get('notes','').strip(),'Review the exact bounded donor texture patch')
    corners=np.asarray(corners,dtype='<f8')
    require(hashlib.sha256(corners.tobytes()).hexdigest()==patch['targetCornerHash'],'Texture patch belongs to different target geometry')
    require(0<maximum_distance<=.003,'Texture patch qualification exceeds the global transfer distance')
    require(0<patch['maximumDistance']<=maximum_distance and 0<patch['maximumTextureFraction']<=.0001,'Texture patch exceeds its measured local scope')
    faces=patch['faces'];require(faces and all(type(i) is int and 0<=i<len(corners) for i in faces) and len(set(faces))==len(faces),'Invalid texture patch face scope')
    area=np.linalg.norm(np.cross(corners[:,1]-corners[:,0],corners[:,2]-corners[:,0]),axis=1)
    require(len(faces)<len(corners)*.03 and area[faces].sum()<area.sum()*.03,'Texture patch exceeds bounded face/surface scope')
    return set(faces)


def linear_rgb(srgb):
    values=np.asarray(srgb,float)
    return np.where(values<=.04045,values/12.92,((values+.055)/1.055)**2.4)


def sample_image(pixels,uv,repeat=True,decode_srgb=False):
    """Bilinear sampling at pixel centres; arrays use Blender's bottom-up order."""
    pixels=np.asarray(pixels);uv=np.asarray(uv,float);height,width=pixels.shape[:2]
    require(pixels.ndim==3 and pixels.shape[2]>=3 and np.isfinite(uv).all(),'Finite image/UV inputs required')
    if repeat:uv=uv%1
    coordinates=uv*np.array([width,height])-.5;lo=np.floor(coordinates).astype(int);fraction=coordinates-lo
    def texel(dx,dy):
        x=lo[:,0]+dx;y=lo[:,1]+dy
        if repeat:values=pixels[y%height,x%width,:3];valid=1
        else:
            valid=((x>=0)&(x<width)&(y>=0)&(y<height))[:,None]
            values=pixels[np.clip(y,0,height-1),np.clip(x,0,width-1),:3]
        return (linear_rgb(values) if decode_srgb else values)*valid
    x=fraction[:,0,None];y=fraction[:,1,None]
    return (texel(0,0)*(1-x)+texel(1,0)*x)*(1-y)+(texel(0,1)*(1-x)+texel(1,1)*x)*y


def finished_colour(base_pixels,uv,positions,normals,reference_pixels,settings):
    # Decode before interpolation, matching the sRGB image shader's linear filter.
    base=sample_image(base_pixels,uv,decode_srgb=True)
    if not settings:return base
    h,w=reference_pixels.shape[:2]
    y0,y1=settings['nativeY'];z0,z1=settings['nativeZ']
    u=(y1-positions[:,1])/(y1-y0);v=(positions[:,2]-z0)/(z1-z0)
    mask=np.clip(np.minimum.reduce([u/.025,(1-u)/.025,v/.025,(1-v)/.025]),0,1)
    for quad,across,facing in ((settings['frontPixelQuad'],v,normals[:,0]>.7),
                              (settings.get('backPixelStrip'),(v*settings.get('backRepeat',8))%1,normals[:,0]<-.7)):
        if quad is None and settings.get('backPattern')=='carbon-weave':
            fy,fz=settings['backFrequency'];wave=np.sin(2*np.pi*(u*fy+v*fz))*np.sin(2*np.pi*(u*fy-v*fz))
            colour=np.repeat((settings['backBaseLinear']+settings['backAmplitudeLinear']*wave)[:,None],3,axis=1)
            factor=(mask*facing)[:,None];base=base*(1-factor)+colour*factor;continue
        corners=np.asarray(quad,float)/[w,h];corners[:,1]=1-corners[:,1];a,b,c,d=corners
        q=a+u[:,None]*(b-a)+across[:,None]*(d-a)+(u*across)[:,None]*(a-b+c-d)
        colour=sample_image(reference_pixels,q,repeat=False,decode_srgb=True);factor=(mask*facing)[:,None]
        base=base*(1-factor)+colour*factor
    return base
