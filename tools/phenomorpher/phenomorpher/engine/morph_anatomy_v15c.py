"""One anatomy-preserving morphology pass from connected Stage1 geometry.

References supply soft size/character guides, never scanline acceptance targets.
No legacy morph pipeline, independent cap restore or bilateral-center warp.
"""
import hashlib
import numpy as np
from .target_contract import PART_JOINTS
from .check_terminal_connectivity_v13 import SEGMENTS,LINKS
from .fit_scale_position_v13a import source_terminal_evidence,terminal_contact
from .morph_preview_pose_v13 import pose_rigid_meshes

REGIONS={'torso':('chest','pelvis'),**{p:(p,) for p in SEGMENTS}}

def copy_meshes(meshes):return [{**m,'position':np.asarray(m['position']).copy(),'faces':np.asarray(m['faces']).copy()} for m in meshes]
def geometry_hash(meshes):
 h=hashlib.sha256()
 for m in meshes:
  h.update((m['part']+'\0'+m['name']).encode());h.update(np.asarray(m['position'],dtype='<f8').tobytes());h.update(np.asarray(m['faces'],dtype='<i8').tobytes())
 return h.hexdigest()
def plane_dimension(meshes,origin,normal,direction):
 values=[]
 for m in meshes:
  if not m.get('render',True):continue
  tri=np.asarray(m['position'])[np.asarray(m['faces'],int)];dist=(tri-origin)@normal
  for a,b in ((0,1),(1,2),(2,0)):
   on=np.abs(dist[:,a])<1e-10;values.extend(((tri[on,a]-origin)@direction).tolist());hit=dist[:,a]*dist[:,b]<0
   t=dist[hit,a]/(dist[hit,a]-dist[hit,b]);p=tri[hit,a]+t[:,None]*(tri[hit,b]-tri[hit,a]);values.extend(((p-origin)@direction).tolist())
 return None if len(values)<2 else float(max(values)-min(values))
def guide(row,fallback):
 row=dict(fallback or {})|dict(row or {});preferred=row.get('preferredMeters',row.get('modelFittingMeters'))
 if preferred is None:return None
 preferred=float(preferred);slack=float(row.get('designSlackFraction',.10));confidence_label=row.get('confidence',.65)
 if isinstance(confidence_label,str):
  if confidence_label not in ('low','medium','high','unavailable'):raise ValueError('Known confidence label required')
  confidence=float(row.get('confidenceWeight',{'low':.35,'medium':.7,'high':.9,'unavailable':0.}[confidence_label]))
 else:confidence=float(row.get('confidenceWeight',confidence_label))
 uncertainty=row.get('measurementUncertaintyMeters',row.get('uncertaintyMeters'))
 if not np.isfinite([preferred,slack,confidence]).all() or preferred<=0 or not 0<=slack<1 or not 0<=confidence<=1:raise ValueError('Finite positive soft guide and bounded confidence/slack required')
 return {'preferredMeters':preferred,'designSlackFraction':slack,'measurementUncertaintyMeters':uncertainty,'confidence':confidence_label,'confidenceWeight':confidence,'guideOnly':bool(row.get('guideOnly',True))}
def soft_factor(actual,row):
 if actual is None or actual<=1e-8 or row is None:return None
 # Measurement uncertainty is reported separately and never added to design slack.
 nearest=float(np.clip(actual,row['preferredMeters']*(1-row['designSlackFraction']),row['preferredMeters']*(1+row['designSlackFraction'])))
 return 1+row['confidenceWeight']*(nearest/actual-1)
def regional_frame(meshes,frames,region):
 parts=REGIONS[region];cloud=np.concatenate([m['position'] for m in meshes if m['part'] in parts and m.get('render',True)])
 if region=='torso':origin=np.asarray(frames['pelvis_g'])[:3,3];end=np.asarray(frames['neck_g'])[:3,3]
 else:a,b=SEGMENTS[region];origin=np.asarray(frames[a])[:3,3];end=np.asarray(frames[b])[:3,3]
 axis=end-origin;length=float(np.linalg.norm(axis))
 if length<1e-9:raise ValueError('Authored regional longitudinal axis is degenerate')
 axis/=length;width=np.array([1.,0,0])-axis[0]*axis
 if np.linalg.norm(width)<1e-8:width=np.array([0.,1,0])-axis[1]*axis
 width/=np.linalg.norm(width);depth=np.cross(axis,width);depth/=np.linalg.norm(depth)
 projected=(cloud-origin)@axis
 low=float(projected.min()) if region=='torso' else 0.;high=length
 if high<=low:raise ValueError('Source regional anatomy has no eligible span')
 return origin,axis,width,depth,low,high

