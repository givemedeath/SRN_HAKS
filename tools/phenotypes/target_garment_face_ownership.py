"""Explicit per-face garment ownership and bounded derived color proposals.

Additive to the strict categorical-mask helper. Original GLB/BIN, indices,
attributes and maps are immutable. Separate material copies can pad a shared
UV boundary; proposals never approve those corrections or a body candidate.
"""
import argparse
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image

import target_contract as contract
from place_purposebuilt_pelvis import embedded_maps, raw_corners, read_glb
from target_part_pipeline import pin, read_target, verify_source_receipt
from target_part_stage import image_pixels, material_inputs
from target_garment_ownership import CODES, boundary_metrics, digest_bytes, mask_pixels, measure_uv_faces, partition

BIND_FIELDS = ('targetContract', 'targetContractSha256', 'targetId', 'rigRevision', 'coordinateSpace', 'part', 'model', 'source', 'sourceSha256', 'sourceReceipt', 'sourceReceiptSha256')
HELPERS = ('target_garment_face_ownership.py', 'target_garment_ownership.py', 'target_contract.py', 'target_part_pipeline.py', 'target_part_stage.py', 'place_purposebuilt_pelvis.py')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save(path, value):
    contract.require(not path.exists(), 'Fresh immutable proposal output required')
    path.write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8')


def pinned(row):
    contract.require(isinstance(row, dict) and set(row) == {'path', 'sha256'}, 'Explicit path/hash pin required')
    return pin(row['path'], row['sha256'])


def common(config_path, *, material_execution=None):
    config_path = Path(config_path).resolve(); cfg = read(config_path)
    contract.require(cfg.get('kind') == 'target-garment-face-proposal' and cfg.get('diagnosticOnly') is True,
                     'Explicit diagnostic per-face proposal required')
    allowed = {'schemaVersion','kind','diagnosticOnly','targetContract','targetContractSha256','part','coordinateSpace',
               'source','sourceSha256','sourceReceipt','sourceReceiptSha256','faceDecisions','ownershipMask','padding',
               'knownSourceGarmentDefects','protectedInputs','notes'}
    contract.require(set(cfg) <= allowed, 'Unknown per-face ownership controls')
    target_path, target = read_target(cfg); part, space = cfg['part'], cfg['coordinateSpace']
    contract.require(part in {'chest','pelvis'} and part in contract.fixed_garment_parts(target), 'Declared chest/pelvis garment owner required')
    contract.require(space in {'working','runtime'}, 'Explicit per-face coordinate space required')
    source = pin(cfg['source'], cfg['sourceSha256']); receipt = pin(cfg['sourceReceipt'], cfg['sourceReceiptSha256'])
    if material_execution is None:
        parent = verify_source_receipt(source, receipt, target_path, target, part, space)
    else:
        from replay_stage_skin_calibration import geometry_input
        parent=geometry_input({'path':str(source),'sha256':contract.sha(source)},{'path':str(receipt),'sha256':contract.sha(receipt)},target_path,target,part,space,material_execution=material_execution)['receipt']
    doc, binary = read_glb(source)
    contract.require(doc['nodes'] == [{'name':'detached_geometry','mesh':0}] and len(doc['meshes']) == 1, 'Canonical detached fitted source required')
    p,n,uv,_ = raw_corners(doc,binary); active = {row['material'] for row in doc['meshes'][0]['primitives']}
    contract.require(len(active) == 1 and all(type(value) is int for value in active), 'One shared source material atlas required')
    material_id = next(iter(active)); material = doc['materials'][material_id]
    contract.require(not material.get('extensions'), 'Material extensions require a separate adapter')
    rows, proof = material_inputs(doc,binary,{material_id:'skin'},part,0,contract.fixed_garment_parts(target))
    defects = cfg.get('knownSourceGarmentDefects')
    contract.require(isinstance(defects,list) and all(isinstance(item,str) and item.strip() for item in defects), 'Explicit observed source garment defects list required')
    radius = cfg['padding'].get('radiusPixels') if isinstance(cfg.get('padding'),dict) else None
    contract.require(set(cfg['padding']) == {'radiusPixels'} and type(radius) is int and 0 <= radius <= 16,
                     'Explicit bounded 0..16 pixel edge-padding radius required')
    frozen = {str(path):contract.sha(path) for path in (config_path,target_path,source,receipt)}
    for name,expected in cfg.get('protectedInputs',{}).items(): frozen[str(pin(name,expected))] = expected
    identity = {**contract.binding(target_path,target,space),'part':part,'model':contract.model(target,part),
                'source':str(source),'sourceSha256':contract.sha(source),'sourceReceipt':str(receipt),'sourceReceiptSha256':contract.sha(receipt)}
    return cfg,target_path,target,source,receipt,parent,doc,binary,p,n,uv,material_id,rows['skin'],proof,frozen,identity


