"""Propose explicit material face ownership and skin/hair masks for review.

Color tests are confined by declared anatomical bounds. This helper never
approves its proposals; inspect atlas and assembled palette variants first.
"""
import argparse
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFilter
from head_export import triangles
from head_workflow import pin,read,require,verify_pins,write_fresh


def microface_neighbors(points, identity, original_count, omitted, maximum_distance=.001):
    """Use shared vertices, or a verified surface within one fitted millimetre."""
    adjacent=np.zeros(original_count,dtype=bool)
    for corner in points[identity]:adjacent|=(np.abs(points[:original_count]-corner)<1e-8).all(2).any(1)
    adjacent[omitted]=False;neighbors=np.flatnonzero(adjacent)
    if len(neighbors):return neighbors,0.
    candidates=np.setdiff1d(np.arange(original_count),omitted);require(len(candidates)>0,'No verified textured surface')
    tri=points[candidates];point=points[identity].mean(0);a=tri[:,0];u=tri[:,1]-a;v=tri[:,2]-a
    uu=(u*u).sum(1);uv=(u*v).sum(1);vv=(v*v).sum(1);w=point-a
    uw=(u*w).sum(1);vw=(v*w).sum(1);den=uu*vv-uv*uv;valid=den>1e-24
    s=np.divide(uw*vv-vw*uv,den,out=np.zeros_like(den),where=valid)
    t=np.divide(vw*uu-uw*uv,den,out=np.zeros_like(den),where=valid)
    projected=a+s[:,None]*u+t[:,None]*v
    distance=np.where(valid&(s>=0)&(t>=0)&(s+t<=1),((projected-point)**2).sum(1),np.inf)
    for first,last in ((0,1),(1,2),(2,0)):
        start=tri[:,first];edge=tri[:,last]-start;length=(edge*edge).sum(1)
        fraction=np.clip(np.divide(((point-start)*edge).sum(1),length,out=np.zeros_like(length),where=length>0),0,1)
        distance=np.minimum(distance,((start+fraction[:,None]*edge-point)**2).sum(1))
    index=int(distance.argmin());metres=float(np.sqrt(distance[index]))
    require(metres<=maximum_distance,'Omitted microface exceeds the verified fitted-distance bound')
    return candidates[index:index+1],metres


