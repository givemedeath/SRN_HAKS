"""Colour-only donor sampling for explicitly bounded projection-miss correction."""
import numpy as np
from tools.headkit.common import require
from .geometry import corner_hash


PATCH_SCOPE={'distance':.003,'textureFraction':.0001}
# A larger colour-only patch needs the user's own approval, quoted in the patch: the 1.90 m stun staff at its chosen
# 41 x 49 mm grip had 212 missed texels (0.045%) up to 3.11 mm from an inside-out generated donor (user, 2026-11-12:
# "Raise the patch cap"; one texel then measured 3.203 mm: "Allow 3.25 mm").
EXTENDED_PATCH_SCOPE={'distance':.00325,'textureFraction':.0005}
# The oriented transfer itself reads at most 3 mm. A fit stretched along its length (the wave-4 Pole Arm at 2.3x, 4.1 mm)
# or reduced across a coarse spot (the Macauitl's paddle, 3.7 mm) sits further from its donor; the user may widen one
# manifest's transfer up to 5 mm, quoted in `maximumDistanceApproval` (2026-11-13: "Allow 4.2 mm", "Allow 3.8 mm").
APPROVED_TRANSFER_DISTANCE=.005


def transfer_distance(policy):
    """The policy's oriented transfer distance: 3 mm at most, or up to 5 mm with the user's quoted approval."""
    maximum=policy.get('maximumDistance',PATCH_SCOPE['distance']);approval=policy.get('maximumDistanceApproval')
    bound=APPROVED_TRANSFER_DISTANCE if isinstance(approval,str) and approval.strip() else PATCH_SCOPE['distance']
    require(0<maximum<=bound,'Bounded outward donor transfer required (over 3 mm needs maximumDistanceApproval quoting the user)')
    return maximum


def patch_scope(patch):
    approval=(patch or {}).get('userApproval')
    return EXTENDED_PATCH_SCOPE if isinstance(approval,str) and approval.strip() else PATCH_SCOPE


def patch_distance_bound(policy):
    """The unoriented patch distance: the policy's maximumUnorientedDistance (default 2.1 mm), within the transfer
    distance unless the patch carries a user approval for the extended scope. A policy that tightens its transfer
    distance below the 3 mm default binds every patch, approved or not."""
    unoriented=policy.get('maximumUnorientedDistance',.0021);maximum=policy.get('maximumDistance',PATCH_SCOPE['distance'])
    if patch_scope(policy.get('unorientedSourcePatch')) is EXTENDED_PATCH_SCOPE and maximum>=PATCH_SCOPE['distance']:return unoriented
    return min(maximum,unoriented)


def validate_texture_patch(corners,patch,*,maximum_distance=.0021):
    require(patch.get('reviewed') is True and patch.get('notes','').strip(),'Review the exact bounded donor texture patch')
    corners=np.asarray(corners,dtype='<f8')
    require(corner_hash(corners)==patch['targetCornerHash'],'Texture patch belongs to different target geometry')
    scope=patch_scope(patch)
    require(0<maximum_distance<=scope['distance'],'Texture patch qualification exceeds the global transfer distance')
    require(0<patch['maximumDistance']<=maximum_distance and 0<patch['maximumTextureFraction']<=scope['textureFraction'],
            'Texture patch exceeds its measured local scope')
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
