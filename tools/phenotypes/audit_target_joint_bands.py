"""Read-only joint-band source color/PLT shade measurements in declared frames.

Deterministic area samples and bidirectional spatial/normal matching are offline
diagnostics. They include potentially hidden surfaces and never select recoloring,
change maps, accept a connector or claim observed client continuity.
"""
import argparse
import hashlib
from itertools import product
import json
from pathlib import Path
import re
import shutil
import struct

import numpy as np
from PIL import Image

import target_contract as contract
from audit_geometry import arrays
from place_purposebuilt_pelvis import raw_corners, read_glb
from target_part_pipeline import pin, read_target, verify_source_receipt
from target_part_stage import image_pixels


BARYCENTRIC = np.asarray([[1/3,1/3,1/3],[.6,.2,.2],[.2,.6,.2],[.2,.2,.6]])


def sample_pixels(image, uv, wrap_s=10497, wrap_t=10497):
    """Top-left raw glTF UV, bilinear base-level byte values at texel centers.

    This measures original bytes; it does not model gamma-correct filtering or
    mipmapping performed by an actual client.
    """
    image = np.asarray(image); uv = np.asarray(uv,dtype=float)
    contract.require(image.ndim in (2,3) and uv.ndim == 2 and uv.shape[1] == 2 and
                     np.isfinite(uv).all(), 'Finite raw material UV samples required')
    if image.ndim == 2: image = image[...,None]
    height,width = image.shape[:2]
    def indices(coordinate, size, wrap):
        contract.require(wrap in (10497,33071,33648), 'Unsupported material texture wrapping')
        if wrap == 33648:
            unit = np.mod(coordinate,2); coordinate = np.where(unit <= 1,unit,2-unit)
        elif wrap == 33071: coordinate = np.clip(coordinate,0,1)
        position = coordinate*size-.5; first = np.floor(position).astype(int); fraction = position-first
        second = first+1
        if wrap == 10497: first,second = first%size,second%size
        else: first,second = np.clip(first,0,size-1),np.clip(second,0,size-1)
        return first,second,fraction
    x0,x1,fx = indices(uv[:,0],width,wrap_s); y0,y1,fy = indices(uv[:,1],height,wrap_t)
    return (image[y0,x0]*(1-fx)[:,None]*(1-fy)[:,None]+image[y0,x1]*fx[:,None]*(1-fy)[:,None]+
            image[y1,x0]*(1-fx)[:,None]*fy[:,None]+image[y1,x1]*fx[:,None]*fy[:,None])


def samples(p,n,uv,materials,frame):
    p,n,uv = np.asarray(p),np.asarray(n),np.asarray(uv)
    contract.require(p.ndim == 3 and p.shape[1:] == (3,3) and n.shape == p.shape and
                     uv.shape == (*p.shape[:2],2) and len(materials) == len(p), 'Ordered triangle samples required')
    world = p@frame[:3,:3].T+frame[:3,3]; normals = n@frame[:3,:3].T
    area = np.linalg.norm(np.cross(world[:,1]-world[:,0],world[:,2]-world[:,0]),axis=1)/2
    contract.require((area > 0).all(), 'Zero-area source triangle in joint audit')
    return {'world':np.einsum('bc,tci->tbi',BARYCENTRIC,world).reshape(-1,3),
            'normal':np.einsum('bc,tci->tbi',BARYCENTRIC,normals).reshape(-1,3),
            'uv':np.einsum('bc,tci->tbi',BARYCENTRIC,uv).reshape(-1,2),
            'weight':np.repeat(area/len(BARYCENTRIC),len(BARYCENTRIC)),
            'triangle':np.repeat(np.arange(len(p)),len(BARYCENTRIC)),
            'barycentricIndex':np.tile(np.arange(len(BARYCENTRIC)),len(p)),
            'material':np.repeat(materials,len(BARYCENTRIC))}