def deform_region(source,region,frame,factors,fraction=1.):
 result=copy_meshes(source);origin,axis,width,depth,low,high=frame
 for m in result:
  if m['part'] not in REGIONS[region]:continue
  p=m['position'];relative=p-origin;longitudinal=relative@axis;t=np.clip((longitudinal-low)/(high-low),0,1)
  # Smooth full-anatomy bell, zero value/derivative at authored axial limits.
  weight=np.sin(np.pi*t)**2;weight[(longitudinal<=low)|(longitudinal>=high)]=0
  for direction,factor in zip((width,depth),factors):p+=fraction*weight[:,None]*(factor-1)*(relative@direction)[:,None]*direction
 return result

def measurements(meshes,frames,packet):
 cloud=np.concatenate([m['position'] for m in meshes if m.get('render',True)]);ground=cloud[:,2].min();height=np.ptp(cloud[:,2]);rows={}
 for section,parts in (('chest',('chest','pelvis')),('waist',('chest','pelvis')),('midThigh',('legl','legr')),('knee',('legl','legr','shinl','shinr')),('calf',('shinl','shinr')),('ankle',('shinl','shinr','footl','footr'))):
  fraction=packet.get('views',{}).get('front',{}).get(section+'Height',{}).get('value')
  if fraction is None:continue
  origin=np.array([0.,0.,ground+height*float(fraction)])
  groups=[parts] if section in ('chest','waist') else [tuple(p for p in parts if p.endswith(side)) for side in ('l','r')]
  for axis,suffix in ((np.array([1.,0,0]),'Width'),(np.array([0.,1,0]),'Depth')):
   values=[plane_dimension([m for m in meshes if m['part'] in group],origin,np.array([0.,0,1]),axis) for group in groups];rows[section+suffix]=None if any(x is None for x in values) else float(np.mean(values))
 for key,parts in (('upperArmWidth',('bicepl','bicepr')),('forearmWidth',('forel','forer'))):
  values=[]
  for part in parts:
   a,b=SEGMENTS[part]
   if a not in frames or b not in frames or not any(m['part']==part and m.get('render',True) for m in meshes):
    values.append(None);continue
   start=np.asarray(frames[a])[:3,3];end=np.asarray(frames[b])[:3,3];normal=end-start;normal[1]=0
   if np.linalg.norm(normal)<1e-9:values.append(None);continue
   normal/=np.linalg.norm(normal);direction=np.array([-normal[2],0,normal[0]]);values.append(plane_dimension([m for m in meshes if m['part']==part],.5*(start+end),normal,direction))
  rows[key]=None if any(x is None for x in values) else float(np.mean(values))
 for suffix,axis in (('Width',0),('Depth',1)):
  values=[]
  for part in ('footl','footr'):
   points=[m['position'] for m in meshes if m['part']==part and m.get('render',True)]
   values.append(None if not points else float(np.ptp(np.concatenate(points)[:,axis])))
  rows['foot'+suffix]=None if any(v is None for v in values) else float(np.mean(values))
 return rows

