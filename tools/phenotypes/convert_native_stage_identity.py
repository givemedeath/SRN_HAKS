"""Exactly-once stock-exact working-to-runtime identity for verified native stages."""
import argparse,json,shutil
from pathlib import Path
import numpy as np
import target_contract as c

def convert(stage_pin,target_pin,output):
 for row in (stage_pin,target_pin):c.require(set(row)=={'path','sha256'}and c.sha(row['path'])==row['sha256'],'Changed identity input')
 source=Path(stage_pin['path']);stage=json.loads(source.read_text());tp=Path(target_pin['path']);target=c.load(tp)
 c.require(stage['kind']=='target-part-stage'and stage['coordinateSpace']=='working'and type(stage['statureApplications'])is int and stage['statureApplications']==0,'Repeated identity conversion rejected')
 c.verify_binding(stage,tp,target,'working');c.require(c.rig_mode(target)=='stock-exact'and target['rig']['runtimeScale']==1,'Identity requires stock-exact unit scale')
 c.require('nativeCompilerInputProof'in stage and stage['nativeCompilerInputProof']['authority']=='literalNativeArchive'and not stage['nativeCompilerInputProof']['identityConversionApplied'],'Verified unconverted native-f64 stage required')
 part=stage['part'];joint=c.PART_JOINTS[part];c.require(np.array_equal(c.frame(target,joint,'working'),c.frame(target,joint,'runtime')),'Working/runtime frames must be exactly equal')
 for p,h in stage['frozenInputs'].items():c.require(c.sha(p)==h,'Changed source stage dependency: '+p)
 c.require(c.sha(stage['asciiModel'])==stage['asciiModelSha256'],'Changed ASCII geometry')
 for name,h in stage['materialResourceHashes'].items():c.require(c.sha(source.parent/'resources'/name)==h,'Changed material dependency')
 out=Path(output).resolve();c.require(not out.exists(),'Fresh identity result required');out.mkdir(parents=True)
 for name in ('ascii','resources'):shutil.copytree(source.parent/name,out/name)
 for name in ('authoritative-native-compiler-corners.npz','compiler-material-face-ownership.npz'):
  if (source.parent/name).exists():shutil.copyfile(source.parent/name,out/name)
 stage.update(c.binding(tp,target,'runtime'));stage['statureApplications']=1;stage['sourceWorkingStage']=stage_pin;stage['asciiModel']=str(out/'ascii'/Path(stage['asciiModel']).name);stage['nativeCompilerInputProof']['identityConversionApplied']=True
 stage['identityRuntimeConversion']={'operation':'stock-exact-working-to-runtime-identity-once','matrix':np.eye(4).tolist(),'inputApplications':0,'outputApplications':1,'positionsNormalsUVTangentsChanged':False,'exactEqualWorkingRuntimeFrames':True,'authoredNativeArchiveHeld':True}
 stage['frozenInputs'].update({str(source.resolve()):c.sha(source),str(Path(__file__).resolve()):c.sha(__file__)})
 result=out/'target-stage.json';result.write_text(json.dumps(stage,indent=2));return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--stage',required=True);p.add_argument('--stage-sha',required=True);p.add_argument('--target',required=True);p.add_argument('--target-sha',required=True);p.add_argument('--output',required=True);a=p.parse_args();print(convert({'path':a.stage,'sha256':a.stage_sha},{'path':a.target,'sha256':a.target_sha},a.output))
