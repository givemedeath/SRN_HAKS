import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3]/'tools/phenotypes'))
from stage_stock_part import sha, save

root=Path(__file__).resolve().parent
collection=root/'arm-calibrated-materials-v1'
calibration=json.loads((collection/'skin-calibration.json').read_text())
audit=root/'arm-material-audit-v1/audit.json'
inspection=json.loads(audit.read_text())
manifest=collection/'body-resource-manifest.json'
inventory=json.loads(manifest.read_text())
palette=root/'stock-equipment-items-v1/raw/pal_skin01.tga'
inputs=dict(calibration['frozenInputs']);inputs.update(inspection['frozenInputs'])
for p in (collection/'skin-calibration.json',audit,manifest,palette,Path(__file__).resolve()):inputs[str(p)]=sha(p)
settings={}
for part,record in inspection['parts'].items():
    for row in record['images'].values():inputs[row['path']]=row['sha256']
    samples=audit.parent/part/'native-uv-samples.npz'; inputs[str(samples)]=sha(samples)
    elbow_or_wrist=.301921 if part.startswith('bicep') else .291763
    settings[part]={'aoStrength':.35,'connectorBandMetres':.020,
        'connectorPlanes':[{'outwardNormal':[0,0,1],'offsetMetres':0},
                           {'outwardNormal':[0,0,-1],'offsetMetres':elbow_or_wrist}],
        'maxDarkenShades':12,'maxBrightenShades':3}
save(root/'arm-material-bake-config-v1.json', {'schemaVersion':1,'kind':'human-male-material-trial',
    'useAO':True,'useRoughness':True,'inputHashes':inputs,'audit':str(audit),
    'baselineResources':str(collection/'body-resources'),'baselineResourceHashes':inventory['resources'],
    'palette':str(palette),'partSettings':settings})
print('Pinned fresh arm-only AO/roughness operation with actual joint planes.')
