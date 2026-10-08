"""Bounded original-source chart detail math for the favored ankle recipe.

Original RGB is immutable. Two declared RGB quantization phases are preserved;
AO is applied only to the final independently replayed RGB, never an intensity
parent. This module does not stage, compile, fit, select or execute old helpers.
"""
import numpy as np
import target_contract as c
from skin_lighting_atlas import pad_lineage

MODE = 'original-source-uv-detail-v1'
KIND = 'replayed-original-source-chart-detail-compiler-inputs'
BASIS = 'replayed-original-source-chart-detail-inputs'
PARTS = ('shinl','footl','shinr','footr')
LUMA = np.asarray([.2126,.7152,.0722])


def controls(value):
    c.require(isinstance(value,dict) and set(value)=={'mode','receipt','sourceManifest'}
              and value['mode']==MODE, 'Exact original-source detail mode/receipt/sourceManifest controls required')
    for key in ('receipt','sourceManifest'):
        row=value[key]
        c.require(isinstance(row,dict) and set(row)=={'path','sha256'} and isinstance(row['path'],str)
                  and isinstance(row['sha256'],str) and len(row['sha256'])==64
                  and all(x in '0123456789abcdef' for x in row['sha256']), 'Exact source-detail file pin required')


def smoothstep(x):
    t=np.clip(x,0,1); return t*t*(3-2*t)


def gaussian(a, sigma=2, radius=6):
    c.require(sigma==2 and radius==6, 'Only frozen source-detail Gaussian sigma2/radius6 supported')
    x=np.arange(-radius,radius+1); k=np.exp(-x*x/(2*sigma*sigma)); k/=k.sum(); out=a.astype(float)
    for axis in (0,1):
        padding=[(0,0)]*out.ndim; padding[axis]=(radius,radius); q=np.pad(out,padding,mode='constant'); z=np.zeros_like(out)
        for j,w in enumerate(k):
            slices=[slice(None)]*out.ndim; slices[axis]=slice(j,j+out.shape[axis]); z+=w*q[tuple(slices)]
        out=z
    return out


def chart_roots(p,uv,faces):
    p=np.asarray(p); uv=np.asarray(uv); faces=np.asarray(faces)
    c.require(p.shape==(len(uv),3) and uv.shape[1:]==(2,) and faces.ndim==2 and faces.shape[1]==3
              and faces.dtype.kind in 'iu' and faces.size and faces.min()>=0 and faces.max()<len(p)
              and np.isfinite(p).all() and np.isfinite(uv).all(), 'Finite indexed physical/UV chart source required')
    _,vid=np.unique(np.concatenate((p,uv),axis=1),axis=0,return_inverse=True); vf=vid[faces]
    edges=np.sort(np.concatenate((vf[:,[0,1]],vf[:,[1,2]],vf[:,[2,0]])),axis=1)
    ids=np.tile(np.arange(len(faces)),3); order=np.lexsort((edges[:,1],edges[:,0])); roots=np.arange(len(faces))
    def root(x):
        while roots[x]!=x: roots[x]=roots[roots[x]]; x=roots[x]
        return x
    for a,b in zip(order[:-1],order[1:]):
        if np.array_equal(edges[a],edges[b]):
            ra,rb=root(ids[a]),root(ids[b]); roots[max(ra,rb)]=min(ra,rb)
    return np.asarray([root(i) for i in range(len(faces))])


def chart_blurs(images,pixel_chart,eligible):
    c.require(len(images)==2 and all(im.shape==eligible.shape+(3,) and im.dtype==np.uint8 for im in images)
              and pixel_chart.shape==eligible.shape and eligible.dtype==bool
              and np.all(pixel_chart[eligible]>=0), 'Two original/replayed-parent RGB chart inputs required')
    value=np.concatenate([im.astype(float) for im in images],axis=2); output=np.zeros_like(value); records=[]
    for chart in np.unique(pixel_chart[eligible]):
        yy,xx=np.nonzero(eligible&(pixel_chart==chart)); y0,y1=int(yy.min()),int(yy.max())+1; x0,x1=int(xx.min()),int(xx.max())+1
        mask=eligible[y0:y1,x0:x1]&(pixel_chart[y0:y1,x0:x1]==chart)
        weight=gaussian(mask.astype(float)); numerator=gaussian(value[y0:y1,x0:x1]*mask[:,:,None]); region=output[y0:y1,x0:x1]
        region[mask]=numerator[mask]/weight[mask,None]
        records.append({'chartRootFace':int(chart),'pixels':len(yy),'bboxXY':[x0,y0,x1,y1]})
    return [output[:,:,3*i:3*(i+1)] for i in range(2)],records


