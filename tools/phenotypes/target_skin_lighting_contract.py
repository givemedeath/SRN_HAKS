"""Target-bound diagnostic skin-lighting inputs and conservative atlas protection.

This interface does not stage or select materials. Every variant starts from the
same untreated fitted GLB; garments, measured connector bands and dependencies
remain protected. The original source is never an output of this operation.
"""
from io import BytesIO
import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import target_contract as contract
from target_part_pipeline import pin, read_target, verify_source_receipt
from place_purposebuilt_pelvis import read_glb, raw_corners, embedded_maps

LUMA=np.asarray([.2126,.7152,.0722])


def finite(value, low, high, label):
    contract.require(not isinstance(value,bool) and isinstance(value,(int,float)) and
        np.isfinite(value) and low<=value<=high,'Invalid bounded '+label)


def validate_controls(config):
    allowed={'schemaVersion','kind','diagnosticOnly','targetContract','targetContractSha256',
      'part','coordinateSpace','source','sourceSha256','sourceReceipt','sourceReceiptSha256',
      'materialRoles','normalInputReview','protectedInputs','protectedRegions','lighting',
      'treatment','palette','referenceStyle','notes'}
    contract.require(set(config)<=allowed and allowed-{'notes'}<=set(config),'Missing or unknown skin-lighting control')
    contract.require(config.get('schemaVersion')==2 and config.get('kind')=='target-skin-lighting-diagnostic'
        and config.get('diagnosticOnly') is True,'Explicit diagnostic v2 skin-lighting configuration required')
    contract.require(config.get('coordinateSpace')=='working' and config.get('part') in contract.BODY_PARTS,
        'Working body part required; head/neck cannot be treated')
    contract.require(isinstance(config.get('protectedInputs'),dict) and config['protectedInputs'],
        'Explicit protected neighboring/stock inputs required')
    lighting=config['lighting']
    contract.require(set(lighting)=={'frame','device','resolution','samples','seed','worldStrength','marginPixels','lights'},
        'Explicit frozen lighting inventory required')
    contract.require(lighting['frame']=='target-world-bind' and lighting['device']=='CPU' and lighting['resolution']==2048,
        'CPU target-world bind lighting and 2K atlas required')
    finite(lighting['samples'],16,256,'samples');finite(lighting['seed'],0,2**31-1,'bake seed')
    contract.require(isinstance(lighting['samples'],int) and isinstance(lighting['seed'],int),'Integer samples/seed required')
    finite(lighting['worldStrength'],0,.25,'world strength');finite(lighting['marginPixels'],0,32,'margin pixels')
    contract.require(isinstance(lighting['marginPixels'],int),'Integer margin required')
    lights=lighting['lights'];contract.require(isinstance(lights,list) and 1<=len(lights)<=8,'One to eight explicit lights required')
    identifiers=set()
    for light in lights:
        contract.require(set(light)=={'id','type','positionWorld','energy','sizeMeters'} and light['type']=='AREA',
            'Neutral AREA lights only; no camera-derived light direction')
        contract.require(isinstance(light['id'],str) and light['id'] not in identifiers,'Unique light IDs required');identifiers.add(light['id'])
        position=np.asarray(light['positionWorld'],float)
        contract.require(position.shape==(3,) and np.isfinite(position).all(),'Finite light position required')
        finite(light['energy'],.01,10000,'light energy');finite(light['sizeMeters'],.01,10,'light size')
    regions=config['protectedRegions'];contract.require(isinstance(regions,list) and 1<=len(regions)<=8,
        'Measured connector/neck protection regions required')
    for region in regions:
        contract.require(set(region)=={'label','originLocal','normalLocal','halfWidthMeters','fadeWidthMeters'},
            'Explicit measured protection plane required')
        origin=np.asarray(region['originLocal'],float);normal=np.asarray(region['normalLocal'],float)
        contract.require(origin.shape==normal.shape==(3,) and np.isfinite(origin).all() and np.isfinite(normal).all()
            and abs(np.linalg.norm(normal)-1)<1e-9,'Unit finite protection plane required')
        finite(region['halfWidthMeters'],.001,.1,'protected half width');finite(region['fadeWidthMeters'],.001,.1,'protected fade width')
    treatment=config['treatment']
    contract.require(set(treatment)=={'strengths','maxDarkenShades','maxBrightenShades','normalization','maskGuardPixels'},
        'Explicit non-cumulative bounded treatment required')
    contract.require(treatment['normalization']=='surface-area-weighted-mean','Area-weighted normalization required')
    values=treatment['strengths'];contract.require(isinstance(values,list) and 2<=len(values)<=6 and values[0]==0,
        'Untreated zero and independent comparison strengths required')
    for value in values:finite(value,0,1,'lighting strength')
    contract.require(values==sorted(set(values)),'Sorted unique strengths required')
    finite(treatment['maxDarkenShades'],0,96,'darkening');finite(treatment['maxBrightenShades'],0,96,'brightening')
    finite(treatment['maskGuardPixels'],1,4,'mask guard');contract.require(isinstance(treatment['maskGuardPixels'],int),'Integer mask guard required')
    contract.require(config['palette'].get('rows')==[3,8],'Matched palette3/8 diagnostics required')
    review=config['normalInputReview']
    contract.require(set(review)=={'path','sha256','status'} and review['status'] in
        ('diagnostic-reviewed','diagnostic-with-known-defects'),'Pinned diagnostic normal-input review required')


