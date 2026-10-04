import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3]/'tools/phenotypes'))
from stage_stock_part import sha, save
from prepare_effective_native_unit import prepare

root=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('--variant',type=int,choices=(1,2),default=1)
variant=parser.parse_args().variant
operation=root/('arm-effective-materials-v'+str(variant))/'material-operation.json'
material=json.loads(operation.read_text())
if variant==2:
    prior=json.loads((root/'arm-effective-materials-v1/material-operation.json').read_text())
    assert prior['effectiveResourceHashes']==material['effectiveResourceHashes'], 'Tool archival must not change material pixels'
manifest=operation.parent/'body-resource-manifest.json'
save(manifest, {'schemaVersion':1,'resources':material['effectiveResourceHashes'],
    'selectedGeometry':json.loads((root/'arm-calibrated-materials-v1/body-resource-manifest.json').read_text())['selectedGeometry'],
    'materialOperation':str(operation),'materialOperationSha256':sha(operation), 'nativeCompiled':False})
for part,stage in [('bicepl','upperarm-left-raw-stage-v1'),('bicepr','upperarm-right-raw-stage-v1'),
                   ('forel','forearm-left-raw-stage-v2'),('forer','forearm-right-raw-stage-v2')]:
    prepare(argparse.Namespace(stage=root/stage,runtime_resources=operation.parent/'resources',
         runtime_manifest=manifest,runtime_manifest_sha256=sha(manifest),
         material_operation=operation,material_operation_sha256=sha(operation),output=root/(part+'-native-v'+str(variant))))
save(root/('arm-native-preparation-index-v'+str(variant)+'.json'), {'parts':{
    part:{'path':str(root/(part+'-native-v'+str(variant))/'native-unit-preparation.json'),
          'sha256':sha(root/(part+'-native-v'+str(variant))/'native-unit-preparation.json')}
    for part in ('bicepl','bicepr','forel','forer')},'nativeCompilerExecuted':False,'clientLaunched':False})
