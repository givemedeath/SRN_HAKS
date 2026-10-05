"""Build measured broadened Human-derived rigs without generation-pose inputs."""
import argparse
import copy
import json
from pathlib import Path
import re
import shutil
import sys
import numpy as np

from retarget import NODE, nodes, transforms, signature, rotation_signature
from target_contract import PART_JOINTS, require, sha, validate
from rig_controller_audit import (effective_nodes, world_frames,
    compatible_parent_basis, preserved_controller_signature, arrays)

KEY = re.compile(r'(?m)^([ \t]*)(position(?:bezier)?key)(?:[ \t]+(\d+))?[ \t]*\n')

def widen(skeleton, shoulder_span, hip_span):
    """Change world X of proximal pivots, retaining parent-local limb lengths."""
    source = copy.deepcopy(skeleton)
    result = copy.deepcopy(skeleton)
    source_world = world_frames(source)
    changed = {}
    for left, right, span in [('lbicep_g','rbicep_g',shoulder_span),
                              ('lthigh_g','rthigh_g',hip_span)]:
        require(np.isfinite(span) and span > 0, 'Positive measured joint span required')
        centre = (source_world[left][0,3]+source_world[right][0,3])/2
        for name, sign in [(left,-1),(right,1)]:
            target = source_world[name][:3,3].copy()
            target[0] = centre + sign*span/2
            parent = result[name]['parent']
            parent_world = world_frames(result)[parent]
            result[name]['position'] = (np.linalg.inv(parent_world) @ np.r_[target,1])[:3]
            changed[name] = (result[name]['position']-source[name]['position']).tolist()
    for name, row in source.items():
        require(result[name]['orientation'] == row['orientation'], 'Bind rotation changed')
        require(result[name]['parent'] == row['parent'], 'Hierarchy changed')
        if name not in changed:
            require(np.array_equal(result[name]['position'],row['position']), 'Dependent local offset changed')
    return result, changed

def transform_keys(rows, source_bind, target_bind, scale, bezier=False, *, bezier_semantics=None):
    rows = np.asarray(rows, dtype=float)
    require(np.isfinite(scale) and scale > 0, 'Positive finite controller scale required')
    widths = (4,7,10) if bezier else (4,)
    require(rows.ndim == 2 and rows.shape[1] in widths and np.isfinite(rows).all(),
            'Invalid positional controller rows')
    source_bind, target_bind = np.asarray(source_bind), np.asarray(target_bind)
    require(source_bind.shape == target_bind.shape == (3,) and
            np.isfinite(source_bind).all() and np.isfinite(target_bind).all(), 'Invalid local bind')
    result = rows.copy()
    result[:,1:4] = target_bind + scale*(rows[:,1:4]-source_bind)
    if bezier:
        # The controller label alone does not establish whether the extra
        # triples are parent-local points or displacements from the key.
        # Require a reviewed encoding declaration; never guess from values.
        require(bezier_semantics in ('parent-local-points','relative-handles'),
                'Reviewed positional Bezier semantics required')
        for column in range(4,rows.shape[1],3):
            values = rows[:,column:column+3]
            result[:,column:column+3] = (target_bind+scale*(values-source_bind)
                if bezier_semantics == 'parent-local-points' else scale*values)
    require(np.array_equal(result[:,0],rows[:,0]), 'Key times changed')
    return result

def resolve_bind(name, source_name, chain_nodes, parents, root_nodes):
    current = source_name
    visited = set()
    while current != 'null':
        require(current not in visited, 'Supermodel inheritance cycle')
        visited.add(current)
        require(current in chain_nodes and current in parents, 'Missing supermodel bind inventory: '+current)
        if name in chain_nodes[current]:
            return chain_nodes[current][name], current
        current = parents[current]
    require(name in root_nodes, 'Unresolved inherited animation bind: ' + name)
    return root_nodes[name], 'pmh0'

def replace_position(body, value):
    line = '  position ' + ' '.join(format(float(v),'.12g') for v in value)
    pattern = r'(?m)^[ \t]*position[ \t]+[^\n]+'
    return re.sub(pattern,line,body) if re.search(pattern,body) else body.rstrip()+'\n'+line+'\n'

def replace_field(body, field, value):
    line = '  '+field+' '+value
    pattern = r'(?mi)^[ \t]*'+re.escape(field)+r'[ \t]+[^\n]+'
    return re.sub(pattern,line,body) if re.search(pattern,body) else body.rstrip()+'\n'+line+'\n'