def decisions(row, identity, face_count):
    path = pinned(row); data = read(path)
    contract.require(data.get('schemaVersion') == 2 and data.get('kind') == 'target-garment-face-decisions', 'Explicit face decision document required')
    contract.require(all(data.get(key) == identity[key] for key in BIND_FIELDS), 'Face decisions belong to another source/target')
    ids = data.get('sourceFaceIds'); roles = data.get('faceRoles')
    contract.require(type(ids) is list and all(type(value) is int for value in ids) and ids == list(range(face_count)), 'Each original source face must appear exactly once in original order')
    contract.require(type(roles) is list and len(roles) == face_count and set(roles) <= set(CODES), 'Complete skin/garment/unknown face decisions required')
    contract.require(data.get('accepted') is False, 'Input face decisions are proposals, not automatic acceptance')
    return path, roles


def support(triangle, shape, filter_radius=1, strict_centers=False):
    """Same full pixel-square/bilinear support as legacy, or strict interior centers."""
    height,width = shape; points = triangle*[width,height]-.5
    edges = np.roll(points,-1,axis=0)-points; diagonal = points[2]-points[0]
    signed = edges[0,0]*diagonal[1]-edges[0,1]*diagonal[0]
    contract.require(np.isfinite(points).all() and triangle.min() >= 0 and triangle.max() <= 1 and abs(signed)>1e-12, 'Nonwrapping nondegenerate finite UVs required for derived padding')
    radius = 0 if strict_centers else .5+filter_radius
    low = np.maximum(np.ceil(points.min(0)-radius).astype(int),[0,0]); high = np.minimum(np.floor(points.max(0)+radius).astype(int),[width-1,height-1])
    y,x = np.mgrid[low[1]:high[1]+1,low[0]:high[0]+1]; sample = np.stack((x,y),axis=-1); inside = np.ones(x.shape,bool); sign = 1 if signed>0 else -1
    for origin,edge in zip(points,edges):
        delta = sample-origin; value = sign*(edge[0]*delta[:,:,1]-edge[1]*delta[:,:,0])
        inside &= value>1e-10 if strict_centers else value>=-radius*(abs(edge[0])+abs(edge[1]))-1e-10
    return (y[inside]*width+x[inside]).astype(np.int64)