def trunk_similarity(source_frames,target_frames,part_scales):
 def basis(frames):
  origin=np.asarray(frames['pelvis_g'])[:3,3];axis=np.asarray(frames['neck_g'])[:3,3]-origin;length=float(np.linalg.norm(axis))
  if length<1e-9:raise ValueError('Source/fitted trunk axis degenerate')
  axis/=length;seed=np.asarray(frames['pelvis_g'])[:3,0];width=seed-np.dot(seed,axis)*axis
  if np.linalg.norm(width)<1e-9:raise ValueError('Trunk has no authored pelvic transverse basis')
  width/=np.linalg.norm(width);return origin,np.column_stack((width,np.cross(axis,width),axis)),length
 source,before,length=basis(source_frames);target,after,new_length=basis(target_frames)
 scales=[float(part_scales[p]) for p in ('chest','pelvis')]
 if not np.isfinite(scales).all() or min(scales)<=0 or abs(scales[0]-scales[1])>1e-8*max(scales) or abs(new_length/length-scales[0])>1e-8*max(scales):raise ValueError('Chest/pelvis do not share one fitted trunk similarity')
 matrix=np.eye(4);matrix[:3,:3]=scales[0]*after@before.T;matrix[:3,3]=target-matrix[:3,:3]@source;return matrix

def owner_similarity(source_frames,target_frames,part_scales,part):
 owner=PART_JOINTS[part];source=np.asarray(source_frames[owner]);target=np.asarray(target_frames[owner]);scale=float(part_scales[part])
 if not np.isfinite(scale) or scale<=0:raise ValueError('Positive source-owned part similarity required')
 matrix=np.eye(4);matrix[:3,:3]=scale*target[:3,:3]@source[:3,:3].T;matrix[:3,3]=target[:3,3]-matrix[:3,:3]@source[:3,3];return matrix

