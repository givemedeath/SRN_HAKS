"""Fit proposal: scale and place a generated head on an approved reference head by matching midline profiles.

Both heads are compared head-local (face +y, up +z). The generated GLB is first taken through the toolkit basis
(x,-z,y) and yawed 180 degrees, the frame the reviewed troll-male-01 matrix uses. The front and back of a narrow
midline band are profiled in height bins; the proposal is the uniform scale and (y, z) offset whose scaled source
profile best matches the reference above its lower neck region (median-centred mean absolute distance, grid search).
The output is a proposal for review with an overlay; it never approves itself."""
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from .common import require, positive, pin, write
from .gltf import mesh


def _axis_angle(values):
    """3x3 rotation of an NWN ASCII orientation (axis x y z, angle radians); a zero angle is identity whatever the axis."""
    x,y,z,angle=(float(v) for v in values);n=np.linalg.norm([x,y,z])
    if angle==0 or n==0:return np.eye(3)
    x,y,z=x/n,y/n,z/n;c,s=np.cos(angle),np.sin(angle);t=1-c
    return np.array([[t*x*x+c,t*x*y-s*z,t*x*z+s*y],[t*x*y+s*z,t*y*y+c,t*y*z-s*x],[t*x*z-s*y,t*y*z+s*x,t*z*z+c]])


def ascii_surface(path, samples=200000, seed=0):
    """Area-weighted surface samples of every trimesh node of an ASCII MDL in model space: each node's verts go through its
    own and its parents' position/orientation (stock heads carry small node offsets and 'orientation 0 0 1 0')."""
    lines=Path(path).read_text(encoding='utf-8').splitlines();nodes={};node=None;i=0
    while i<len(lines):
        words=lines[i].split();key=words[0].lower() if words else ''
        if key=='node' and len(words)>=3:node=nodes[words[2].lower()]={'parent':None,'position':np.zeros(3),'rotation':np.eye(3),'triangles':[],'verts':None}
        elif key=='endnode':node=None
        elif node is not None and key=='parent' and len(words)==2:node['parent']=None if words[1].upper()=='NULL' else words[1].lower()
        elif node is not None and key=='position' and len(words)==4:node['position']=np.array([float(v) for v in words[1:]])
        elif node is not None and key=='orientation' and len(words)==5:node['rotation']=_axis_angle(words[1:])
        elif node is not None and key=='verts':
            count=int(words[1]);node['verts']=np.array([[float(v) for v in lines[i+1+k].split()[:3]] for k in range(count)]);i+=count
        elif node is not None and key=='faces':
            require(node['verts'] is not None,'Faces before verts');count=int(words[1])
            idx=np.array([[int(v) for v in lines[i+1+k].split()[:3]] for k in range(count)]);node['triangles'].append(node['verts'][idx]);i+=count
        i+=1
    def world(name,depth=0):
        require(name in nodes and depth<64,'Reference node hierarchy is broken: '+str(name))
        n=nodes[name];rotation,position=n['rotation'],n['position']
        if n['parent'] is None:return rotation,position
        parent_rotation,parent_position=world(n['parent'],depth+1);return parent_rotation@rotation,parent_rotation@position+parent_position
    triangles=[]
    for name,n in nodes.items():
        if n['triangles']:rotation,position=world(name);triangles+=[t@rotation.T+position for t in n['triangles']]
    require(triangles,'Reference has no trimesh faces');return surface_samples(np.concatenate(triangles),samples,seed)


def surface_samples(triangles, samples=200000, seed=0):
    """Area-weighted points on triangles (n,3,3), so sparse and dense meshes profile alike."""
    tri=np.asarray(triangles,float);area=np.linalg.norm(np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]),axis=1)
    require(area.sum()>0,'Degenerate surface');rng=np.random.default_rng(seed)
    pick=rng.choice(len(tri),samples,p=area/area.sum());u,v=rng.random((2,samples))
    flip=u+v>1;u[flip],v[flip]=1-u[flip],1-v[flip];t=tri[pick]
    return t[:,0]+u[:,None]*(t[:,1]-t[:,0])+v[:,None]*(t[:,2]-t[:,0])


def head_local(positions):
    """GLB -> toolkit NWN basis (x,-z,y) -> 180-degree yaw: (-x, z, y)."""
    p=np.asarray(positions,float);return np.stack([-p[:,0],p[:,2],p[:,1]],1)


def profile(points, step, band=.05):
    width=np.ptp(points[:,0]);mid=np.median(points[:,0]);c=points[np.abs(points[:,0]-mid)<band*width]
    require(len(c)>100,'Midline band is empty');z0=c[:,2].min();n=max(1,int(np.ceil((c[:,2].max()-z0)/step)))
    i=np.minimum(((c[:,2]-z0)/step).astype(int),n-1);front=np.full(n,-np.inf);back=np.full(n,np.inf)
    np.maximum.at(front,i,c[:,1]);np.minimum.at(back,i,c[:,1]);return z0+(np.arange(n)+.5)*step,front,back