def derive_color(color, mask, wanted, interior, role, radius):
    """Nearest same-role original interior texel, within an explicit pixel radius."""
    code = CODES[role]; shape = mask.shape; height,width = shape
    seed = interior & (mask==code); needed = wanted & (mask!=code)
    y,x = np.where(needed); unresolved = np.ones(len(y),bool); chosen = np.full(len(y),-1,np.int64); distance2 = np.full(len(y),-1,np.int32)
    offsets = sorted((dy*dy+dx*dx,dy,dx) for dy in range(-radius,radius+1) for dx in range(-radius,radius+1) if dy*dy+dx*dx<=radius*radius)
    for d2,dy,dx in offsets:
        indices = np.flatnonzero(unresolved)
        if not len(indices): break
        yy,xx = y[indices]+dy,x[indices]+dx; valid = (yy>=0)&(yy<height)&(xx>=0)&(xx<width)
        selected = indices[valid]; yy,xx = yy[valid],xx[valid]; hits = seed[yy,xx]
        selected = selected[hits]; yy,xx = yy[hits],xx[hits]
        chosen[selected] = yy*width+xx; distance2[selected] = d2; unresolved[selected] = False
    output = color.copy(); good = ~unresolved
    output[y[good],x[good]] = color.reshape(-1,3)[chosen[good]]
    delta = np.abs(output.astype(np.int16)-color.astype(np.int16)); changed = np.any(delta,axis=2)
    proof = {'radiusPixels':radius,'wantedTexels':int(wanted.sum()),'interiorSeedTexels':int(seed.sum()),'neededTexels':len(y),'paddedTexels':int(good.sum()),
             'unresolvedTexels':int(unresolved.sum()),'changedColorTexels':int(changed.sum()),'maximumChannelDelta':int(delta.max()),
             'maximumCopyDistancePixels':float(np.sqrt(distance2[good].max())) if good.any() else 0.,
             'outsideRoleSupportPixelsUnchanged':bool(np.array_equal(output[~wanted],color[~wanted])),'method':'Nearest original same-role diagnostic texel within declared radius and owned triangle interiors; stable distance/y/x tie order.'}
    return output, proof, {'destinationTexelIds':y*width+x,'sourceTexelIds':chosen,'distanceSquaredPixels':distance2,'unresolved':unresolved}


def ownership_metrics(p,uv,roles,counts,interior_counts,radius):
    area=np.linalg.norm(np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0]),axis=1)*.5;labels=np.asarray(roles)
    uv_edges=np.stack((uv[:,1]-uv[:,0],uv[:,2]-uv[:,0]),axis=-1);world_edges=np.stack((p[:,1]-p[:,0],p[:,2]-p[:,0]),axis=-1)
    jacobian=world_edges@np.linalg.inv(uv_edges)
    # Frobenius norm bounds world length from an atlas-pixel displacement;
    # this deliberately exposes stretched islands rather than claiming one
    # constant millimeter bound for all UV charts.
    per_pixel_bound=np.linalg.norm(jacobian,axis=(1,2))/2048
    return {'faceRoleCounts':{role:int(np.count_nonzero(labels==role)) for role in CODES},
            'faceAreaMetersSquared':{role:float(area[labels==role].sum()) for role in CODES},
            'mixedInteriorAreaMetersSquared':float(area[(interior_counts[:,0]>0)&(interior_counts[:,2]>0)].sum()),
            'maximumPaddingAffineDistanceBoundMeters':{role:float(per_pixel_bound[labels==role].max()*radius) if np.any(labels==role) else 0. for role in ('skin','garment')},
            'distanceLimit':'Conservative local triangle UV-to-position Frobenius bound; not an observed body silhouette displacement or approval. Geometry remains exact.'}

def original_png(doc,binary,texture):
    image = doc['images'][doc['textures'][texture['index']]['source']]; view = doc['bufferViews'][image['bufferView']]; start = view.get('byteOffset',0)
    return binary[start:start+view['byteLength']]