def build_registration(stage1,packet):
 rows={};source_meshes=stage1.get('sourceStandingMeshes');source_frames=stage1.get('sourceStandingFrames');target_frames=stage1['standingFrames'];provenance=packet.get('canonicalCalibration',{});parts_scales=stage1.get('partScales',{})
 if source_meshes and source_frames:
  cloud=np.concatenate([m['position'] for m in source_meshes if m.get('render',True)]);floor=float(cloud[:,2].min());height=float(np.ptp(cloud[:,2]))
 else:floor=height=None
 frame_hash=hashlib.sha256()
 for name,frame in sorted((source_frames or {}).items()):frame_hash.update(name.encode()+b'\0');frame_hash.update(np.asarray(frame,dtype='<f8').tobytes())
 source_binding={'sourceStandingGeometryHash':geometry_hash(source_meshes) if source_meshes else None,'sourceStandingFramesHash':frame_hash.hexdigest()}
 mappings={'chest':[(('chest','pelvis'),'torso')],'waist':[(('chest','pelvis'),'torso')],'midThigh':[(('legl',),'legl'),(('legr',),'legr')],'knee':[(('legl','shinl'),'legl'),(('legr','shinr'),'legr')],'calf':[(('shinl',),'shinl'),(('shinr',),'shinr')],'ankle':[(('shinl','footl'),'shinl'),(('shinr','footr'),'shinr')]}
 for key,guide_row in packet.get('proposedTargets',{}).items():
  suffix='Width' if key.endswith('Width') else 'Depth' if key.endswith('Depth') else None;section=key[:-len(suffix)] if suffix else None
  if section not in mappings:continue
  row={'sourceFraction':guide_row.get('sourceFraction'),'destinationReferenceFraction':guide_row.get('destinationFraction',packet.get('views',{}).get('front',{}).get(section+'Height',{}).get('value')),'sourceDonorId':provenance.get('sourceDonorId'),'sourceAnatomyBinding':source_binding,'status':'unavailable'}
  try:
   if source_meshes is None or source_frames is None or not provenance.get('sourceDonorId'):raise ValueError('Frozen source anatomy provenance absent')
   bound_frames=provenance.get('sourceCanonicalJointFramesMeters',{})
   needed={'pelvis_g','neck_g'} if section in ('chest','waist') else {PART_JOINTS[part] for groups,owner in mappings[section] for part in groups}
   if any(n not in bound_frames or n not in source_frames or not np.allclose(np.asarray(bound_frames[n]),np.asarray(source_frames[n]),atol=1e-8,rtol=0) for n in needed):raise ValueError('Source canonical owner frame binding differs or missing')
   recorded_height=guide_row.get('sourceStandingStatureMeters')
   if recorded_height is not None and abs(float(recorded_height)-height)>1e-8:raise ValueError('Source standing stature binding differs')
   z=guide_row.get('sourcePlaneZMeters')
   if z is None:
    if row['sourceFraction'] is None:raise ValueError('Source-owned section height unavailable')
    z=floor+height*float(row['sourceFraction'])
   z=float(z)
   if not np.isfinite(z) or not floor<=z<=floor+height:raise ValueError('Source plane outside source anatomy')
   if row['sourceFraction'] is not None and abs(z-(floor+height*float(row['sourceFraction'])))>1e-8:raise ValueError('Source section fraction/plane disagree')
   point=np.array([0.,0.,z]);normal=np.array([0.,0.,1.]);direction=np.array([1.,0.,0.]) if suffix=='Width' else np.array([0.,1.,0.]);transports=[]
   source_values=[plane_dimension([m for m in source_meshes if m['part'] in owned],point,normal,direction) for owned,owner in mappings[section]]
   if any(v is None for v in source_values):raise ValueError('Bound source plane has unavailable source-part contour')
   measured_source=float(np.mean(source_values));recorded_dimension=guide_row.get('nativeDonorDimensionMeters')
   if recorded_dimension is not None and abs(measured_source-float(recorded_dimension))>1e-8:raise ValueError('Bound source anatomical dimension differs from calibrated donor')
   row['remeasuredSourceNativeDimensionMeters']=measured_source;row['calibratedSourceNativeDimensionMeters']=recorded_dimension
   for owned,owner in mappings[section]:
    matrix=trunk_similarity(source_frames,target_frames,parts_scales) if owner=='torso' else owner_similarity(source_frames,target_frames,parts_scales,owner)
    candidate_point=matrix[:3,:3]@point+matrix[:3,3];candidate_normal=np.linalg.inv(matrix[:3,:3]).T@normal;candidate_normal/=np.linalg.norm(candidate_normal);candidate_direction=matrix[:3,:3]@direction;candidate_direction/=np.linalg.norm(candidate_direction)
    if owner!='torso' and len(owned)>1:
     for component in owned:
      component_matrix=owner_similarity(source_frames,target_frames,parts_scales,component);p=component_matrix[:3,:3]@point+component_matrix[:3,3];n=np.linalg.inv(component_matrix[:3,:3]).T@normal;n/=np.linalg.norm(n);d=component_matrix[:3,:3]@direction;d/=np.linalg.norm(d)
      if abs(float(np.dot(p-candidate_point,candidate_normal)))>1e-8 or not np.allclose(n,candidate_normal,atol=1e-8,rtol=0) or not np.allclose(d,candidate_direction,atol=1e-8,rtol=0):raise ValueError('Piecewise fitted joint union has no single transported source plane')
    transports.append({'parts':list(owned),'ownerBasis':owner,'sourceToCandidateSimilarity':matrix.tolist(),'candidatePlanePointMeters':candidate_point.tolist(),'candidatePlaneNormal':candidate_normal.tolist(),'candidateProjectedDimensionDirection':candidate_direction.tolist()})
   row.update(status='registered-source-anatomical-plane',sourcePlanePointMeters=point.tolist(),sourcePlaneNormal=normal.tolist(),sourceProjectedDimensionDirection=direction.tolist(),sourceStandingFloorMeters=floor,sourceStandingStatureMeters=height,transports=transports,referencePlaneIsMeasurementPlane=False,scope='Exact source anatomical plane transported under source-owned fitted similarities; destination art fractions are separate diagnostics')
  except (ValueError,KeyError,TypeError) as error:row['reason']=str(error)
  rows[key]=row
 return rows

def registered_measurements(meshes,frames,packet,registration):
 rows=measurements(meshes,frames,packet)
 for key,row in registration.items():
  if row['status']!='registered-source-anatomical-plane':rows[key]=None;continue
  values=[]
  for transport in row['transports']:
   groups=[m for m in meshes if m['part'] in transport['parts']]
   values.append(plane_dimension(groups,np.asarray(transport['candidatePlanePointMeters']),np.asarray(transport['candidatePlaneNormal']),np.asarray(transport['candidateProjectedDimensionDirection'])))
  rows[key]=None if any(value is None for value in values) else float(np.mean(values))
 return rows