def band_mask(points,anchor,axis,interval,radius):
    anchor,axis,interval = np.asarray(anchor,float),np.asarray(axis,float),np.asarray(interval,float)
    contract.require(anchor.shape == (3,) and axis.shape == (3,) and interval.shape == (2,) and
                     all(np.isfinite(value).all() for value in [anchor,axis,interval]) and
                     interval[0] < interval[1] and np.isfinite(radius) and radius > 0,
                     'Finite explicit cylindrical joint band required')
    length = np.linalg.norm(axis); contract.require(length > 0, 'Distinct axis joints required')
    axis = axis/length; delta = points-anchor; axial = delta@axis
    radial = np.linalg.norm(delta-axial[:,None]*axis,axis=1)
    return (axial >= interval[0])&(axial <= interval[1])&(radial <= radius)


def percentile(values,weights,quantiles=(.05,.5,.95)):
    order = np.argsort(values); values,weights = values[order],weights[order]
    distribution = (np.cumsum(weights)-weights*.5)/weights.sum()
    return np.interp(quantiles,distribution,values).tolist()


def statistics(values,weights):
    values,weights = np.asarray(values,float),np.asarray(weights,float)
    if values.ndim == 1: values = values[:,None]
    contract.require(len(values) == len(weights) and len(values) and np.isfinite(values).all() and
                     np.isfinite(weights).all() and (weights > 0).all(), 'Nonempty finite positive-area samples required')
    mean = np.average(values,axis=0,weights=weights)
    return {'samples':len(values),'representedAreaSquareMetres':float(weights.sum()),'mean':mean.tolist(),
            'std':np.sqrt(np.average((values-mean)**2,axis=0,weights=weights)).tolist(),
            'minimum':values.min(axis=0).tolist(),'maximum':values.max(axis=0).tolist(),
            'p05MedianP95PerChannel':[percentile(values[:,index],weights) for index in range(values.shape[1])]}


def match(source,target,distance_limit,minimum_normal_cosine,neighbors):
    contract.require(np.isfinite(distance_limit) and distance_limit > 0 and
                     np.isfinite(minimum_normal_cosine) and -1 <= minimum_normal_cosine <= 1 and
                     type(neighbors) is int and 1 <= neighbors <= 64, 'Explicit bounded geometric matching policy required')
    contract.require(len(source['world']) and len(target['world']), 'Empty spatial band cannot prove continuity')
    contract.require(np.isfinite(source['world']).all() and np.isfinite(target['world']).all(), 'Finite world samples required')
    sn,tn = source['normal'],target['normal']; sl,tl = np.linalg.norm(sn,axis=1),np.linalg.norm(tn,axis=1)
    contract.require(np.isfinite(sn).all() and np.isfinite(tn).all() and (sl > 0).all() and (tl > 0).all(),
                     'Finite nonzero sampled normals required for facing compatibility')
    source_cells = {}; target_cells = {}
    for index,key in enumerate(np.floor(source['world']/distance_limit).astype(np.int64)):
        source_cells.setdefault(tuple(key),[]).append(index)
    for index,key in enumerate(np.floor(target['world']/distance_limit).astype(np.int64)):
        target_cells.setdefault(tuple(key),[]).append(index)
    source_rows = []; target_rows = []; distance_rows = []; cosine_rows = []
    offsets = list(product((-1,0,1),repeat=3))
    # Every candidate within one cell-width radius is in this 27-cell stencil.
    # Grouped bounded NumPy blocks avoid an optional SciPy dependency and an
    # unbounded all-pairs allocation while finding the same nearest candidates.
    for cell,selected in sorted(source_cells.items()):
        candidate = sorted(index for offset in offsets for index in
                           target_cells.get(tuple(cell[axis]+offset[axis] for axis in range(3)),[]))
        if not candidate: continue
        candidate = np.asarray(candidate,int)
        for start in range(0,len(selected),64):
            rows = np.asarray(selected[start:start+64],int)
            squared = np.sum((source['world'][rows,None,:]-target['world'][candidate][None,:,:])**2,axis=2)
            count = min(neighbors,len(candidate))
            if count < len(candidate): closest = np.argpartition(squared,count-1,axis=1)[:,:count]
            else: closest = np.tile(np.arange(len(candidate)),(len(rows),1))
            distances = np.sqrt(np.take_along_axis(squared,closest,axis=1))
            order = np.argsort(distances,axis=1,kind='stable')
            closest = np.take_along_axis(closest,order,axis=1); distances = np.take_along_axis(distances,order,axis=1)
            indices = candidate[closest]
            cosine = np.einsum('si,ski->sk',sn[rows],tn[indices])/(sl[rows,None]*tl[indices])
            allowed = (distances <= distance_limit)&(cosine >= minimum_normal_cosine)
            retained = allowed.any(axis=1); local_rows = np.flatnonzero(retained); first = np.argmax(allowed,axis=1)[retained]
            source_rows.extend(rows[retained]); target_rows.extend(indices[local_rows,first])
            distance_rows.extend(distances[local_rows,first]); cosine_rows.extend(cosine[local_rows,first])
    rows = np.asarray(source_rows,int); order = np.argsort(rows); rows = rows[order]
    return {'source':rows,'target':np.asarray(target_rows,int)[order], 'distance':np.asarray(distance_rows,float)[order],
            'normalCosine':np.asarray(cosine_rows,float)[order], 'coverageSamples':len(rows)/len(source['world']),
            'coverageArea':float(source['weight'][rows].sum()/source['weight'].sum())}