def scale_vector_arrays(body, scale):
    require(not re.search(r'(?mi)^\s*(weights|bonemap|boneweights)\s',body),
            'Skinned supermodel geometry needs explicit bind-data handling')
    match = re.search(r'(?m)^([ \t]*)verts\s+(\d+)[ \t]*\n',body)
    if not match:
        return body
    lines = body[match.end():].splitlines(keepends=True)
    count = int(match[2]); rows = lines[:count]
    require(len(rows)==count, 'Truncated geometry vertex array')
    values = np.asarray([[float(x) for x in row.split()] for row in rows])
    require(values.shape == (count,3), 'Unexpected geometry vertex arity')
    output = ''.join('    '+' '.join(format(float(v),'.12g') for v in row)+'\n' for row in values*scale)
    return body[:match.end()]+output+''.join(lines[count:])

def export_model(text, name, alias, parent_alias, scale, deltas, chain_nodes, parents, root_nodes,
                 *, bezier_semantics=None, target_nodes=None):
    """Retain declared geometry/controller ownership and untouched controller text."""
    require('endmodelgeom' in text, 'Model geometry boundary missing')
    head, tail = text.split('endmodelgeom',1)
    audits = []
    source_effective = effective_nodes(name,chain_nodes,parents,root_nodes)
    target_effective = copy.deepcopy(source_effective)
    target_root = target_nodes if target_nodes is not None else root_nodes
    for key,row in target_root.items():
        if key == 'pmh0':
            continue
        target_effective[key] = copy.deepcopy(row)
        # Each private supermodel's root is an identity alias; its core nodes
        # must use the phenotype's Human-derived hierarchy and bind positions.
        if target_effective[key]['parent'] == 'pmh0':
            target_effective[key]['parent'] = name
    source_frames = world_frames(source_effective)
    target_frames = world_frames(target_effective)
    def target_row(key, source_row):
        if target_nodes is not None and key in target_nodes:
            return target_effective[key], 'pmh0'
        result = copy.deepcopy(source_row)
        result['position'] += np.asarray(deltas.get(key,[0,0,0]))
        return result, 'inherited-private-copy'
    def geometry_node(match):
        key = match[2].lower()
        node_scale=re.search(r'(?mi)^\s*scale\s+(\S+)',match[3])
        require(node_scale is None or float(node_scale[1])==1.,
                'Non-unit geometry node scale requires explicit frame handling: '+key)
        row = nodes('node '+match[1]+' '+match[2]+'\n'+match[3]+'endnode')[key]
        target, _ = target_row(key,row)
        body = replace_position(match[3], target['position']*scale)
        if target_nodes is not None and key in target_nodes and key != 'pmh0':
            body = replace_field(body,'parent',target['parent'])
            body = replace_field(body,'orientation',' '.join(format(float(v),'.12g')
                                 for v in target['orientation']))
        body = scale_vector_arrays(body,scale)
        return 'node '+match[1]+' '+match[2]+'\n'+body+'endnode'
    head = NODE.sub(geometry_node,head)
    def animation_node(match):
        key = match[2].lower(); body = match[3]
        row, owner = resolve_bind(key,name,chain_nodes,parents,root_nodes)
        source_bind = row['position']
        target, target_owner = target_row(key,row)
        target_bind = target['position']*scale
        declared_parent = re.search(r'(?mi)^\s*parent\s+(\S+)',body)
        require(declared_parent and declared_parent[1].lower()==row['parent'],
                'Animation parent differs from its source bind: '+key)
        spatial = bool(KEY.search(body) or re.search(
            r'(?mi)^\s*(position|orientation(?:bezier)?key|orientation)\s',body))
        basis_error = (compatible_parent_basis(row,target,source_frames,target_frames)
                       if spatial else None)
        audits.append({'node':key,'sourceBindOwner':owner,'targetBindOwner':target_owner,
                       'controller':'binding','sourceParentLocalSpace':row['parent'],
                       'targetParentLocalSpace':target['parent'],
                       'parentBasisMaxError':basis_error,'spatialController':spatial,
                       'sourceBind':source_bind.tolist(),'targetBind':target_bind.tolist(),
                       'orientationControllerPreserved':True})
        if target_nodes is not None and key in target_nodes:
            body = replace_field(body,'parent',target['parent'])
        parsed_arrays={start:(label,values,end) for label,values,start,end in arrays(body)}
        def keys(block):
            indent,label=block[1],block[2]
            parsed_label,values,end=parsed_arrays[block.start()]
            require(parsed_label==label,'Controller parser mismatch')
            count=len(values)
            rows=[line for line in body[block.end():end].splitlines(keepends=True)
                  if line.strip() and line.strip().lower()!='endlist' and
                  not line.lstrip().startswith('#')]
            transformed = transform_keys(values,source_bind,target_bind,scale,label=='positionbezierkey',
                                         bezier_semantics=bezier_semantics)
            serialized = ''.join(indent+'  '+original.split()[0]+' '+
                ' '.join(format(float(v),'.12g') for v in line[1:])+'\n'
                for original,line in zip(rows,transformed))
            audits.append({'node':key,'sourceBindOwner':owner,'controller':label,'keys':count,
                           'sourceBind':source_bind.tolist(),'targetBind':target_bind.tolist()})
            if block[3] is None:
                serialized+=indent+'endlist\n'
            return block.start(),end,block[0]+serialized
        replacements = [keys(block) for block in KEY.finditer(body)]
        for start,end,replacement in reversed(replacements):
            body = body[:start]+replacement+body[end:]
        static = re.search(r'(?m)^\s*position\s+([^\n]+)',body)
        if static:
            values = np.asarray([float(x) for x in static[1].split()])
            require(values.shape==(3,), 'Invalid static animation position')
            body = replace_position(body,target_bind+scale*(values-source_bind))
            audits.append({'node':key,'sourceBindOwner':owner,'controller':'position','keys':1})
        # Every nonpositional controller, including static rotations, must
        # retain its exact serialized values. Node/model aliases are separate.
        if not replacements and not static and not (target_nodes is not None and key in target_nodes):
            return match[0]
        return '  node '+match[1]+' '+match[2]+'\n'+body+'  endnode'
    tail = NODE.sub(animation_node,tail)
    result = head+'endmodelgeom'+tail
    result = re.sub(r'(?mi)^setsupermodel\s+\S+\s+\S+',
                    'setsupermodel '+alias+' '+parent_alias,result)
    result = re.sub(r'(?i)\b'+re.escape(name)+r'\b',alias,result)
    require(signature(result)==signature(text), 'Clip timing/events changed')
    before = rotation_signature(text); after = rotation_signature(result)
    # Root model aliases may appear as animation node identifiers.
    before = [(c,alias if n==name else n,k,v) for c,n,k,v in before]
    require(after==before, 'Animation rotation controller changed')
    require(preserved_controller_signature(result)==
            preserved_controller_signature(text,{name:alias}),
            'Controller values, order, type, or ownership changed')
    return result,audits

