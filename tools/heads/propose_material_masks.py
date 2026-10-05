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


def choose_palette_row(values,mask,coverage,palette,layer):
    sample=values[(mask==layer)&coverage]
    require(len(sample)>0,'Missing covered palette sample')
    sample=sample[::max(1,len(sample)//10000)]
    distance=[float(((sample[:,None,:]-row[None,:,:])**2).sum(2).min(1).mean()) for row in palette]
    return int(np.argmin(distance))


def propose(config_path,output):
    c=read(config_path);verify_pins(c['inputs']);fit=read(c['fit']['path'])
    require(c['kind']=='srn-head-mask-proposal-input','Explicit semantic proposal required')
    require(read(c['atlasTransfer']['path'])['atlasTransferVerified'] is True,'Atlas transfer proof required')
    correction=read(c['correction']['path'])
    if correction.get('taperDepthMetres',0):
        verify_pins([c['surfaceInheritance']]);inheritance=read(c['surfaceInheritance']['path'])
        require(inheritance['passed'] is True and inheritance['source']==fit['source']
                and inheritance['originalAtlasReusable'] is True,'Revised connector needs exact upper-surface texture proof')
    p,n,uv=triangles(fit['source']['path'],fit['localMatrix']);center=p.mean(1)
    color=np.array(Image.open(c['baseColor']).convert('RGB'));require(color.shape==(2048,2048,3),'2K atlas required')
    metal=np.asarray(Image.open(c['metallic']).convert('L'));normal=np.array(Image.open(c['originalNormal']).convert('RGB'))
    pixels=np.c_[uv.mean(1)[:,0],1-uv.mean(1)[:,1]]
    pixels=np.clip(np.rint(pixels*2047).astype(int),0,2047);rgb=color[pixels[:,1],pixels[:,0]].astype(float)
    metallic=metal[pixels[:,1],pixels[:,0]]
    gray=rgb.max(1)-rgb.min(1)<28
    eye=np.zeros(len(p),dtype=bool)
    for bounds in c['eyeBounds']:
        low,high=np.asarray(bounds);eye|=((center>=low)&(center<=high)).all(1)&gray
    cyber=np.zeros(len(p),dtype=bool)
    for bounds in c['cyberBounds']:
        low,high=np.asarray(bounds);cyber|=((center>=low)&(center<=high)).all(1)&((metallic>80)|(rgb[:,2]>rgb[:,0]+8))
    cyber&=~eye
    cap_regions=[]
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
            layer=2 if eye[ids].any() or cyber[ids].any() else int(face_hair[neighbors].mean()>.5)
            cap_regions.append({'faces':ids,'layer':layer,'neighborColor':np.rint(rgb[neighbors].mean(0)).astype('uint8')})
    groups=[{'kind':'palette','triangles':np.flatnonzero(~(eye|cyber)).tolist()}]
    for ids,suffix,metalness in ((eye,'e',0),(cyber,'c',1)):
        if ids.any():groups.append({'kind':'fixed','suffix':suffix,'metallicness':metalness,'triangles':np.flatnonzero(ids).tolist()})
    require(eye.any(),'No eyes identified; anatomical bounds need review')
    require(not c['cyberBounds'] or cyber.any(),'No cyberware identified; bounds need review')
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
    for i in np.flatnonzero(eye|cyber):draw.polygon([tuple(row) for row in uv[i]*[2047,-2047]+[0,2047]],fill=255)
    for i in cap_ids:capdraw.polygon([tuple(row) for row in uv[i]*[2047,-2047]+[0,2047]],fill=255)
    fixed_mask=np.asarray(fixed)!=0;cap_mask=np.asarray(cap.filter(ImageFilter.MaxFilter(3)))!=0
    mask[fixed_mask]=2;mask[cap_mask]=0;normal[cap_mask]=[128,128,255]
    for region in cap_regions:
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
    for label,path in [('skin',c['skinPalette']),('hair',c['hairPalette'])]:
        palette=np.asarray(Image.open(path).convert('RGB'),dtype=float)
        rows[label]=choose_palette_row(values,mask,coverage,palette,0 if label=='skin' else 1)
        Image.fromarray(palette.astype('uint8')).resize((768,len(palette)*4)).save(output/(label+'-palette.png'))
    # Legacy neck caps use skin; generic holes inherit reviewed neighboring
    # skin/hair/fixed ownership rather than the service's unused-atlas fill.
    palette=np.asarray(Image.open(c['skinPalette']).convert('RGB'));color[cap_mask]=palette[rows['skin'],180]
    for region in cap_regions:
        if region['layer']==2:chosen=region['neighborColor']
        else:
            label='hair' if region['layer']==1 else 'skin'
            palette=np.asarray(Image.open(c[label+'Palette']).convert('RGB'));chosen=palette[rows[label],180]
        color[region['pixels']]=chosen
    Image.fromarray(color).save(output/'selected-color.png')
    roughness=None
    if c.get('roughness'):
        roughness=np.asarray(Image.open(c['roughness']).convert('L')).copy()
        require(roughness.shape==(2048,2048),'2K connector roughness required')
        roughness[cap_mask]=160;Image.fromarray(roughness).save(output/'selected-roughness.png')
    write_fresh(output/'proposal.json',{'kind':'srn-head-mask-proposal','config':pin(config_path),
        'mask':pin(output/'semantic.png'),'normal':pin(output/'selected-normal.png'),'color':pin(output/'selected-color.png'),
        'roughness':None if roughness is None else pin(output/'selected-roughness.png'),
        'groups':groups,'sourcePaletteRows':rows,'fixedEyeTriangles':int(eye.sum()),'fixedCyberTriangles':int(cyber.sum()),
        'paletteSampling':'Selected UV islands only; unused service atlas fill excluded','uvCoverage':pin(output/'uv-coverage.png'),
        'skinPixels':int((mask==0).sum()),'hairPixels':int((mask==1).sum()),'fixedPixels':int((mask==2).sum()),
        'capMaterialInheritance':[{'faces':r['faces'],'layer':r['layer']} for r in cap_regions],
        'maskReviewed':False,'nativeValidated':False,'clientValidated':False})
    verify_pins(c['inputs'])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();propose(args.config,args.output)