def proposal(config_path, output):
    cfg,tp,target,source,receipt,parent,doc,binary,p,n,uv,mid,original,material_proof,frozen,identity = common(config_path)
    decision_path,roles = decisions(cfg['faceDecisions'],identity,len(p)); mask_path = pinned(cfg['ownershipMask']); mask = mask_pixels(mask_path)
    frozen.update({str(decision_path):contract.sha(decision_path),str(mask_path):contract.sha(mask_path)})
    _,counts,issues = measure_uv_faces(uv,mask,1)
    invalid = [row for row in issues if row['reason'] not in {'mixed-skin-garment-footprint','unknown-mask-texels'}]
    contract.require(not invalid, 'Invalid UV footprint requires a separately reviewed geometry descendant')
    wanted = {role:np.zeros(mask.shape,bool) for role in ('skin','garment')}; interior = {role:np.zeros(mask.shape,bool) for role in wanted}
    interior_counts = np.zeros((len(p),3),np.int64)
    for face,triangle in enumerate(uv):
        centers = support(triangle,mask.shape,strict_centers=True); values = mask.reshape(-1)[centers]
        interior_counts[face] = [np.count_nonzero(values==code) for code in (0,127,255)]
        if roles[face] in wanted:
            wanted[roles[face]].reshape(-1)[support(triangle,mask.shape)] = True
            interior[roles[face]].reshape(-1)[centers] = True
    output = Path(output).resolve(); contract.require(not output.exists(),'Fresh per-face proposal output required'); output.mkdir(parents=True)
    outputs = {}; maps = {}; padproof = {}; material = doc['materials'][mid]
    for name,texture in [('baseColor',material['pbrMetallicRoughness']['baseColorTexture']),('normal',material['normalTexture']),('ORM',material['pbrMetallicRoughness']['metallicRoughnessTexture'])]:
        path = output/('original-'+name+'.png'); path.write_bytes(original_png(doc,binary,texture)); outputs[str(path)] = contract.sha(path)
    for role in wanted:
        derived,proof,copies = derive_color(original['color'],mask,wanted[role],interior[role],role,cfg['padding']['radiusPixels'])
        color_path = output/(role+'-derived-base-color.png'); Image.fromarray(derived).save(color_path)
        support_path = output/(role+'-sampled-support.png'); Image.fromarray(wanted[role].astype(np.uint8)*255).save(support_path)
        lineage_path = output/(role+'-padding-lineage.npz'); np.savez_compressed(lineage_path,**copies)
        for path in (color_path,support_path,lineage_path): outputs[str(path)] = contract.sha(path)
        maps[role] = {'baseColor':{'path':str(color_path),'sha256':contract.sha(color_path)},'normal':{'path':str(output/'original-normal.png'),'sha256':contract.sha(output/'original-normal.png')},
                      'ORM':{'path':str(output/'original-ORM.png'),'sha256':contract.sha(output/'original-ORM.png')},'sampledSupport':{'path':str(support_path),'sha256':contract.sha(support_path)},'paddingLineage':{'path':str(lineage_path),'sha256':contract.sha(lineage_path)}}
        padproof[role] = proof
        if role=='skin':
            intensity = (derived.astype(float)@np.asarray([.2126,.7152,.0722])).clip(0,255).astype(np.uint8)
            path = output/'skin-derived-plt-intensity-ao0.png'; Image.fromarray(intensity).save(path); outputs[str(path)] = contract.sha(path); maps[role]['pltIntensityAO0'] = {'path':str(path),'sha256':contract.sha(path)}
    archive = output/'face-measurements.npz'; np.savez_compressed(archive,sourceFaceIds=np.arange(len(p)),filterPixelCounts=counts,strictInteriorPixelCounts=interior_counts,faceRoleCodes=np.asarray([CODES[role] for role in roles],np.uint8)); outputs[str(archive)] = contract.sha(archive)
    metrics,_ = boundary_metrics(p,roles)
    snapshots = {}; directory = output/'helper-snapshots'; directory.mkdir()
    for name in HELPERS:
        original_helper = Path(__file__).with_name(name).resolve(); copied = directory/name; shutil.copyfile(original_helper,copied); frozen[str(copied)] = contract.sha(copied); snapshots[str(original_helper)] = {'path':str(copied),'sha256':contract.sha(copied)}
    for name,expected in frozen.items(): pin(name,expected)
    record = {'schemaVersion':2,'kind':'target-garment-face-proposal',**identity,'sourceFaces':len(p),'sourceFaceIds':list(range(len(p))),'faceRoles':roles,
              'configuration':{'path':str(Path(config_path).resolve()),'sha256':contract.sha(Path(config_path).resolve())},'faceDecisions':{'path':str(decision_path),'sha256':contract.sha(decision_path)},'ownershipMask':{'path':str(mask_path),'sha256':contract.sha(mask_path)},
              'filterRadiusPixels':1,'measuredAmbiguousFaces':issues,'mixedStrictInteriorFaces':np.flatnonzero((interior_counts[:,0]>0)&(interior_counts[:,2]>0)).tolist(),
              'faceMeasurements':{'path':str(archive),'sha256':contract.sha(archive)},'ownershipMeasurements':ownership_metrics(p,uv,roles,counts,interior_counts,cfg['padding']['radiusPixels']),'boundaryMetrics':metrics,'padding':cfg['padding'],'paddingProof':padproof,'derivedCompilerInputs':maps,
              'originalEmbeddedMaps':embedded_maps(doc,binary),'originalMaterialProof':material_proof,'originalBINByteSha256':digest_bytes(binary),
              'protectedAttributePolicy':'No source/index/position/UV/normal/tangent/color/map mutation; only proposed separate role color/PLT copies. Normal pixels and authored ORM/roughness transport remain exact.',
              'knownSourceGarmentDefects':cfg['knownSourceGarmentDefects'],'completeFaceDecisions': 'unknown' not in roles and set(roles)=={'skin','garment'},
              'paddingResolved':all(not row['unresolvedTexels'] for row in padproof.values()),'frozenInputs':frozen,'outputHashes':outputs,'helperSnapshots':snapshots,
              'decision':'unreviewed','accepted':False,'diagnosticOnly':True,'productionAccepted':False,'clientAccepted':False,'sourceChanged':False,
              'limits':['Per-face decisions and color padding are separate reviewable proposals, never garment-design or palette acceptance.', 'Unknown faces/unresolved padding block the reviewed staging API.', 'Known source garment defects require a revised source/proposal, not a material-ownership waiver.', 'Legacy target_part_stage does not consume these sidecars; explicit additive integration is required.']}
    path = output/'proposal.json'; save(path,record)
    template = {key:record[key] for key in BIND_FIELDS}; template.update(schemaVersion=2,kind='target-garment-face-review',proposalReceipt={'path':str(path),'sha256':contract.sha(path)},sourceFaceIds=record['sourceFaceIds'],faceRoles=roles,
        accepted=False,decision='pending',reviewer=None,notes=None,garmentDesignReviewed=False,reviewedViews=[],boundaryReview={'sourceFaceIds':[row['sourceFace'] for row in issues],'decision':'pending','notes':None},paletteEdgeEvidence=[])
    save(output/'pending-review-template.json',template)
    save(output/'pending-stage-interface.json',{'schemaVersion':2,'kind':'target-part-stage-reviewed-garment-inputs','diagnosticOnly':True,**identity,'garmentFaceProposal':{'path':str(path),'sha256':contract.sha(path)},'garmentFaceReview':None,'aoStrength':0,
        'status':'Adapter required: legacy stage rejects this kind. Generate direct palette edge review from proposed maps before reviewed native staging; body acceptance remains separate.'})
    return path