def build(baseline, output, extra_supermodels=()):
    require(not output.exists(), 'Fresh target rig directory required')
    inventory=json.loads((baseline/'baseline.json').read_text())
    measurements=json.loads((baseline/'race-measurements.json').read_text())
    height=1.9339157; scale=10/7; orc_factor=height/measurements['pmo0']['height']
    shoulder=measurements['pmo0']['shoulderSpan']*orc_factor
    hip=measurements['pmo0']['hipSpan']*orc_factor
    root_text=(baseline/'ascii/pmh0.mdl').read_text(encoding='cp1252')
    source=nodes(root_text); working,deltas=widen(source,shoulder,hip)
    chain=[]; current='pmh0'; parents={}; texts={}
    while current!='null':
        require(current not in chain,'Animation inheritance cycle')
        chain.append(current); parents[current]=inventory['animations'][current]['supermodel']
        texts[current]=(baseline/'ascii'/(current+'.mdl')).read_text(encoding='cp1252')
        require(inventory['animations'][current]['animationScale']==1,'Non-unit source animation scale requires separate policy')
        current=parents[current]
    for extra in extra_supermodels:
        current=extra.lower();visited=set()
        while current!='null':
            require(current not in visited,'Equipment supermodel inheritance cycle')
            visited.add(current)
            if current in chain:
                break
            require(current in inventory['animations'],'Missing declared equipment supermodel: '+current)
            chain.append(current);parents[current]=inventory['animations'][current]['supermodel']
            texts[current]=(baseline/'ascii'/(current+'.mdl')).read_text(encoding='cp1252')
            require(inventory['animations'][current]['animationScale']==1,
                    'Non-unit equipment animation scale requires separate policy')
            current=parents[current]
    chain_nodes={n:nodes(t) for n,t in texts.items()}
    aliases={n:('pmg0' if i==0 else 'sr_tmg0_'+str(i).zfill(2)) for i,n in enumerate(chain)}
    output.mkdir(parents=True)
    snapshots=output/'source-inputs'; snapshots.mkdir()
    snapshot_inputs=[baseline/'baseline.json',baseline/'race-measurements.json']
    for directory in ('ascii','raw'):
        snapshot_inputs.extend(path for path in (baseline/directory).glob('*')
                               if path.stem in chain or path.stem.startswith(('pmh0_','pmo0_'))
                               or path.stem=='pmo0' or path.name in
                               ('appearance.2da','phenotype.2da','racialtypes.2da'))
    frozen={}; original_inputs={}
    for path in sorted(set(snapshot_inputs)):
        relative=path.relative_to(baseline)
        destination=snapshots/relative; destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,destination)
        frozen[str(destination.resolve())]=sha(destination)
        original_inputs[str(path.resolve())]={'snapshot':str(destination.resolve()),'sha256':sha(path)}
    helper_pins={}
    for filename in ('build_target_rig.py','rig_controller_audit.py','retarget.py','target_contract.py'):
        original=Path(__file__).with_name(filename)
        destination=snapshots/'tools'/filename;destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(original,destination)
        frozen[str(destination.resolve())]=sha(destination)
        helper_pins[filename]=sha(destination)
    receipts=[]
    for space,factor in [('working',1.),('runtime',scale)]:
        directory=output/space/'ascii';directory.mkdir(parents=True)
        for name in chain:
            text,audit=export_model(texts[name],name,aliases[name],aliases.get(parents[name],'NULL'),
                                    factor,deltas,chain_nodes,parents,source,target_nodes=working)
            dest=directory/(aliases[name]+'.mdl');dest.write_text(text,encoding='ascii')
            receipts.append({'space':space,'source':name,'model':aliases[name], 'sha256':sha(dest),
                             'clipCount':len(signature(text)),'positionalControllers':audit})
    working_world=transforms(working)
    runtime=copy.deepcopy(working)
    for row in runtime.values():row['position']*=scale
    runtime_world=transforms(runtime)
    contract={'schemaVersion':2,'kind':'phenotype-target','id':'troll-male-muscular-purposebuilt-v1',
              'identity':{'race':'troll','gender':'male','phenotype':0,'bodyType':'muscular','prefix':'pmg0','raceId':2,'appearanceRow':2},
              'heightMeters':height*scale,'workingHeightMeters':height,
              'models':{part:'pmg0_'+part+'001' for part in PART_JOINTS},
              'rig':{'revision':'broadened-'+output.name+'-bind-audit-pilot','sourcePrefix':'pmh0','runtimeScale':scale,'positionPolicy':'bind-relative',
                     'preserveRotations':True,'preserveTimingEvents':True,'sourceBindLocal':{n:r['position'].tolist() for n,r in source.items()},
                     'targetWorkingBindLocal':{n:r['position'].tolist() for n,r in working.items()},
                     'frames':{'working':{n:m.tolist() for n,m in working_world.items()},'runtime':{n:m.tolist() for n,m in runtime_world.items()}},
                     'changedLocalPositions':deltas,'privateAliases':aliases,'pilotAccepted':False},
              'measurements':{'halfOrcHeight':measurements['pmo0']['height'],'halfOrcToWorking':orc_factor,
                              'workingShoulderSpan':shoulder,'workingHipSpan':hip,'runtimeShoulderSpan':shoulder*scale,'runtimeHipSpan':hip*scale},
              'equipment':{'sourcePrefix':'pmh0','excludedBareStyle':1,'mode':'measured-regional','profilesAccepted':False,
                           'extraSupermodels':list(extra_supermodels),
                           'supermodelMappings':aliases},
              'material':{'normalStrength':1,'skinTexture0':False,'roughnessOverride':0,'fixedGarmentPart':'pelvis'},
              'productionAccepted':False,'clientAccepted':False,'frozenInputs':frozen}
    validate(contract)
    path=output/'target-contract.json';path.write_text(json.dumps(contract,indent=2)+'\n')
    audit={'schemaVersion':2,'kind':'target-rig-export','targetContractSha256':sha(path),'models':receipts,
           'sourceInputs':frozen,'originalInputs':original_inputs,
           'exportHelpers':helper_pins,
           'python':{'executable':sys.executable,'sha256':sha(Path(sys.executable)),
                     'version':sys.version,'numpyVersion':np.__version__},
           'geometryScaleAppliedOnce':True,'sourceRotationsTimingEventsUnchanged':True,
           'coreSupermodelBindPolicy':'Use the widened Human phenotype bind and hierarchy; preserve animation controller rotations and ownership',
           'generationPoseInputs':False,'positionBezierSemantics':None,
           'positionBezierPolicy':'Reject until encoded semantics are reviewed; no positional Bezier controllers in this stock chain',
           'clientAccepted':False}
    (output/'rig-export.json').write_text(json.dumps(audit,indent=2)+'\n')
    return contract,audit

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--extra-supermodel',action='append',default=[])
    a=p.parse_args();contract,audit=build(a.baseline.resolve(),a.output.resolve(),a.extra_supermodel)
    print(json.dumps({'target':contract['id'],'measurements':contract['measurements'],
                      'models':len(audit['models']),'controllers':sum(len(x['positionalControllers']) for x in audit['models'])}))