def smooth_log_profile(z,anchors):
    """Positive nonovershooting C1 factor; zero slopes at context boundaries."""
    anchors=np.asarray(anchors,float);q=np.asarray(z,float)
    if len(anchors)<2 or np.any(np.diff(anchors[:,0])<=0) or not np.isfinite(anchors).all() or np.any(anchors[:,1]<=0):raise ValueError('Ordered positive broad anatomy factors required')
    x=anchors[:,0];y=np.log(anchors[:,1]);h=np.diff(x);delta=np.diff(y)/h;m=np.zeros(len(x))
    for i in range(1,len(x)-1):
        if delta[i-1]*delta[i]>0:
            w1=2*h[i]+h[i-1];w2=h[i]+2*h[i-1];m[i]=(w1+w2)/(w1/delta[i-1]+w2/delta[i])
    index=np.clip(np.searchsorted(x,q,side='right')-1,0,len(x)-2);t=np.clip((q-x[index])/h[index],0,1)
    value=(2*t**3-3*t**2+1)*y[index]+(t**3-2*t**2+t)*h[index]*m[index]+(-2*t**3+3*t**2)*y[index+1]+(t**3-t**2)*h[index]*m[index+1]
    return np.where((q<=x[0])|(q>=x[-1]),1.,np.exp(value))

def coordinated_torso_profile(source,frame,initial,guides,registration,bounds):
    origin,axis,width,depth,low,high=frame;profiles=[]
    for suffix in ('Width','Depth'):
        anchors=[(low,1.),(high,1.)];goals=[]
        for section in ('waist','chest'):
            key=section+suffix;registered=registration.get(key,{});row=guides.get(key);factor=soft_factor(initial.get(key),row)
            if factor is None or registered.get('status')!='registered-source-anatomical-plane':continue
            transports=registered['transports']
            if len(transports)!=1 or transports[0]['ownerBasis']!='torso':raise ValueError('Torso preference requires one shared registered anatomy frame')
            transport=transports[0];normal=np.asarray(transport['candidatePlaneNormal']);point=np.asarray(transport['candidatePlanePointMeters']);denominator=float(np.dot(normal,axis))
            if abs(denominator)<1e-8:raise ValueError('Registered torso section is parallel to trunk axis')
            coordinate=float(np.dot(normal,point-origin)/denominator)
            if not low<coordinate<high:raise ValueError('Registered torso section outside broad source anatomy')
            factor=float(np.clip(factor,*bounds));anchors.append((coordinate,factor));goals.append({'key':key,'longitudinalCoordinateMeters':coordinate,'requestedSoftRadialFactor':factor,'preferredMeters':row['preferredMeters'],'confidenceWeight':row['confidenceWeight'],'sourceInitialDimensionMeters':initial[key]})
        if len(goals)==2 and goals[0]['longitudinalCoordinateMeters']>=goals[1]['longitudinalCoordinateMeters']:raise ValueError('Registered waist/chest anatomy order is invalid')
        anchors.sort()
        if any(b[0]-a[0]<.01*(high-low) for a,b in zip(anchors,anchors[1:])):raise ValueError('Torso preference anchors would concentrate shaping in a short span')
        profiles.append({'axis':suffix,'anchors':anchors,'goals':goals,'interpolation':'C1 nonovershooting log radial factor; zero derivative at context boundaries; exact source detail remains'})
    result=copy_meshes(source)
    for m in result:
        if m['part'] not in ('chest','pelvis'):continue
        relative=m['position']-origin;coordinate=relative@axis
        for direction,profile in zip((width,depth),profiles):
            factors=smooth_log_profile(coordinate,profile['anchors']);m['position']+=(factors-1)[:,None]*(relative@direction)[:,None]*direction
    return result,{'kind':'coordinated-source-anatomy-torso-profile-v15c','contextIntervalMeters':[low,high],'profiles':profiles,'sharedChestPelvisFrame':True,'sourceGeometryHash':geometry_hash(source),'exactScanlineEnvelopeFitting':False,'sourceTerminalRestoreLayerApplied':False,'fieldStackingApplied':False,'profileFactorsAreNotAssetApprovals':True}