def remeasure_proposal(proposed, doc, binary, p, uv, *, material_execution=None):
    """Reconstruct every derived pixel/lineage from the frozen original parent."""
    values=common(pinned(proposed['configuration'])) if material_execution is None else common(pinned(proposed['configuration']),material_execution=material_execution)
    cfg,tp,target,source,receipt,parent,_,_,_,_,_,mid,original,material_proof,_,identity = values
    contract.require(all(proposed.get(key)==identity[key] for key in BIND_FIELDS) and proposed['padding']==cfg['padding']
                     and proposed['knownSourceGarmentDefects']==cfg['knownSourceGarmentDefects'], 'Proposal configuration/source controls differ')
    decision_path,roles=decisions(cfg['faceDecisions'],identity,len(p))
    contract.require(proposed['faceDecisions']==cfg['faceDecisions'] and proposed['ownershipMask']==cfg['ownershipMask']
                     and proposed['faceRoles']==roles and all(type(value) is int for value in proposed['sourceFaceIds']), 'Proposal face/mask lineage differs')
    mask=mask_pixels(pinned(cfg['ownershipMask']));_,counts,issues=measure_uv_faces(uv,mask,1)
    contract.require(proposed['measuredAmbiguousFaces']==issues and proposed['filterRadiusPixels']==1, 'Measured filter ambiguity differs')
    wanted={role:np.zeros(mask.shape,bool) for role in ('skin','garment')};interior={role:np.zeros(mask.shape,bool) for role in wanted};interior_counts=np.zeros_like(counts)
    for face,triangle in enumerate(uv):
        centers=support(triangle,mask.shape,strict_centers=True);values=mask.reshape(-1)[centers]
        interior_counts[face]=[np.count_nonzero(values==code) for code in (0,127,255)]
        if roles[face] in wanted:
            wanted[roles[face]].reshape(-1)[support(triangle,mask.shape)]=True;interior[roles[face]].reshape(-1)[centers]=True
    with np.load(pinned(proposed['faceMeasurements']),allow_pickle=False) as archive:
        contract.require(np.array_equal(archive['sourceFaceIds'],np.arange(len(p))) and np.array_equal(archive['filterPixelCounts'],counts)
                         and np.array_equal(archive['strictInteriorPixelCounts'],interior_counts) and np.array_equal(archive['faceRoleCodes'],np.asarray([CODES[role] for role in roles],np.uint8)), 'Measured face archive differs')
    contract.require(proposed['mixedStrictInteriorFaces']==np.flatnonzero((interior_counts[:,0]>0)&(interior_counts[:,2]>0)).tolist()
                     and proposed['boundaryMetrics']==boundary_metrics(p,roles)[0] and proposed['ownershipMeasurements']==ownership_metrics(p,uv,roles,counts,interior_counts,cfg['padding']['radiusPixels']), 'Measured interior/boundary evidence differs')
    for role in wanted:
        derived,proof,copies=derive_color(original['color'],mask,wanted[role],interior[role],role,cfg['padding']['radiusPixels'])
        fields=proposed['derivedCompilerInputs'][role]
        color=np.asarray(Image.open(pinned(fields['baseColor'])).convert('RGB')); sampled=np.asarray(Image.open(pinned(fields['sampledSupport'])))
        contract.require(np.array_equal(color,derived) and np.array_equal(sampled,wanted[role].astype(np.uint8)*255) and proof==proposed['paddingProof'][role], 'Derived color exceeds measured original-pixel padding operation')
        with np.load(pinned(fields['paddingLineage']),allow_pickle=False) as archive:
            contract.require(set(archive.files)==set(copies) and all(np.array_equal(archive[key],copies[key]) for key in copies), 'Padding source/destination lineage differs')
        if role=='skin':
            intensity=(derived.astype(float)@np.asarray([.2126,.7152,.0722])).clip(0,255).astype(np.uint8)
            contract.require(np.array_equal(np.asarray(Image.open(pinned(fields['pltIntensityAO0']))),intensity), 'Derived PLT intensity differs from reviewed color parent')
    material=doc['materials'][mid]; directory=pinned(proposed['derivedCompilerInputs']['skin']['normal']).parent
    for name,texture in [('baseColor',material['pbrMetallicRoughness']['baseColorTexture']),('normal',material['normalTexture']),('ORM',material['pbrMetallicRoughness']['metallicRoughnessTexture'])]:
        contract.require((directory/('original-'+name+'.png')).read_bytes()==original_png(doc,binary,texture), 'Original map archive bytes differ')
    return cfg