def match(source, reference, *, exclude_lower=.25, scales=(.2,.6,.0025), offsets=(-.2,.2,.002), step=.004, source_step=.002):
    zr,fr,br=profile(reference,step);keep=zr>=zr.min()+exclude_lower*np.ptp(zr)
    okf=np.isfinite(fr)&keep;okb=np.isfinite(br)&keep;zs,fs,bs=profile(source,source_step)
    def error(s,tz):
        q=(zr-tz)/s;k=np.clip(np.round((q-zs[0])/source_step).astype(int),0,len(zs)-1);inside=(q>=zs[0])&(q<=zs[-1])
        ff,bb=s*fs[k],s*bs[k];mf=okf&inside&np.isfinite(ff);mb=okb&inside&np.isfinite(bb)
        if mf.sum()<.8*okf.sum() or mb.sum()<.5*okb.sum():return np.inf,0.
        residual=np.r_[fr[mf]-ff[mf],br[mb]-bb[mb]];ty=float(np.median(residual));return float(np.mean(np.abs(residual-ty))),ty
    grid=[(error(s,tz)[0],s,tz) for s in np.arange(*scales) for tz in np.arange(*offsets)]
    best=min(grid);require(np.isfinite(best[0]),'No admissible profile alignment')
    _,s,tz=best;err,ty=error(s,tz)
    return {'scale':float(s),'translation':[0.,ty,float(tz)],'meanAbsoluteProfileDistance':err,'excludeLowerFraction':exclude_lower}


def nose_tip(points, step, tolerance, *, around=None, window=None):
    """Most forward midline point in the middle half of the profile height (clear of chin, crown, crests and horns);
    a flat tip is centred over the bins within tolerance of the maximum. With `around`/`window` the search is limited to
    that height band, so tusks or a lip further forward than the nose (05, 04-A) cannot win."""
    z,front,_=profile(points,step);ok=np.isfinite(front);lo,hi=z[ok].min(),z[ok].max()
    band=ok&(z>lo+.25*(hi-lo))&(z<hi-.25*(hi-lo))
    if around is not None:band&=np.abs(z-around)<=window
    require(band.any(),'No midline face band')
    n=np.flatnonzero(band)[np.argmax(front[band])];peak=front[n];near=band&(front>=peak-tolerance);lo=hi=n
    # Only the contiguous run around the maximum: a chin as far forward as the nose must not pull the tip down.
    while lo>0 and near[lo-1]:lo-=1
    while hi<len(z)-1 and near[hi+1]:hi+=1
    return np.array([0.,peak,float(z[lo:hi+1].mean())])


NOSE_WINDOW,NOSE_AGREEMENT=.015,.02  # metres, reference scale


def reference_depth(points, exclude_lower=.25, step=.004):
    """Depth/height of the midline profile the fit matches (above exclude_lower): front-most minus back-most over the height.
    Back hair (ponytails, buns, hanging hair) deepens it and pulls the profile fit to the wrong scale. Race heads v1: the
    references that mis-scaled fits measured pfh0_head001 1.64, pfd0_head008 2.02 and pfo0_head009 1.97 (fit scale 0.50-0.60);
    their replacements 1.23 (pfh0_head024), 1.63 (pfd0_head012) and 1.56 (pfo0_head011)."""
    z,front,back=profile(points,step);keep=(z>=z.min()+exclude_lower*np.ptp(z))&np.isfinite(front)&np.isfinite(back)
    require(keep.sum()>3,'Reference profile is too short');return float((front[keep].max()-back[keep].min())/np.ptp(z[keep]))


def rank_references(paths, exclude_lower=.25, samples=40000):
    """Candidate stock reference heads, most compact (lowest depth/height) first. Pick the lowest whose side silhouette shows
    no hanging hair or bun; the ranking is measured, the choice still needs that look."""
    rows=[{'reference':pin(path),'depthRatio':round(reference_depth(ascii_surface(path,samples),exclude_lower),3)} for path in paths]
    return sorted(rows,key=lambda row:row['depthRatio'])