def summarize_pair(source,target,matched,palette,rows):
    result = {'matchedSamples':len(matched['source']),'sourceSampleCoverage':matched['coverageSamples'],
              'sourceAreaCoverage':matched['coverageArea'],'measurementAvailable':bool(len(matched['source']))}
    if not result['measurementAvailable']: return result
    a,b = matched['source'],matched['target']; weights = source['weight'][a]
    color_delta = source['rgb'][a]-target['rgb'][b]; shade_delta = source['shade'][a]-target['shade'][b]
    result.update(distanceMetres=statistics(matched['distance'],weights),
                  normalCosine=statistics(matched['normalCosine'],weights),
                  originalByteRgbSignedDifference=statistics(color_delta,weights),
                  originalByteRgbAbsoluteDifference=statistics(np.abs(color_delta),weights),
                  untreatedPltShadeSignedDifference=statistics(shade_delta,weights),
                  untreatedPltShadeAbsoluteDifference=statistics(np.abs(shade_delta),weights))
    result['paletteInputColorDifference'] = {}
    for row in rows:
        first = np.stack([np.interp(source['shade'][a],np.arange(256),palette[row,:,channel]) for channel in range(3)],axis=1)
        second = np.stack([np.interp(target['shade'][b],np.arange(256),palette[row,:,channel]) for channel in range(3)],axis=1)
        result['paletteInputColorDifference'][str(row)] = statistics(first-second,weights)
    return result