class ContactBaseline:
 def __init__(self,source,frames,motion):
  self.inventories,self.standing,_=source_terminal_evidence(source,frames);self.samples=[{'clip':'pause1','timeSeconds':0.,'jointWorldMatrices':frames}]+list(motion);self.source=source;self.frames=frames;self.baselines=[]
  for sample in self.samples:
   posed=pose_rigid_meshes(source,frames,sample['jointWorldMatrices']);self.baselines.append({pair:terminal_contact(posed,inv)['minimumTriangleClearanceMeters'] for pair,inv in self.inventories.items()})
 def check(self,meshes,parts=None):
  rows=[];passed=True
  for sample,baseline in zip(self.samples,self.baselines):
   posed=pose_rigid_meshes(meshes,self.frames,sample['jointWorldMatrices'])
   for pair,inv in self.inventories.items():
    if parts is not None and not set(pair)&set(parts):continue
    actual=terminal_contact(posed,inv);limit=baseline[pair];gate=actual['minimumTriangleClearanceMeters']<=limit+1e-8;passed=passed and gate
    rows.append({'parts':list(pair),'clip':sample['clip'],'timeSeconds':sample['timeSeconds'],**actual,'sourceStage1ClearanceMeters':limit,'sourceCalibratedTerminalGatePassed':gate,'numericalEpsilonMeters':1e-8})
  return passed,rows