def texture_blob(doc,binary,binding):
    contract.require(binding.get('texCoord',0)==0 and not binding.get('extensions'),'Original TEXCOORD_0 bindings required')
    texture=doc['textures'][binding['index']]
    contract.require(not texture.get('extensions'),'Texture extension unsupported')
    image=doc['images'][texture['source']]
    contract.require('bufferView' in image and not image.get('uri') and image.get('mimeType')=='image/png','Original embedded PNG map required')
    view=doc['bufferViews'][image['bufferView']];contract.require(view.get('buffer',0)==0,'External map unsupported')
    start=view.get('byteOffset',0);blob=binary[start:start+view['byteLength']]
    pixels=np.asarray(Image.open(BytesIO(blob)).convert('RGB'))
    contract.require(pixels.shape==(2048,2048,3),'Original 2K maps required')
    return blob,pixels


def prepare(config_path):
    path=Path(config_path).resolve();config=json.loads(path.read_text(encoding='utf-8'));validate_controls(config)
    target_path,target=read_target(config);part=config['part'];source=pin(config['source'],config['sourceSha256'])
    receipt_path=pin(config['sourceReceipt'],config['sourceReceiptSha256'])
    parent=verify_source_receipt(source,receipt_path,target_path,target,part,'working')
    review_path=pin(config['normalInputReview']['path'],config['normalInputReview']['sha256'])
    review=json.loads(review_path.read_text(encoding='utf-8'))
    contract.require(review.get('targetId')==target['id'] and review.get('source',{}).get('sha256') in
        (contract.sha(source),parent['sourceSha256']),'Normal review belongs to another target/source')
    frozen={str(p):contract.sha(p) for p in (path,target_path,source,receipt_path,review_path,Path(__file__).resolve())}
    for p,expected in {**parent['frozenInputs'],**config['protectedInputs']}.items():frozen[str(pin(p,expected))]=expected
    for entry in (config['palette'],config['referenceStyle']):
        p=pin(entry['path'],entry['sha256']);frozen[str(p)]=entry['sha256']
    doc,binary=read_glb(source);extra={};positions,normals,uv,primitives=raw_corners(doc,binary,extra=extra)
    contract.require(doc['nodes']==[{'name':'detached_geometry','mesh':0}],'Canonical fitted geometry required')
    contract.require('TANGENT' in extra and len(extra['TANGENT']['triangleIndices'])==len(positions),
        'Complete authored tangent basis required; never regenerate Mikk tangents')
    tangents=np.concatenate(extra['TANGENT']['rows']);contract.require(tangents.shape==positions.shape[:2]+(4,),
        'Authored corner tangent count differs')
    roles={int(k):v for k,v in config['materialRoles'].items()}
    active={p['material'] for p in primitives}
    contract.require(set(roles)==active and set(roles.values())<={'skin','garment'} and 'skin' in roles.values(),
        'Exact active skin/garment ownership required')
    garment_parts=contract.fixed_garment_parts(target)
    contract.require('garment' not in roles.values() or part in garment_parts,'Garment outside declared owners')
    if contract.rig_mode(target)=='stock-exact' and part in garment_parts:
        contract.require('garment' in roles.values(),'Required owner garment cannot be hidden')
    materials={};triangle_roles=[];reference=None
    for row in primitives:triangle_roles.extend([roles[row['material']]]*row['triangles'])
    for material_id,role in roles.items():
        material=doc['materials'][material_id];pbr=material['pbrMetallicRoughness']
        contract.require(material.get('alphaMode','OPAQUE')=='OPAQUE' and pbr.get('baseColorFactor',[1,1,1,1])==[1,1,1,1],
            'Opaque unmodified source material required')
        contract.require(material['normalTexture'].get('scale',1)==1,'Original normal strength one required')
        maps={name:texture_blob(doc,binary,binding) for name,binding in
            (('color',pbr['baseColorTexture']),('normal',material['normalTexture']),('orm',pbr['metallicRoughnessTexture']))}
        if role=='skin':
            if reference is None:reference=maps['color'][1]
            else:contract.require(np.array_equal(reference,maps['color'][1]),'Skin materials require one untreated atlas')
        materials[material_id]={'role':role,'maps':maps,'sourceMaterial':material}
    original=(reference.astype(float)@LUMA).clip(0,255).astype(np.uint8)
    return dict(configPath=path,config=config,targetPath=target_path,target=target,source=source,
        sourceReceipt=receipt_path,parent=parent,frozenInputs=frozen,doc=doc,binary=binary,positions=positions,
        normals=normals,uv=uv,tangents=tangents,primitives=primitives,triangleRoles=triangle_roles,
        materials=materials,originalIntensity=original,originalEmbeddedMaps=embedded_maps(doc,binary))