def stock_neck_inputs(selected,palette,palette_rows,source_prefix='pmh0'):
    """Used mesh UV/shade inputs only; provisional neck fit is not accepted here."""
    contract.require(re.fullmatch(r'p[mf][a-z]0', source_prefix) is not None, 'Declared stock phenotype0 neck family required')
    bitmap = source_prefix + '_neck001'
    ascii_path = pin(selected['ascii'],selected['asciiSha256']); plt_path = pin(selected['plt'],selected['pltSha256'])
    text = ascii_path.read_text(encoding='ascii')
    nodes = re.findall(r'(?ms)^node trimesh (\S+)\n(.*?)^endnode',text)
    contract.require(len(nodes) == 1 and re.search(r'(?m)^\s*bitmap ' + re.escape(bitmap) + r'\s*$',nodes[0][1]),
                     'Frozen installed target-source neck bitmap required')
    p,uv,faces = [np.asarray(arrays(nodes[0][1],key)) for key in ['verts','tverts','faces']]
    contract.require(np.array_equal(faces,faces.astype(int)), 'Noninteger stock neck topology'); faces = faces.astype(int)
    triangles = p[faces[:,:3]]; native_uv = uv[faces[:,4:7],:2]
    source_uv = native_uv.copy(); source_uv[...,1] = 1-source_uv[...,1]
    face_normal = np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0])
    sample = samples(triangles,np.repeat(face_normal[:,None,:],3,axis=1),source_uv,np.zeros(len(triangles),int),np.eye(4))
    data = plt_path.read_bytes(); contract.require(data[:8] == b'PLT V1  ' and len(data) >= 24,'Frozen neck PLT required')
    layers,reserved,width,height = struct.unpack_from('<IIII',data,8)
    contract.require(layers == 10 and reserved == 0 and width > 0 and height > 0 and
                     len(data) == 24+2*width*height, 'Invalid neck PLT structure')
    image = np.frombuffer(data[24:],dtype='u1').reshape(height,width,2)[::-1]
    shade = sample_pixels(image[...,0],sample['uv'],33071,33071)[:,0]
    # Layer indices are categorical, not interpolated color values.
    x = np.clip((sample['uv'][:,0]*width).astype(int),0,width-1)
    y = np.clip((sample['uv'][:,1]*height).astype(int),0,height-1)
    skin = image[y,x,1] == 0
    contract.require(skin.any(), 'No skin layer samples in installed neck UVs')
    weights = sample['weight'][skin]; shade = shade[skin]
    result = {'ascii':str(ascii_path),'asciiSha256':contract.sha(ascii_path),'plt':str(plt_path),'pltSha256':contract.sha(plt_path),
              'sourceBitmap':bitmap,'triangles':len(triangles),'skinSampleFraction':float(skin.mean()),
              'usedMeshUvPltShade':statistics(shade,weights),'paletteInputColors':{},
              'provisionalTargetGeometryAssociationAccepted':False,
              'limitation':'Whole stock neck mesh UV inputs; no spatial neck/chest match or client continuity claim'}
    for row in palette_rows:
        rgb = np.stack([np.interp(shade,np.arange(256),palette[row,:,channel]) for channel in range(3)],axis=1)
        result['paletteInputColors'][str(row)] = statistics(rgb,weights)
    return result,[ascii_path,plt_path]