LANDMARKS=('eyeLeft','eyeRight','lips','noseTip')
# Face landmarks of the base heads, head_g frame (m): every non-Human r3 srn_body head001 (origin/main ea0dff41) is a reshaped
# Human head001 sharing its texture, so pupils and the lip seam come from reviewed UV points on the Human PLT (pupil .186/.646 male,
# .186/.644 female; lip seam .05/.272, .05/.275) and the nose tip is the most forward vertex between them (race heads v1
# review-kit/base_landmarks.py). pmh0/pfh0 are the stock Human head001s, the reference for approved Human heads.
BASE_HEADS={
    'pmh0':{'eyeLeft':(-0.03359,0.09835,0.06378),'eyeRight':(0.03369,0.09832,0.06380),'lips':(-0.00018,0.11280,-0.01242),'noseTip':(-0.00020,0.13385,0.02779)},
    'pfh0':{'eyeLeft':(-0.03326,0.09880,0.05858),'eyeRight':(0.03349,0.09876,0.05832),'lips':(0.00007,0.10728,-0.00532),'noseTip':(0.00017,0.13089,0.02382)},
    'pme0':{'eyeLeft':(-0.03640,0.10658,0.06912),'eyeRight':(0.03651,0.10654,0.06914),'lips':(-0.00020,0.12223,-0.01346),'noseTip':(-0.00021,0.14505,0.03012)},
    'pfe0':{'eyeLeft':(-0.03512,0.10431,0.06185),'eyeRight':(0.03536,0.10427,0.06157),'lips':(0.00008,0.11326,-0.00561),'noseTip':(0.00018,0.13819,0.02515)},
    'pmd0':{'eyeLeft':(-0.02984,0.08738,0.05666),'eyeRight':(0.02993,0.08735,0.05668),'lips':(-0.00016,0.10021,-0.01104),'noseTip':(-0.00017,0.11892,0.02469)},
    'pfd0':{'eyeLeft':(-0.02927,0.08695,0.05156),'eyeRight':(0.02948,0.08692,0.05133),'lips':(0.00006,0.09441,-0.00468),'noseTip':(0.00015,0.11519,0.02097)},
    'pmo0':{'eyeLeft':(-0.03746,0.10969,0.07114),'eyeRight':(0.03757,0.10966,0.07116),'lips':(-0.00020,0.12581,-0.01386),'noseTip':(-0.00022,0.14929,0.03100)},
    'pfo0':{'eyeLeft':(-0.03639,0.10809,0.06409),'eyeRight':(0.03664,0.10805,0.06380),'lips':(0.00008,0.11737,-0.00582),'noseTip':(0.00019,0.14319,0.02606)},
    'pmg0':{'eyeLeft':(-0.04908,0.14371,0.09319),'eyeRight':(0.04922,0.14366,0.09322),'lips':(-0.00027,0.16482,-0.01815),'noseTip':(-0.00029,0.19558,0.04061)},
    'pfg0':{'eyeLeft':(-0.04644,0.13794,0.08179),'eyeRight':(0.04676,0.13789,0.08143),'lips':(0.00010,0.14978,-0.00742),'noseTip':(0.00024,0.18274,0.03326)},
}


def landmark_policy(config):
    """fit.landmarks: reviewed source landmarks (head-local, unscaled source units) and the race/sex base head they match."""
    require(isinstance(config,dict) and config.get('reviewed') is True,'Landmark fit needs reviewed landmarks')
    require(set(config)<={'base','calibration','source','reviewed','maximumResidual','notes'},'Unknown landmark fit key')
    table=BASE_HEADS;require(config.get('base') in table,'Landmark fit base head is not in the table')
    calibration=config.get('calibration',1.0);require(type(calibration) in (int,float) and .8<=calibration<=1.25,'Landmark calibration outside .8..1.25')
    source=config.get('source');require(isinstance(source,dict) and set(source)==set(LANDMARKS),'Landmark fit needs '+', '.join(LANDMARKS))
    a=np.asarray([source[k] for k in LANDMARKS],float);b=calibration*np.asarray([table[config['base']][k] for k in LANDMARKS],float)
    require(a.shape==(4,3) and np.isfinite(a).all(),'Landmarks are finite xyz points')
    # Eyes pair by side, not by label: a design's 'left' eye is image-left (the character's right) while the table is in
    # head_g x order, and a positive scale plus translation keeps x order, so each pair is ordered by x before the fit.
    for points in (a,b):
        if points[0,0]>points[1,0]:points[[0,1]]=points[[1,0]]
    require(a[1,0]-a[0,0]>0,'Landmark eyes must be apart in x')
    residual=config.get('maximumResidual',.006);require(type(residual) in (int,float) and 0<residual<=.01,'Landmark residual bound outside 0..1 cm')
    return a,b,residual