def exact_periodic_nearest(st,sh,ids,qt,qh):
    st,sh,qt,qh=[np.asarray(x,float) for x in (st,sh,qt,qh)]; ids=np.asarray(ids)
    c.require(st.ndim==sh.ndim==qt.ndim==qh.ndim==ids.ndim==1 and len(st)==len(sh)==len(ids)>0
              and len(qt)==len(qh)>0 and ids.dtype.kind in 'iu' and len(np.unique(ids))==len(ids)
              and ids.min()>=0 and all(np.isfinite(x).all() for x in (st,sh,qt,qh))
              and np.all((sh>=.024)&(sh<.040)) and np.all((qh>=.024)&(qh<=.040)), 'Bounded original24..40mm donor/query cohort required')
    radius=.035; angle_bins=512; height_bins=64; da=2*np.pi/angle_bins; dh=.016/height_bins
    si=np.floor((st+np.pi)/da).astype(int)%angle_bins; sj=np.clip(np.floor((sh-.024)/dh).astype(int),0,height_bins-1); tiles={}
    for cell in np.unique(si*height_bins+sj):
        rows=np.flatnonzero(si*height_bins+sj==cell); tiles[int(cell)]=rows[np.argsort(ids[rows])]
    qi=np.floor((qt+np.pi)/da).astype(int)%angle_bins; qj=np.clip(np.floor((qh-.024)/dh).astype(int),0,height_bins-1)
    found=np.empty(len(qi),dtype='i8'); errors=np.empty(len(qi)); source=np.c_[radius*np.cos(st),radius*np.sin(st),sh]
    query=np.c_[radius*np.cos(qt),radius*np.sin(qt),qh]; maxsearch=0
    for cell in np.unique(qi*height_bins+qj):
        target=np.flatnonzero(qi*height_bins+qj==cell); cx,cy=divmod(int(cell),height_bins)
        for reach in range(1,33):
            rows=[tiles[x*height_bins+y] for x in sorted({(cx+dx)%angle_bins for dx in range(-reach,reach+1)})
                  for y in range(max(0,cy-reach),min(height_bins,cy+reach+1)) if x*height_bins+y in tiles]
            if not rows: continue
            choices=np.concatenate(rows); choices=choices[np.argsort(ids[choices])]
            dist=((query[target,None,:]-source[choices][None,:,:])**2).sum(2); best=dist.argmin(1); chosen=choices[best]
            error=np.sqrt(dist[np.arange(len(best)),best]); escape=min(2*radius*np.sin(reach*da/2),reach*dh)
            if error.max()<=escape:
                found[target]=ids[chosen]; errors[target]=error; maxsearch=max(maxsearch,reach); break
        else: raise ValueError('Original body detail lookup unsupported beyond32tiles')
    c.require(errors.max()<.001, 'Original body donor metric exceeds frozen1mm bound')
    return found,errors,maxsearch


def atlas_arrays(original,height,masks):
    c.require(original.dtype==np.uint8 and original.ndim==3 and original.shape[2]==3
              and height.shape==original.shape[:2] and np.isfinite(height).all(), 'Original byteRGB/finiteheight atlas required')
    for key in ('coverage','protected'):
        c.require(masks[key].shape==height.shape and masks[key].dtype==bool,'Explicit original coverage/protection required')
    return masks['coverage']&~masks['protected']


def common_tone(original,height,masks,part,body,band,target,cap):
    c.require(part in ('shinl','footl'), 'Original left skin donor required')
    eligible=atlas_arrays(original,height,masks); body,band,target,cap=[np.asarray(x,float) for x in (body,band,target,cap)]
    c.require(all(x.shape==(3,) and np.isfinite(x).all() and (x>0).all() for x in (body,band,target,cap)), 'Measured positive RGB statistics required')
    weight=1-smoothstep((height-.012)/.008) if part=='shinl' else smoothstep(height/.010); value=original.astype(float)
    if part=='shinl':
        delta=band[1:]/band[0]-body[1:]/body[0]; c.require(delta@delta>1e-15,'Nonempty measured pigment correction required')
        chroma=original[:,:,1:].astype(float)/np.maximum(original[:,:,0:1].astype(float),1)
        amount=np.clip(((chroma-body[1:]/body[0])*delta).sum(2)/(delta@delta),0,1)
        value[:,:,1:]-=original[:,:,0:1].astype(float)*delta*amount[:,:,None]*weight[:,:,None]; value*=target/body
    else: value*=1+weight[:,:,None]*(target/cap-1)
    result=original.copy(); result[eligible]=np.rint(np.clip(value[eligible],0,255)).astype('u1')
    lineage,distance,padding=pad_lineage(masks['coverage'],masks['protected'],4)
    result[padding]=result.reshape(-1,3)[lineage[padding]]
    c.require(np.array_equal(result[masks['protected']],original[masks['protected']]), 'Protected originalRGB changed')
    return result,{'sourceHeight':height,'coverage':masks['coverage'],'protected':masks['protected'],'eligible':eligible,
                   'weight':weight,'lineage':lineage,'distance':distance,'paddingDestination':padding}