def masks(positions,uv,roles,size,regions,guard=2):
    contract.require(positions.shape==uv.shape[:2]+(3,) and len(positions)==len(roles),'Mask geometry/role association differs')
    contract.require(np.isfinite(positions).all() and np.isfinite(uv).all() and uv.min()>=-1e-6 and uv.max()<=1+1e-6,
        'Wrapped/nonfinite UV requires separate review')
    coverage=Image.new('L',(size,size));cloth=Image.new('L',(size,size));influence=Image.new('L',(size,size));protect=Image.new('L',(size,size))
    cd,gd,idraw,pd=[ImageDraw.Draw(i) for i in (coverage,cloth,influence,protect)]
    values=np.ones(len(positions))
    for region in regions:
        n=np.asarray(region['normalLocal']);origin=np.asarray(region['originLocal']);distance=(positions-origin)@n
        low,high=distance.min(1),distance.max(1)
        straddle=(low<=region['halfWidthMeters'])&(high>=-region['halfWidthMeters'])
        closest=np.minimum(abs(low),abs(high));weight=np.clip((closest-region['halfWidthMeters'])/region['fadeWidthMeters'],0,1)
        weight[straddle]=0;values=np.minimum(values,weight)
    polys=[[(float(u)*(size-1),float(v)*(size-1)) for u,v in coords] for coords in np.clip(uv,0,1)]
    for index in np.argsort(-values,kind='stable'):
        polygon=polys[index];cd.polygon(polygon,fill=255)
        if roles[index]=='garment':gd.polygon(polygon,fill=255);pd.polygon(polygon,fill=255)
        elif roles[index]=='skin':
            value=int(round(values[index]*255));idraw.polygon(polygon,fill=value)
            if value==0:pd.polygon(polygon,fill=255)
        else:raise ValueError('Undeclared mask role')
    protected=np.asarray(protect.filter(ImageFilter.MaxFilter(guard*2+1)))>0
    garment=np.asarray(cloth)>0;used=np.asarray(coverage)>0
    field=np.asarray(influence.filter(ImageFilter.GaussianBlur(.6)),dtype=float)/255
    field[protected|garment|~used]=0
    return field,used,garment,protected