def choose_palette_row(values,mask,coverage,palette,layer):
    sample=values[(mask==layer)&coverage]
    require(len(sample)>0,'Missing covered palette sample')
    sample=sample[::max(1,len(sample)//10000)]
    distance=[float(((sample[:,None,:]-row[None,:,:])**2).sum(2).min(1).mean()) for row in palette]
    return int(np.argmin(distance))


def _as_path(item):
    return str(Path(item['path'] if isinstance(item, dict) else item).resolve())


def propose(config_path,output):
    c=read(config_path)
    require(c['kind']=='srn-head-mask-proposal-input','Explicit semantic proposal required')
    verify_pins(c['inputs'])
    declared={_as_path(p):p for p in c['inputs']}
    fit=read(_as_path(c['fit']))
    require(read(_as_path(c['atlasTransfer']))['atlasTransferVerified'] is True,'Atlas transfer proof required')
    correction=read(_as_path(c['correction']))
    consumed=[c['fit'],fit['source'],c['atlasTransfer'],c['correction'],
              c['baseColor'],c['metallic'],c['originalNormal'],
              c['skinPalette'],c['hairPalette']]
    if c.get('roughness'):consumed.append(c['roughness'])
    if correction.get('taperDepthMetres',0) or c.get('surfaceInheritance'):
        require(c.get('surfaceInheritance') is not None,'Surface inheritance proof required')
        consumed.append(c['surfaceInheritance'])
    for item in consumed:
        target=_as_path(item)
        require(target in declared,f'Consumed source omitted from declaration: {target}')
        if isinstance(item,dict) and 'sha256' in item:
            require(declared[target]['sha256']==item['sha256'],'Declared pin hash mismatch')
    verify_pins([declared[_as_path(item)] for item in consumed])
    if correction.get('taperDepthMetres',0):
        inheritance=read(_as_path(c['surfaceInheritance']))
        require(inheritance['passed'] is True and inheritance['source']==fit['source']
                and inheritance['originalAtlasReusable'] is True,'Revised connector needs exact upper-surface texture proof')
    p,n,uv=triangles(_as_path(fit['source']),fit['localMatrix']);center=p.mean(1)
    color=np.array(Image.open(_as_path(c['baseColor'])).convert('RGB'));require(color.shape==(2048,2048,3),'2K atlas required')
    metal=np.asarray(Image.open(_as_path(c['metallic'])).convert('L'));normal=np.array(Image.open(_as_path(c['originalNormal'])).convert('RGB'))
    pixels=np.c_[uv.mean(1)[:,0],1-uv.mean(1)[:,1]]
    pixels=np.clip(np.rint(pixels*2047).astype(int),0,2047);rgb=color[pixels[:,1],pixels[:,0]].astype(float)
    metallic=metal[pixels[:,1],pixels[:,0]]
    gray=rgb.max(1)-rgb.min(1)<28
    eye_filter=c.get('eyeColorFilter','neutral')
    require(eye_filter in ('neutral','ocular','anatomical'),'Explicit supported eye color filter required')
    ocular=rgb.max(1)-rgb.min(1)<50
    eye=np.zeros(len(p),dtype=bool)
    for bounds in c['eyeBounds']:
        low,high=np.asarray(bounds);eye|=((center>=low)&(center<=high)).all(1)&(gray if eye_filter=='neutral' else ocular if eye_filter=='ocular' else True)
    cyber=np.zeros(len(p),dtype=bool)
    for bounds in c['cyberBounds']:
        low,high=np.asarray(bounds);cyber|=((center>=low)&(center<=high)).all(1)&((metallic>80)|(rgb[:,2]>rgb[:,0]+8))
    cyber&=~eye
    horns=np.zeros(len(p),dtype=bool)
    for bounds in c.get('fixedAccessoryBounds',[]):
        low,high=np.asarray(bounds)
        require(low.shape==high.shape==(3,) and np.all(low<high), 'Explicit fixed accessory material bounds required')
        horns|=((center>=low)&(center<=high)).all(1)
    bright_accessories=np.zeros(len(p),dtype=bool)
    for bounds in c.get('brightAccessoryBounds',[]):
        low,high=np.asarray(bounds)
        require(low.shape==high.shape==(3,) and np.all(low<high), 'Explicit bright accessory bounds required')
        bright_accessories|=((center>=low)&(center<=high)).all(1)&(rgb.max(1)>200)&(rgb.min(1)>130)&(rgb.max(1)-rgb.min(1)<100)
    require(not c.get('brightAccessoryBounds') or bright_accessories.any(),'No bright accessories identified; bounds need review')
    horns|=bright_accessories
    horns&=~(eye|cyber)
    cap_regions=[]
    omitted_regions=[]
    if correction.get('kind')=='srn-head-cap-only-closure':
        require(correction['output']==fit['source'],'Cap-only proof differs from selected geometry')
        original_count=correction['inputTriangles']
        face_hair=(rgb.max(1)<100)&(rgb[:,0]-rgb[:,2]<28)&(rgb[:,1]-rgb[:,2]<22)
        for hole in correction['holes']:
            ids=hole['faces'];corners=np.unique(p[ids].reshape(-1,3),axis=0)
            adjacent=np.zeros(original_count,dtype=bool)
            for corner in corners:adjacent|=(np.abs(p[:original_count]-corner)<1e-8).all(2).any(1)
            neighbors=np.flatnonzero(adjacent);require(len(neighbors)>0,'Cap has no preserved surface neighbors')
            eye[ids]=bool(eye[neighbors].mean()>.5);cyber[ids]=bool(cyber[neighbors].mean()>.5)
            horns[ids]=bool(horns[neighbors].mean()>.5)
            layer=2 if eye[ids].any() or cyber[ids].any() or horns[ids].any() else int(face_hair[neighbors].mean()>.5)
            cap_regions.append({'faces':ids,'layer':layer,'neighborColor':np.rint(rgb[neighbors].mean(0)).astype('uint8')})
        allowance=read(_as_path(c['atlasTransfer'])).get('fittedCapOnlyAtlasAllowance') or {}
        omitted=allowance.get('omittedOriginalFaceIds',[])
        distance_limit=c.get('omittedSurfaceDistanceMetres',.001)
        require(0<distance_limit<=.005,'Microface inheritance distance exceeds five fitted millimetres')
        require(distance_limit<=.001 or allowance.get('allSourceFacesRetained'),'Extended distance requires a fitted atlas omission proof')
        for identity in omitted:
            neighbors,distance=microface_neighbors(p,identity,original_count,omitted,maximum_distance=distance_limit)
            eye[identity]=bool(eye[neighbors].mean()>.5);cyber[identity]=bool(cyber[neighbors].mean()>.5);horns[identity]=bool(horns[neighbors].mean()>.5)
            layer=2 if eye[identity] or cyber[identity] or horns[identity] else int(face_hair[neighbors].mean()>.5)
            region={'faces':[identity],'layer':layer,'neighbors':neighbors.tolist(),'distanceMetres':distance,'neighborColor':np.rint(rgb[neighbors].mean(0)).astype('uint8')}
            if c.get('roughness'):
                rough=np.asarray(Image.open(_as_path(c['roughness'])).convert('L'))
                region['neighborRoughness']=int(np.rint(rough[pixels[neighbors,1],pixels[neighbors,0]].mean()))
            omitted_regions.append(region)
    require(eye.any(),'No eyes identified; anatomical bounds need review')
    require(not c['cyberBounds'] or cyber.any(),'No cyberware identified; bounds need review')
    require(not c.get('fixedAccessoryBounds') or horns.any(),'No fixed accessories identified; bounds need review')
    groups=[{'kind':'palette','triangles':np.flatnonzero(~(eye|cyber|horns)).tolist()}]
    fixed_specs=[]
    for ids,suffix,metalness in ((eye,'e',0),(cyber,'c',1),(horns,'a',0)):
        if ids.any():fixed_specs.append({'ids':ids,'suffix':suffix,'metallicness':metalness})
    if len(fixed_specs)>2:
        # Exporter allows at most 3 groups (1 palette + 2 fixed). Merge compatible dielectric fixed regions (metallicness 0).
        dielectric=np.zeros(len(p),dtype=bool)
        other_specs=[]
        for spec in fixed_specs:
            if spec['metallicness']==0:dielectric|=spec['ids']
            else:other_specs.append(spec)
        require(dielectric.any(),'Compatible fixed dielectric regions required for merge')
        fixed_specs=[{'ids':dielectric,'suffix':'e','metallicness':0}]+other_specs
    for spec in fixed_specs:
        groups.append({'kind':'fixed','suffix':spec['suffix'],'metallicness':spec['metallicness'],
                       'triangles':np.flatnonzero(spec['ids']).tolist()})
    require(len(groups)<=3,'Generated material groups exceed exporter limit of three')
    # Dark neutral fibers are distinct from warm skin, including brows/beard.
    values=color.astype(float)
    hair=(values.max(2)<100)&(values[:,:,0]-values[:,:,2]<28)&(values[:,:,1]-values[:,:,2]<22)
    mask=np.where(hair,1,0).astype('uint8')
    fixed=Image.new('L',(2048,2048));cap=Image.new('L',(2048,2048));draw=ImageDraw.Draw(fixed);capdraw=ImageDraw.Draw(cap)
    if correction.get('kind')=='srn-head-cap-only-closure':
        require(correction['output']==fit['source'] and correction['trimApplied'] is False
                and correction['taperApplied'] is False,'Cap-only proof differs from the selected geometry')
        cap_ids=[i for hole in correction['holes'] for i in hole['faces']]
    else:
        cap_ids=correction.get('connectorFaceIds',correction.get('capFaceIds',[]))
    for i in np.flatnonzero(eye|cyber|horns):draw.polygon([tuple(row) for row in uv[i]*[2047,-2047]+[0,2047]],fill=255)
    for i in cap_ids:capdraw.polygon([tuple(row) for row in uv[i]*[2047,-2047]+[0,2047]],fill=255)
    fixed_mask=np.asarray(fixed)!=0;cap_mask=np.asarray(cap.filter(ImageFilter.MaxFilter(3)))!=0
    mask[fixed_mask]=2;mask[cap_mask]=0;normal[cap_mask]=[128,128,255]
    for region in cap_regions+omitted_regions:
        region_image=Image.new('L',(2048,2048));region_draw=ImageDraw.Draw(region_image)
        for i in region['faces']:region_draw.polygon([tuple(row) for row in uv[i]*[2047,-2047]+[0,2047]],fill=255)
        region['pixels']=np.asarray(region_image.filter(ImageFilter.MaxFilter(3)))!=0
        mask[region['pixels']]=region['layer']
    output=Path(output);require(not output.exists(),'Fresh semantic proposal required');output.mkdir(parents=True)
    Image.fromarray(mask).save(output/'semantic.png');Image.fromarray(normal).save(output/'selected-normal.png')
    labels=np.array([[212,146,104],[45,65,190],[80,210,210]],dtype=np.uint8)
    Image.fromarray(labels[mask]).save(output/'semantic-review.png')
    rows={}
    coverage_image=Image.new('L',(2048,2048));coverage_draw=ImageDraw.Draw(coverage_image)
    for face in uv:coverage_draw.polygon([tuple(row) for row in face*[2047,-2047]+[0,2047]],fill=255)
    coverage=np.asarray(coverage_image)!=0;coverage_image.save(output/'uv-coverage.png')
    for label,path in [('skin',_as_path(c['skinPalette'])),('hair',_as_path(c['hairPalette']))]:
        palette=np.asarray(Image.open(path).convert('RGB'),dtype=float)
        rows[label]=choose_palette_row(values,mask,coverage,palette,0 if label=='skin' else 1)
        Image.fromarray(palette.astype('uint8')).resize((768,len(palette)*4)).save(output/(label+'-palette.png'))
    # Legacy neck caps use skin; generic holes inherit reviewed neighboring
    # skin/hair/fixed ownership rather than the service's unused-atlas fill.
    palette=np.asarray(Image.open(_as_path(c['skinPalette'])).convert('RGB'));color[cap_mask]=palette[rows['skin'],180]
    for region in cap_regions+omitted_regions:
        if region['layer']==2:chosen=region['neighborColor']
        else:
            label='hair' if region['layer']==1 else 'skin'
            palette=np.asarray(Image.open(_as_path(c[label+'Palette'])).convert('RGB'));chosen=palette[rows[label],180]
        color[region['pixels']]=chosen
    Image.fromarray(color).save(output/'selected-color.png')
    roughness=None
    if c.get('roughness'):
        roughness=np.asarray(Image.open(_as_path(c['roughness'])).convert('L')).copy()
        require(roughness.shape==(2048,2048),'2K connector roughness required')
        roughness[cap_mask]=160;Image.fromarray(roughness).save(output/'selected-roughness.png')
        for region in omitted_regions:roughness[region['pixels']]=region['neighborRoughness']
        Image.fromarray(roughness).save(output/'selected-roughness.png')
    write_fresh(output/'proposal.json',{'kind':'srn-head-mask-proposal','config':pin(config_path),
        'mask':pin(output/'semantic.png'),'normal':pin(output/'selected-normal.png'),'color':pin(output/'selected-color.png'),
        'roughness':None if roughness is None else pin(output/'selected-roughness.png'),
        'groups':groups,'sourcePaletteRows':rows,'fixedEyeTriangles':int(eye.sum()),'fixedCyberTriangles':int(cyber.sum()),
        'fixedAccessoryTriangles':int(horns.sum()),
        'paletteSampling':'Selected UV islands only; unused service atlas fill excluded','uvCoverage':pin(output/'uv-coverage.png'),
        'skinPixels':int((mask==0).sum()),'hairPixels':int((mask==1).sum()),'fixedPixels':int((mask==2).sum()),
            'capMaterialInheritance':[{'faces':r['faces'],'layer':r['layer']} for r in cap_regions],
            'omittedOriginalMaterialInheritance':[{'faces':r['faces'],'layer':r['layer'],'neighbors':r['neighbors'],'distanceMetres':r['distanceMetres']} for r in omitted_regions],
        'maskReviewed':False,'nativeValidated':False,'clientValidated':False})
    verify_pins(c['inputs'])
    verify_pins([declared[_as_path(item)] for item in consumed])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();propose(args.config,args.output)