def audit(config_path,output):
    config_path = Path(config_path).resolve(); config = json.loads(config_path.read_text(encoding='utf-8'))
    target_path,target = read_target(config); space = config['coordinateSpace']
    contract.require(config.get('kind') == 'target-joint-band-audit' and space in ('working','runtime') and
                     config.get('bandExtentUnits') == 'declared-space-metres', 'Explicit v2 target/space band contract required')
    contract.require(np.isfinite(config['minimumProposalAreaCoverage']) and 0 < config['minimumProposalAreaCoverage'] <= 1 and
                     np.isfinite(config['proposalThresholdShadeBytes']) and 0 < config['proposalThresholdShadeBytes'] <= 255,
                     'Explicit positive trial-proposal coverage and shade thresholds required')
    palette_path = pin(config['skinPalette'],config['skinPaletteSha256'])
    palette = np.asarray(Image.open(palette_path).convert('RGB')); palette_rows = config['paletteRows']
    contract.require(palette.shape[1:] == (256,3) and palette_rows and len(set(palette_rows)) == len(palette_rows) and
                     all(type(row) is int and 0 <= row < len(palette) for row in palette_rows), 'Declared installed skin palette rows required')
    sources = {}; source_rows = {}; frozen = [config_path,target_path,palette_path]
    for part,selected in config['parts'].items():
        contract.require(part in contract.BODY_PARTS, 'Undeclared target joint material owner')
        receipt_path = pin(selected['geometryReceipt'],selected['sha256']); frozen.append(receipt_path)
        receipt = json.loads(receipt_path.read_text(encoding='utf-8')); source = pin(receipt['candidate'],receipt['candidateSha256'])
        verify_source_receipt(source,receipt_path,target_path,target,part,space); frozen.append(source)
        doc,binary = read_glb(source); p,n,uv,primitives = raw_corners(doc,binary)
        frame = contract.frame(target,contract.PART_JOINTS[part],space)
        contract.require(np.array_equal(np.asarray(receipt['attachmentWorld']),frame), 'Fitted attachment frame differs')
        material_ids = np.asarray([row['material'] for row in primitives for _ in range(row['triangles'])])
        sample = samples(p,n,uv,material_ids,frame)
        sample['rgb'] = np.empty((len(sample['world']),3)); sample['shade'] = np.empty(len(sample['world']))
        map_rows = []
        for index in np.unique(material_ids):
            material = doc['materials'][int(index)]; pbr = material['pbrMetallicRoughness']
            contract.require(material.get('alphaMode','OPAQUE') == 'OPAQUE' and
                             pbr.get('baseColorFactor',[1,1,1,1]) == [1,1,1,1], 'Untreated opaque painted input required')
            texture = pbr['baseColorTexture']; pixels = image_pixels(doc,binary,texture)
            sampler = doc.get('samplers',[])[doc['textures'][texture['index']]['sampler']] if 'sampler' in doc['textures'][texture['index']] else {}
            wrap_s,wrap_t = sampler.get('wrapS',10497),sampler.get('wrapT',10497)
            mask = sample['material'] == index
            shade = (pixels.astype(float)@np.asarray([.2126,.7152,.0722])).clip(0,255).astype('u1')
            sample['rgb'][mask] = sample_pixels(pixels,sample['uv'][mask],wrap_s,wrap_t)
            sample['shade'][mask] = sample_pixels(shade,sample['uv'][mask],wrap_s,wrap_t)[:,0]
            map_rows.append({'material':int(index),'originalBindings':material,'sampler':sampler,
                             'colorDecodedSha256':hashlib.sha256(pixels.tobytes()).hexdigest(),
                             'untreatedPltShadeDecodedSha256':hashlib.sha256(shade.tobytes()).hexdigest()})
        sources[part] = sample; source_rows[part] = {'source':str(source),'sourceSha256':contract.sha(source),
            'geometryReceipt':str(receipt_path),'geometryReceiptSha256':contract.sha(receipt_path),
            'attachmentJoint':contract.PART_JOINTS[part],'attachmentFrame':frame.tolist(),
            'triangles':len(p),'materialInputs':map_rows,'statureApplications':receipt['statureApplications']}
    results = []; archives = {}; proposals = []
    for band in config['bands']:
        band_id = band['id']; contract.require(re.fullmatch(r'[a-z0-9-]+',band_id) and band_id not in archives,'Unique stable joint band id required')
        anchor = contract.frame(target,band['anchorJoint'],space)[:3,3]
        axis = contract.frame(target,band['axisJoint'],space)[:3,3]-anchor
        pair = band['parts']; contract.require(len(pair) == 2 and len(set(pair)) == 2 and set(pair) <= set(sources), 'Declared two-part band comparison required')
        selected = {}
        band_result = {'id':band_id,'definition':band,'anchorWorld':anchor.tolist(),'axisWorld':(axis/np.linalg.norm(axis)).tolist(),
                       'parts':{},'bidirectionalMatches':{},'actualClientContinuityAccepted':False}
        for part in pair:
            sample = sources[part]; mask = band_mask(sample['world'],anchor,axis,band['axialIntervalMetres'],band['radialLimitMetres'])
            contract.require(mask.any(),'Empty joint band: '+band_id+' '+part)
            selected[part] = {key:value[mask] for key,value in sample.items()}
            band_result['parts'][part] = {'samples':int(mask.sum()),'representedTriangles':int(len(np.unique(sample['triangle'][mask]))),
                'originalByteRgb':statistics(sample['rgb'][mask],sample['weight'][mask]),
                'untreatedPltShade':statistics(sample['shade'][mask],sample['weight'][mask])}
            for key,value in selected[part].items(): archives[band_id+'__'+part+'__'+key] = value
        archives[band_id] = np.asarray(pair)
        for first,second in [pair,pair[::-1]]:
            matched = match(selected[first],selected[second],band['pairDistanceLimitMetres'],band['minimumNormalCosine'],band['neighbors'])
            summary = summarize_pair(selected[first],selected[second],matched,palette,palette_rows)
            band_result['bidirectionalMatches'][first+'-to-'+second] = summary
            for key in ['source','target','distance','normalCosine']:
                archives[band_id+'__'+first+'-to-'+second+'__'+key] = matched[key]
            if summary['measurementAvailable'] and summary['sourceAreaCoverage'] >= config['minimumProposalAreaCoverage']:
                delta = summary['untreatedPltShadeSignedDifference']['mean'][0]
                if abs(delta) >= config['proposalThresholdShadeBytes']:
                    proposals.append({'band':band_id,'direction':first+'-to-'+second,'measuredSignedShadeDifference':delta,
                        'action':'Review physical seam and hidden-surface coverage first; only then prepare independently derived common-parent PLT trials',
                        'trialMaximumAbsoluteShadeOffsets':[2,4,8],'preserve':'Geometry, authored normals, UVs, normal/roughness maps, painted local contrast and accepted neighbors',
                        'selectedCorrection':None,'trialPrepared':False,'clientReviewRequired':True})
        results.append(band_result)
    neck = None
    if config.get('stockNeck'):
        neck,paths = stock_neck_inputs(config['stockNeck'],palette,palette_rows,target['rig']['sourcePrefix']); frozen.extend(paths)
    output = Path(output).resolve(); contract.require(not output.exists(),'Fresh immutable joint-band audit required')
    output.mkdir(parents=True); archive_path = output/'joint-samples.npz'; np.savez_compressed(archive_path,**archives)
    frozen.append(archive_path)
    for name in ['audit_target_joint_bands.py','target_contract.py','target_part_pipeline.py','target_part_stage.py','place_purposebuilt_pelvis.py']:
        path = output/name; shutil.copyfile(Path(__file__).with_name(name),path); frozen.append(path)
    receipt = {'schemaVersion':2,'kind':'target-joint-band-audit',**contract.binding(target_path,target,space),
               'sources':source_rows,'bands':results,'stockNeckInputs':neck,'boundedTrialProposals':proposals,
               'sampleArchive':str(archive_path),'sampleArchiveSha256':contract.sha(archive_path),
               'samplingPolicy':{'barycentricWeights':BARYCENTRIC.tolist(),'areaWeighted':True,
                   'sourceRgb':'Original byte RGB base-level bilinear taps at raw glTF UV; no gamma/mipmap simulation',
                   'pltShade':'Byte-space painted luminance floor from untreated parent, no added AO',
                   'paletteColors':'Interpolated installed palette-row inputs only; actual PLT generation/filtering unobserved',
                   'frames':'Hash-bound declared attachment-local to world, no additional stature conversion'},
               'geometryEdited':False,'materialPixelsEdited':False,'correctionSelected':None,
               'rigMode':contract.rig_mode(target),'rigValidated':contract.rig_ready(target),
               'rigPilotAccepted':target['rig'].get('pilotAccepted',False),'productionAccepted':False,'clientAccepted':False,
               'frozenInputs':{str(path):contract.sha(path) for path in sorted(set(frozen))},
               'limitations':'Neutral-pose cylinder bands and nearest facing-compatible samples may include hidden caps/intersections. Coverage, distance and painted detail affect interpretation. Measurements do not prove visible seams, motion connectors or actual client palette continuity.'}
    result = output/'joint-band-audit.json'; result.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True); args = parser.parse_args()
    result = audit(args.config,args.output); print(json.dumps({'receipt':str(result),'receiptSha256':contract.sha(result)}))