def fit_stage2(stage1,packet,policy,preserve=False):
 source=copy_meshes(stage1['standingMeshes']);frames=stage1['standingFrames'];policy=policy or {};registration=build_registration(stage1,packet);initial=registered_measurements(source,frames,packet,registration);guides={key:guide(policy.get('measurements',{}).get(key),row) for key,row in packet.get('proposedTargets',{}).items()}
 for key,row in policy.get('measurements',{}).items():guides[key]=guide(row,packet.get('proposedTargets',{}).get(key))
 result={**stage1};result['standingMeshes']=copy_meshes(source);result['bindMeshes']=copy_meshes(stage1['bindMeshes'])
 if preserve:
  result['receipt']={**stage1.get('receipt',{}),'kind':'anatomy-first-stage2-v15c','identityPreserved':True,'shapeMorphApplied':False,'sourceGeometryHash':geometry_hash(source),'previewGeometryHash':geometry_hash(source),'assetApprovalCreated':False,'visualAcceptance':False,'motionAcceptance':False,'productionAccepted':False};return result
 bounds=policy.get('factorBounds',[.75,1.5])
 if not 0<bounds[0]<=1<=bounds[1]:raise ValueError('Positive conservative factor bounds required')
 motion=policy.get('motionSamples',[]);checker=ContactBaseline(source,frames,motion);cumulative=copy_meshes(source);regions=[];deferred=[]
 for region,parts in REGIONS.items():
  if not any(m['part'] in parts and m.get('render',True) for m in source):continue
  keys=('chest','waist') if region=='torso' else (('upperArm',) if region.startswith('bicep') else ('forearm',) if region.startswith('fore') else ('midThigh',) if region.startswith('leg') else ('calf',))
  factors=[];used=[]
  for suffix in ('Width','Depth'):
   proposals=[];weights=[]
   for prefix in keys:
    key=prefix+suffix;row=guides.get(key);ratio=soft_factor(initial.get(key),row)
    if ratio is not None and row['confidenceWeight']>0:proposals.append(np.log(ratio));weights.append(row['confidenceWeight']);used.append(key)
   factor=1. if not proposals else float(np.exp(np.average(proposals,weights=weights)));factors.append(float(np.clip(factor,*bounds)))
  frame=regional_frame(source,frames,region);profile_receipt=None
  if region=='torso':
   try:regional,profile_receipt=coordinated_torso_profile(source,frame,initial,guides,registration,bounds)
   except ValueError as error:
    regional=copy_meshes(source);profile_receipt={'status':'unavailable','reason':str(error)};deferred.append({'region':'torso','reason':'Registered coherent torso profile unavailable: '+str(error)})
  else:regional=deform_region(source,region,frame,factors)
  delta={i:m['position']-s['position'] for i,(m,s) in enumerate(zip(regional,source)) if m['part'] in parts};trials=[];chosen=None
  for fraction in (1.,.75,.5,.25,0.):
   trial=copy_meshes(cumulative)
   for i,d in delta.items():trial[i]['position']+=fraction*d
   passed,contacts=checker.check(trial,parts);trials.append({'fraction':fraction,'passed':passed,'contacts':contacts})
   if passed:chosen=trial;break
  if chosen is None:raise ValueError('Unmodified Stage1 contact baseline cannot be replayed')
  cumulative=chosen;regions.append({'region':region,'parts':list(parts),'requestedRadialFactors':None if region=='torso' else factors,'averagedPreferenceDiagnostic':factors if region=='torso' else None,'retainedRegionalFraction':fraction,'guideKeys':sorted(set(used)),'coordinatedProfile':profile_receipt,'trials':trials,'shapeBasis':('Fresh source anatomy with shared C1 longitudinal log factors at registered waist/chest; context endpoint derivative zero' if region=='torso' else 'Fresh source anatomy about fixed authored limb axis; broad smooth bell with exact axial endpoint preservation')})
  if fraction<1:deferred.append({'region':region,'reason':'Source-calibrated contact conflicts; only this region backed off','retainedRegionalFraction':fraction})
 passed,contacts=checker.check(cumulative)
 if not passed:raise ValueError('Cumulative anatomy pass lost a source-calibrated terminal gate')
 actual=registered_measurements(cumulative,frames,packet,registration);rows={}
 for key,row in guides.items():
  if row is None:continue
  value=actual.get(key);preferred=row['preferredMeters'];rows[key]={**row,'actualMeters':value,'deviationMeters':None if value is None else value-preferred,'deviationFraction':None if value is None else value/preferred-1,'withinDesignSlack':None if value is None else abs(value/preferred-1)<=row['designSlackFraction'],'reason':'Source anatomy/contact preservation and confidence-weighted conservative regional guide','approval':False}
 for old,new in zip(source,cumulative):
  if not np.array_equal(old['faces'],new['faces']):raise ValueError('Topology changed')
  if old['part'] not in set(sum((list(x) for x in REGIONS.values()),[])) and not np.array_equal(old['position'],new['position']):raise ValueError('Protected head/neck/hand/foot geometry changed')
 result['standingMeshes']=cumulative;result['bindMeshes']=pose_rigid_meshes(cumulative,frames,stage1['bindFrames'])
 for i,(old,new) in enumerate(zip(source,cumulative)):
  if np.array_equal(old['position'],new['position']):result['bindMeshes'][i]=copy_meshes([stage1['bindMeshes'][i]])[0]
 result['receipt']={**stage1.get('receipt',{}),'kind':'anatomy-first-stage2-v15c','stageOrder':['connected Stage1 transforms','single source-preserving regional anatomy pass'],'identityPreserved':False,'shapeMorphApplied':geometry_hash(cumulative)!=geometry_hash(source),'sourceGeometryHash':geometry_hash(source),'previewGeometryHash':geometry_hash(cumulative),'regions':regions,'guideMeasurements':rows,'residuals':rows,'deferred':deferred,'sourceAnatomicalRegistration':registration,'sourceAnatomicalInitialMeasurementsMeters':initial,'terminalContacts':contacts,'allRequiredSourceCalibratedTerminalGates':passed,'motionContactSamplesProvided':len(motion),'motionContactValidationPending':not bool(motion),'rigFramesChanged':False,'headNeckHandsFeetProtected':True,'designSlackFractionDefault':.10,'measurementUncertaintyAddedToSlack':False,'assetApprovalCreated':False,'visualAcceptance':False,'motionAcceptance':False,'productionAccepted':False,'limitations':['Source-scaled anatomy is preferred over precise reference scanlines','Regional backoff can leave preferred dimensions outside design slack; deviations remain explicit','Minimum triangle contact does not establish adequate overlap coverage or visible anatomy','Broader motion/native/client validation and manual anatomy review remain required']};return result