def reviewed_staging_inputs(proposal_path, review_path, target_path, target, part, space, source, source_receipt, ao_strength=0, *, material_execution=None):
    """Explicit adapter interface; returns immutable partition and reviewed material rows.

    It writes no geometry/resource/selection. The caller must record its own
    native stage receipt and must not fall through to legacy original-color rows.
    """
    proposal_path,review_path,target_path,source,source_receipt = [Path(path).resolve() for path in (proposal_path,review_path,target_path,source,source_receipt)]
    proposed,reviewed = read(proposal_path),read(review_path)
    contract.require(proposed.get('schemaVersion')==2 and proposed.get('kind')=='target-garment-face-proposal' and proposed.get('accepted') is False and proposed.get('decision')=='unreviewed','Original per-face proposal required')
    if material_execution is None:
        parent = verify_source_receipt(source,source_receipt,target_path,target,part,space)
        adopted_pins=None
    else:
        from replay_stage_skin_calibration import geometry_input
        parent_value=geometry_input({'path':str(source),'sha256':contract.sha(source)},{'path':str(source_receipt),'sha256':contract.sha(source_receipt)},target_path,target,part,space,material_execution=material_execution)
        parent=parent_value['receipt'];adopted_pins=dict(parent_value['pins'])
    for item in (proposed,reviewed):
        contract.verify_binding(item,target_path,target,space)
        contract.require(item.get('part')==part and item.get('model')==contract.model(target,part) and Path(item['source']).resolve()==source and item['sourceSha256']==contract.sha(source)
                         and Path(item['sourceReceipt']).resolve()==source_receipt and item['sourceReceiptSha256']==contract.sha(source_receipt),'Per-face review source/owner differs')
    if material_execution is None:
        for name,expected in {**proposed['frozenInputs'],**proposed['outputHashes']}.items(): pin(name,expected)
    else:
        from phenotype_material_execution_adoption import resolve
        for path,value in ((proposal_path,proposed),(review_path,reviewed)):
            physical,_=resolve(material_execution,module_file=__file__,path=path,value=value,tp=target_path,target=target,part=part,space=space,consumer='garment.reviewed')
            adopted_pins.update(physical)
    contract.require(reviewed.get('schemaVersion')==2 and reviewed.get('kind')=='target-garment-face-review' and reviewed.get('accepted') is True and reviewed.get('decision')=='approved-face-ownership-and-material-inputs'
                     and reviewed.get('reviewer') and reviewed.get('notes'),'Independent explicit per-face/material review required')
    contract.require(reviewed.get('proposalReceipt')=={'path':str(proposal_path),'sha256':contract.sha(proposal_path)},'Review binds exact per-face/material proposal')
    contract.require(not proposed['knownSourceGarmentDefects'] and reviewed.get('garmentDesignReviewed') is True,'Unresolved source garment defects require a revised source, not ownership approval')
    roles = proposed['faceRoles']
    contract.require(proposed['completeFaceDecisions'] and proposed['paddingResolved'] and set(roles)=={'skin','garment'} and reviewed.get('faceRoles')==roles and reviewed.get('sourceFaceIds')==proposed['sourceFaceIds'],'Complete explicit decisions and resolved bounded padding required')
    contract.require(set(reviewed.get('reviewedViews',[])) >= {'front','rear','side','uv-boundary'},'Direct garment design and UV boundary views required')
    boundary = reviewed.get('boundaryReview',{})
    contract.require(boundary.get('sourceFaceIds')==[row['sourceFace'] for row in proposed['measuredAmbiguousFaces']] and boundary.get('decision')=='reviewed-per-face-boundary' and boundary.get('notes'),'Measured mixed/interior/filter ambiguities require explicit boundary review')
    evidence = reviewed.get('paletteEdgeEvidence',[]); palettes=set()
    for row in evidence:
        contract.require(type(row.get('palette')) is int and row['palette'] in (3,8) and row.get('basis') in ('native-material-preview','literal-client') and row.get('view')=='garment-edges'
                         and row.get('proposalSha256')==contract.sha(proposal_path),'Direct palette3/8 edge evidence must bind exact proposed compiler inputs')
        pin(row['path'],row['sha256']); palettes.add(row['palette'])
    contract.require(palettes=={3,8},'Direct palette3 and8 garment-edge views required before reviewed staging')
    doc,binary=read_glb(source);p,n,uv,_=raw_corners(doc,binary)
    contract.require(len(p)==proposed['sourceFaces'] and proposed['sourceFaceIds']==list(range(len(p))) and digest_bytes(binary)==proposed['originalBINByteSha256'] and embedded_maps(doc,binary)==proposed['originalEmbeddedMaps'],'Original attributes/maps/topology lineage differs')
    if material_execution is None:remeasure_proposal(proposed,doc,binary,p,uv)
    else:remeasure_proposal(proposed,doc,binary,p,uv,material_execution=material_execution)
    partitioned,material_roles,primitive_ids=partition(doc,binary,roles,100000)
    rows,original_proof=material_inputs(partitioned,binary,{int(key):value for key,value in material_roles.items()},part,ao_strength,contract.fixed_garment_parts(target))
    for role,row in rows.items():
        color=np.asarray(Image.open(pinned(proposed['derivedCompilerInputs'][role]['baseColor'])).convert('RGB'))
        contract.require(color.shape==(2048,2048,3),'Derived 2K color compiler input required')
        row['color']=color
        material=doc['materials'][doc['meshes'][0]['primitives'][0]['material']]
        ao=image_pixels(doc,binary,material['occlusionTexture'])[:,:,0].astype(float)/255 if ao_strength else np.ones((2048,2048))
        row['intensity']=((color.astype(float)@np.asarray([.2126,.7152,.0722]))*(1-ao_strength*(1-ao))).clip(0,255).astype(np.uint8)
        # Sidecar normal/ORM proofs bind the originals; they never replace them.
        normal=np.asarray(Image.open(pinned(proposed['derivedCompilerInputs'][role]['normal'])).convert('RGB'))
        orm=np.asarray(Image.open(pinned(proposed['derivedCompilerInputs'][role]['ORM'])).convert('RGB'))
        contract.require(np.array_equal(normal,row['normal']) and np.array_equal(orm,image_pixels(doc,binary,material['pbrMetallicRoughness']['metallicRoughnessTexture'])),'Normal/ORM pixels must remain exact')
    proof={'kind':'reviewed-per-face-derived-compiler-inputs','proposalReceipt':{'path':str(proposal_path),'sha256':contract.sha(proposal_path)},'reviewReceipt':{'path':str(review_path),'sha256':contract.sha(review_path)},
           'geometryBINExact':True,'originalFaceOrderExact':True,'attributesUVNormalsTangentsExact':True,'originalEmbeddedMapsExact':True,'normalPixelsExact':True,'authoredRoughnessTransportExact':True,
           'sourceEmbeddedMaps':proposed['originalEmbeddedMaps'],'derivedCompilerInputs':proposed['derivedCompilerInputs'],'paddingProof':proposed['paddingProof'],'paletteEdgeEvidence':evidence,'aoStrength':ao_strength,
           'productionAccepted':False,'clientAccepted':False,'limitation':'Ownership/material inputs reviewed only; whole body native serialization, equipment, animation and literal-client acceptance remain separate.'}
    return {'document':partitioned,'binary':binary,'materialRoles':material_roles,'primitiveIds':primitive_ids,'faceRoles':roles,'materialRows':rows,'originalMaterialProof':original_proof,'proof':proof,'parent':parent,**({'frozenInputs':adopted_pins} if adopted_pins is not None else {})}


def validate_review(proposal_path,review_path,output):
    proposed=read(proposal_path);tp=Path(proposed['targetContract']);target=contract.load(tp)
    result=reviewed_staging_inputs(proposal_path,review_path,tp,target,proposed['part'],proposed['coordinateSpace'],proposed['source'],proposed['sourceReceipt'])
    output=Path(output).resolve();contract.require(not output.exists(),'Fresh review verification output required');output.mkdir(parents=True)
    path=output/'reviewed-staging-inputs.json';save(path,result['proof']);return path


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--mode',choices=('propose','verify-review'),required=True)
    parser.add_argument('--config',type=Path);parser.add_argument('--proposal',type=Path);parser.add_argument('--review',type=Path);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.mode=='propose':
        if args.config is None:parser.error('--config required for propose')
        result=proposal(args.config,args.output)
    else:
        if args.proposal is None or args.review is None:parser.error('--proposal and --review required')
        result=validate_review(args.proposal,args.review,args.output)
    print(json.dumps({'receipt':str(result),'sha256':contract.sha(result)}))