def detail_transfer(original,parent,height,masks,shaft,centre,face_roots,owner_face,gain):
    eligible=atlas_arrays(original,height,masks); c.require(parent.shape==original.shape and parent.dtype==np.uint8,'Replayed common-toneRGB parent required')
    c.require(shaft.shape==height.shape+(3,) and centre.shape==(2,) and owner_face.shape==height.shape
              and np.isfinite(shaft).all() and np.isfinite(centre).all() and owner_face[masks['coverage']].min()>=0
              and owner_face[masks['coverage']].max()<len(face_roots),'Explicit original geometry/face atlas required')
    pixel_chart=np.full(height.shape,-1,dtype='i4');pixel_chart[masks['coverage']]=face_roots[owner_face[masks['coverage']]]
    (ob,pb),records=chart_blurs([original,parent],pixel_chart,eligible); hp=original.astype(float)-ob; php=parent.astype(float)-pb
    theta=np.arctan2(shaft[:,:,1]-centre[1],shaft[:,:,0]-centre[0]);radial=np.linalg.norm(shaft[:,:,:2]-centre,axis=2)
    weight=(1-smoothstep((height-.012)/.008))*smoothstep((radial-.008)/.004);weight[~eligible]=0
    target=eligible&(weight>0);donors=eligible&(height>=.024)&(height<.040)&(radial>.010);tids=np.flatnonzero(target);sids=np.flatnonzero(donors)
    c.require(len(tids)>0 and len(sids)>0,'Nonempty original source detail/target cohorts required')
    goal=.024+.016*smoothstep((height.ravel()[tids]+.014)/.034)
    ids,errors,maxreach=exact_periodic_nearest(theta.ravel()[sids],height.ravel()[sids],sids,theta.ravel()[tids],goal)
    gain=np.asarray(gain,float);c.require(gain.shape==(3,) and np.isfinite(gain).all() and (gain>0).all(),'Measured original common-tone gain required')
    values=parent.astype(float);values.reshape(-1,3)[tids]+=weight.ravel()[tids,None]*(hp.reshape(-1,3)[ids]*gain-php.reshape(-1,3)[tids])
    result=parent.copy();result[target]=np.rint(np.clip(values[target],0,255)).astype('u1')
    lineage,distance,padding=pad_lineage(masks['coverage'],masks['protected'],4);result[padding]=result.reshape(-1,3)[lineage[padding]]
    c.require(np.array_equal(result[masks['protected']],parent[masks['protected']])
              and np.array_equal(result[masks['coverage']&~target],parent[masks['coverage']&~target]),'Original protected/outside detail support changed')
    lookup=np.full(height.shape,-1,dtype='i4');lookup.ravel()[tids]=ids
    donor_uv=np.full(height.shape+(2,),np.nan,dtype='f4');size=height.shape[0]
    c.require(height.shape==(size,size),'Square atlas required')
    donor_uv.reshape(-1,2)[tids]=np.c_[ids%size+.5,ids//size+.5]/size
    error_image=np.zeros(height.shape,dtype='f4');error_image.ravel()[tids]=errors
    goal_image=np.zeros(height.shape,dtype='f4');goal_image.ravel()[tids]=goal
    arrays={'sourceFaceChartRoots':face_roots,'sourcePixelChartRoot':pixel_chart,'sourceHeight':height,
            'coverage':masks['coverage'],'protected':masks['protected'],'weight':weight,'targetMask':target,'donorMask':donors,
            'donorSourcePixelId':lookup,'donorOriginalUV':donor_uv,'donorHeightGoal':goal_image,'lookupPhysicalMetricError':error_image,
            'originalSourceHighpassRGB':hp,'parentHighpassRGB':php,'paddingSourcePixelId':lineage,
            'paddingDistance':distance,'paddingDestination':padding}
    return result,arrays,records,{'maximumLookupMetricErrorMeters':float(errors.max()),'maximumSearchedTileRadius':maxreach,
                                'originalDonorPixels':len(sids),'targetPixels':len(tids)}


def match_arrays(recorded,expected):
    c.require(set(recorded)==set(expected),'Source detail atlas inventory differs')
    for key,value in expected.items():
        c.require(np.array_equal(recorded[key],value,equal_nan=True),'Source detail mathematical replay differs: '+key)


def intensity(color,ao_red,ao_strength):
    c.require(not isinstance(ao_strength,bool) and ao_strength in (0,.15,.35),'Original AO strength must be0/.15/.35')
    c.require(color.dtype==ao_red.dtype==np.uint8 and color.shape==ao_red.shape+(3,),'Original byteRGB/AO atlas required')
    return ((color.astype(float)@LUMA)*(1-ao_strength*(1-ao_red.astype(float)/255))).clip(0,255).astype('u1')