def landmark_fit(source, target, maximum_residual):
    """Uniform scale and translation (no rotation: the toolkit basis and yaw are kept) mapping source landmarks onto the base
    head's, least squares. Base heads are bald and ours carry hair, beards, horns and ears, so faces are matched, not outlines
    (user 2026-10-28: each race and sex has its own base head; scale heads to it)."""
    a,b=np.asarray(source,float),np.asarray(target,float);ac,bc=a-a.mean(0),b-b.mean(0)
    scale=float(np.sum(ac*bc)/np.sum(ac*ac));positive(scale,'landmark scale')
    translation=b.mean(0)-scale*a.mean(0);errors=np.linalg.norm(a*scale+translation-b,axis=1)
    require(errors.max()<=maximum_residual,f'Landmark residual {errors.max()*100:.2f} cm above {maximum_residual*100:.2f} cm; recheck the landmarks')
    return scale,translation,errors


def propose(source, reference, output, *, exclude_lower=.25, align='profile', landmarks=None):
    """align='nose' keeps the profile-matched scale but places the head by aligning nose tips (troll-male-01's
    reviewed rule against pmg0_head014), so hair, crests or a neckless reference cannot shift the placement.
    align='landmarks' scales and places the head by its reviewed face landmarks on the base head's (BASE_HEADS)."""
    require(align in ('profile','nose','landmarks'),'Fit alignment is profile, nose or landmarks')
    require((align=='landmarks')==(landmarks is not None),'fit.landmarks is read only by the landmark alignment')
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    value=mesh(source);local=head_local(surface_samples(value['positions'][value['faces']],1000000));target=ascii_surface(reference)
    if align=='landmarks':
        a,b,residual=landmark_policy(landmarks);s,translation,errors=landmark_fit(a,b,residual)
        result={'scale':s,'translation':translation.tolist(),'align':align,'base':landmarks['base'],'calibration':landmarks.get('calibration',1.0),
                'landmarkErrors':dict(zip(LANDMARKS,errors.round(5).tolist()))}
    else:
        result=match(local,target,exclude_lower=exclude_lower);s=result['scale'];result['align']=align
    result['referenceDepthRatio']=reference_depth(target,exclude_lower)  # compare candidates with `headkit fit-references`
    if align=='nose':
        # The same physical bin height and tip tolerance on both heads (0.5 mm after scaling). The source tip is searched
        # within NOSE_WINDOW of where the profile fit puts the reference nose, and nose placement may refine the profile
        # placement only by NOSE_AGREEMENT: anything further means another feature was taken for the nose.
        target_nose=nose_tip(target,.001,.0005);profiled=np.asarray(result['translation'])
        source_nose=nose_tip(local,.001/s,.0005/s,around=(target_nose[2]-profiled[2])/s,window=NOSE_WINDOW/s)
        translation=target_nose-s*source_nose;shift=float(np.linalg.norm(translation-profiled))
        require(shift<=NOSE_AGREEMENT,f'Nose and profile placements disagree by {shift*100:.1f} cm; review the fit with align profile')
        result.update(profileTranslation=result['translation'],translation=translation.tolist(),noseProfileShift=shift,
                      sourceNose=source_nose.tolist(),referenceNose=target_nose.tolist())
    matrix=np.eye(4);matrix[:3,:3]=np.diag([-s,-s,s]);matrix[:3,3]=result['translation']
    fitted=local*s+np.array(result['translation'])
    size,pad=700,max(.32,float(np.abs(target).max())*1.15);canvas=np.zeros((size,size*2,3),np.uint8)
    from scipy import ndimage
    for axes,offset in (((0,2),0),((1,2),size)):
        masks=[]
        for points in (fitted,target):
            x=((points[:,axes[0]]/pad*.5+.5)*size).astype(int);y=((.5-points[:,axes[1]]/pad*.5)*size).astype(int)
            ok=(x>=0)&(x<size)&(y>=0)&(y<size);mask=np.zeros((size,size),bool);mask[y[ok],x[ok]]=True
            masks.append(ndimage.binary_closing(mask,iterations=2))
        view=canvas[:,offset:offset+size];view[masks[0]]=(255,140,60)
        view[masks[1]&~ndimage.binary_erosion(masks[1],iterations=2)]=(70,160,255)
    image=Image.fromarray(canvas)
    draw=ImageDraw.Draw(image);cut=target[:,2].min()+exclude_lower*np.ptp(target[:,2]);yline=int((.5-cut/pad*.5)*size)
    draw.line((0,yline,size*2,yline),fill=(90,90,90));draw.text((10,10),'front: orange = proposal, blue outline = reference; grey = lower limit of matched profile',fill='white')
    draw.text((size+10,10),'side: face toward +y (right)',fill='white');image.save(output/'fit-overlay.png')
    result.update(matrix=matrix.tolist(),source=pin(source),reference=pin(reference),overlay=pin(output/'fit-overlay.png'),
                  basis='toolkit GLB->NWN (x,-z,y) source with 180-degree yaw, reference head-local',reviewRequired=True)
    write(output/'fit-proposal.json',result,fresh=True);return result