def sample(image,uv):
    height,width=image.shape[:2];xy=np.clip(uv,0,1)*np.array([width-1,height-1]);# Raw GLTF V already addresses top-left rows; no second flip.
    x,y=xy[:,0],xy[:,1];x0=np.floor(x).astype(int);y0=np.floor(y).astype(int);x1=np.minimum(x0+1,width-1);y1=np.minimum(y0+1,height-1)
    a=x-x0;b=y-y0
    return image[y0,x0]*(1-a)*(1-b)+image[y0,x1]*a*(1-b)+image[y1,x0]*(1-a)*b+image[y1,x1]*a*b


def surface_samples(positions,uv,roles):
    weights=np.linalg.norm(np.cross(positions[:,1]-positions[:,0],positions[:,2]-positions[:,0]),axis=1)/2
    skin=np.asarray(roles)=='skin';contract.require(skin.any() and (weights[skin]>0).all(),'Nondegenerate skin surface required')
    bary=np.asarray([[1/3]*3,[.6,.2,.2],[.2,.6,.2],[.2,.2,.6]])
    samples=np.einsum('sc,tcv->tsv',bary,uv[skin]).reshape(-1,2)
    return samples,np.repeat(weights[skin]/4,4)


def normalized_lighting(raw_rgb,uv_samples,weights):
    contract.require(raw_rgb.ndim==3 and raw_rgb.shape[2]==3 and np.isfinite(raw_rgb).all() and raw_rgb.min()>=-1e-7,
        'Finite nonnegative linear diffuse bake required')
    raw=np.maximum(raw_rgb,0)@LUMA;mean=float(np.average(sample(raw,uv_samples),weights=weights))
    contract.require(np.isfinite(mean) and mean>1e-8,'Empty/unlit atlas cannot define treatment')
    return raw/mean,mean


def compose(original,field,influence,garment,protected,strength,darken,brighten):
    finite(strength,0,1,'lighting strength');finite(darken,0,96,'darkening');finite(brighten,0,96,'brightening')
    contract.require(original.dtype==np.uint8 and original.ndim==2 and all(np.shape(a)==original.shape for a in
        (field,influence,garment,protected)),'Intensity field/protection shape differs')
    contract.require(np.isfinite(field).all() and (field>=0).all() and np.isfinite(influence).all() and
        (influence>=0).all() and (influence<=1).all(),'Invalid intensity/influence field')
    contract.require(garment.dtype==np.bool_ and protected.dtype==np.bool_,'Boolean protection masks required')
    delta=np.clip(original.astype(float)*(field-1),-darken,brighten)*strength*influence
    result=np.rint(original.astype(float)+delta).clip(0,255).astype(np.uint8)
    blocked=np.logical_or(garment,protected)| (influence==0);result[blocked]=original[blocked]
    contract.require(np.array_equal(result[blocked],original[blocked]),'Protected garment/connector changed')
    contract.require(np.max(abs(result.astype(int)-original.astype(int)))<=np.ceil(max(darken,brighten)*strength),
        'Bounded intensity change exceeded')
    return result


def weighted_stats(image,uv_samples,weights):
    values=sample(image.astype(float),uv_samples);order=np.argsort(values);v=values[order];w=weights[order];cdf=np.cumsum(w)/w.sum()
    mean=float(np.average(values,weights=weights));p05,p95=np.interp([.05,.95],cdf,v)
    return {'mean':mean,'std':float(np.sqrt(np.average((values-mean)**2,weights=weights))),
        'p05':float(p05),'p95':float(p95),'p05P95Span':float(p95-p05),'relativeSpan':float((p95-p05)/max(mean,1e-9)),
        'minimum':float(values.min()),'maximum':float(values.max())}

