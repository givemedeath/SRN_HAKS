"""CPU only: pin complete14 effective previews and prepare unexecuted pose argv."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys

PILOT = Path(__file__).resolve().parent
ROOT = PILOT.parents[2]
TOOLS = ROOT/'tools/phenotypes'
PROTOCOL = PILOT/'animation-sheet-protocol-v1/protocol.json'
sys.path.insert(0, str(TOOLS))
from effective_body_contract import validate_effective_body

BODY = {'chest','pelvis','bicepl','bicepr','forel','forer','handl','handr',
        'legl','legr','shinl','shinr','footl','footr'}
ALL = BODY|{'head','neck'}
WORST_SUPPLEMENTS = ['idle-pause2-0p5', 'combat-1hslashr-0p5',
                    'combat-nwslashl-0p875', 'crouch-getlow-0p5',
                    'kneel-worship-3p5', 'death-kdfntdie-0p466667']


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8')


def validated_preview(path, expected_sha, skin_row):
    path=Path(path).resolve()
    require(sha(path)==expected_sha, 'Effective preview receipt changed')
    receipt=json.loads(path.read_text())
    require(receipt.get('pass') is True and receipt.get('readOnlySourceInputs') is True
            and receipt.get('sourceResourcesBytesUnchanged') is True,
            'Successful immutable-input effective preview required')
    converted=Path(receipt['sourceInventory']).resolve().parent
    _,_,inventory=validate_effective_body(converted)
    require(inventory['completeBodySelected'] is True and set(inventory['modelParts'].values())==BODY,
            'Final pose batch requires all fourteen actual selected native parts')
    require(receipt['effectiveNativeParts']==sorted(BODY)
            and receipt['effectiveResourceCount']==72
            and set(receipt['stockFallbackParts'])=={'head','neck'},
            'Final preview must contain fourteen native parts plus stock head/neck only')
    frozen={str(path):expected_sha}
    historical_code=[]
    for source,pin in receipt['inputHashes'].items():
        source=Path(source)
        if source.is_file() and sha(source)==pin:
            frozen[str(source.resolve())]=pin
        else:
            archive=path.parent/('executed-'+source.name)
            require(source.suffix=='.py' and archive.is_file() and sha(archive)==pin,
                    'Effective preview noncode source changed or executed helper missing: '+str(source))
            frozen[str(archive.resolve())]=pin
            historical_code.append({'original':str(source), 'executedArchive':str(archive), 'sha256':pin})
    variants={kind:next((row for row in receipt['variants']
                         if row['kind']==kind and row['skinRow']==skin_row), None)
              for kind in ['native','stock']}
    require(all(variants.values()), 'Both native and stock selected palette variants required')
    require(variants['native']['layerSelectors']==variants['stock']['layerSelectors'],
            'Custom and stock palette selectors differ')
    configs={}
    config_pins={Path(row['path']).resolve():row['sha256'] for row in receipt['previewConfigs']}
    for kind,variant in variants.items():
        require(set(variant['parts'])==ALL, 'Full body/head/neck effective preview missing')
        for part,row in variant['parts'].items():
            glb=Path(row['glb']).resolve()
            require(sha(glb)==row['glbSha256'], 'Effective part GLB changed: '+part)
            frozen[str(glb)]=row['glbSha256']
            corner=Path(row['sourceCornerArchive']).resolve()
            require(sha(corner)==row['sourceCornerArchiveSha256'], 'Source corner proof changed')
            frozen[str(corner)]=row['sourceCornerArchiveSha256']
            require(sha(row['sourceAscii'])==receipt['inputHashes'][row['sourceAscii']],
                    'Actual current ASCII source changed')
            expected_kind='effective selected native ASCII' if kind=='native' and part in BODY \
                          else 'actual stock comparator fallback'
            require(row['sourceKind']==expected_kind, 'Unexpected part provenance')
        config=Path(next(iter(variant['parts'].values()))['glb']).resolve().parent/'stock-replacement.json'
        require(config in config_pins and sha(config)==config_pins[config], 'Replacement config not byte-pinned')
        record=json.loads(config.read_text())
        require(record['modelPrefix']=='pmh0' and record['height']==1.9339157
                and record['shoulderStyle']==0 and set(record['parts'])==ALL,
                'Stock Human dimensions or bare shoulder ownership changed')
        require(all(Path(record['parts'][part]).resolve()==Path(row['glb']).resolve()
                    for part,row in variant['parts'].items()), 'Config/receipt part mappings differ')
        frozen[str(config)]=config_pins[config]
        configs[kind]=config
    return receipt,inventory,configs,frozen,historical_code


def build(preview, preview_sha, output, camera_scale, comparison_scale=None, skin_row=3):
    output=Path(output).resolve()
    require(output.is_relative_to(PILOT) and not output.exists(), 'Fresh owned pilot output required')
    comparison_scale=camera_scale if comparison_scale is None else comparison_scale
    require(all(math.isfinite(value) and value>0 for value in [camera_scale,comparison_scale]),
            'Positive finite explicit camera scales required')
    receipt,inventory,configs,frozen,historical_code=validated_preview(preview,preview_sha,skin_row)
    protocol=json.loads(PROTOCOL.read_text())
    primary=[row for row in protocol['sheetSnapshots'] if row['priority']=='primary-sheet']
    require(len(primary)==8 and {row['category'] for row in primary}==
            {'idle','walk','run','cast','combat','crouch','kneel','death'}, 'Eight animation categories required')
    supplements={row['id']:row for row in protocol['sheetSnapshots'] if row['priority']=='supplemental'}
    require(set(WORST_SUPPLEMENTS)<=set(supplements), 'Measured supplemental cases unavailable')
    diagnostic=primary+[supplements[key] for key in WORST_SUPPLEMENTS]
    baseline=ROOT/'output/phenotypes/purposebuilt-stock-inputs-v1/stock'
    helpers=[Path(__file__), TOOLS/'pose_preview.py', TOOLS/'audit_geometry.py', TOOLS/'retarget.py',
             TOOLS/'effective_body_contract.py', TOOLS/'stock_limb_contract.py', TOOLS/'stage_stock_part.py']
    frozen.update({str(path):sha(path) for path in [PROTOCOL,*helpers]})
    for chain in protocol['actualMaleChain']:
        require(sha(chain['file'])==chain['sha256'], 'Original male animation chain changed')
        frozen[chain['file']]=chain['sha256']
    for row in diagnostic:
        require(sha(row['controllerFile'])==row['controllerSha256'], 'Actual controller changed')
    output.mkdir(parents=True)
    snapshot=output/'pose-helper-snapshot';snapshot.mkdir()
    for helper in helpers:
        shutil.copy2(helper,snapshot/helper.name)
    snapshots={str(path):sha(path) for path in snapshot.iterdir()}
    shutil.copy2(PROTOCOL,output/'protocol-observed.json')
    base=['E:/Program Files/Blender Foundation/Blender 4.0/blender.exe','-b',
          '--python-exit-code','1','--python',str(snapshot/'pose_preview.py'),'--',
          '--baseline',str(baseline),'--stock-prefix','pmh0','--stock-height','1.9339157',
          '--no-stock','--include-heads','--shoulder-style','0','--focus','full-body',
          '--material-mode','color']
    batches=[]
    def plan(row,kind,views,scale,replacements):
        target=output/'renders'/kind/row['id']
        argv=[*base,'--clip',row['clip'],'--time',str(row['timeSeconds']),
              '--camera-scale',str(scale)]
        for config in replacements:
            argv+=['--stock-replacement',str(config)]
        for view in views:
            argv+=['--view',view]
        argv+=['--output',str(target)]
        expected_images=[str(target/(view+'.png')) for view in views]
        return {'id':row['id'], 'batch':kind, 'category':row['category'], 'clip':row['clip'],
                'timeSeconds':row['timeSeconds'], 'views':views, 'explicitCameraScale':scale,
                'specimenCount':len(replacements), 'argv':argv, 'expectedImages':expected_images,
                'expectedReceipt':str(target/'comparison.json'), 'executed':False,
                'fullBodyReviewed':False, 'controllerFile':row['controllerFile'],
                'controllerSha256':row['controllerSha256'],
                'controllerBlockSha256':next(r['controllerBlockSha256'] for r in protocol['clipCases']
                                            if r['clip']==row['clip']),
                'review':None}
    for row in primary:
        batches.append(plan(row,'primary-custom-only',['top'] if row['category']=='death' else ['front'],
                            camera_scale,[configs['native']]))
    for row in diagnostic:
        batches.append(plan(row,'comparison',['front','rear','left'],comparison_scale,
                            [configs['stock'],configs['native']]))
    save(output/'batch.json', {'schemaVersion':1, 'preparedOnly':True, 'rendersExecuted':False,
                              'clientControlled':False, 'sourceInputsModified':False,
                              'completeBodySelected':True,
                              'effectiveInventory':receipt['sourceInventory'],
                              'effectiveResourceCount':len(inventory['resourceHashes']),
                              'previewReceipt':str(Path(preview).resolve()),
                              'skinRow':skin_row, 'layerSelectors':next(row['layerSelectors'] for row in receipt['variants']
                                                                       if row['kind']=='native' and row['skinRow']==skin_row),
                              'frozenInputs':frozen, 'executedHelperSnapshots':snapshots,
                              'historicalPreviewHelperOrigins':historical_code,
                              'renderPlans':batches,
                              'primaryCount':8, 'comparisonCases':len(diagnostic),
                              'totalImageRequests':8+3*len(diagnostic),
                              'cameraPolicy':{'primarySharedScale':camera_scale,
                                              'comparisonSharedScale':comparison_scale,
                                              'renderAspectRatiosDifferBySpecimenCount':True,
                                              'numericActualCameraReceiptsRequired':True},
                              'offlineLimitation':'Static samples within stock clips; endpoints and stored transition '
                                                  'times do not execute actual cross-clip engine blending.',
                              'referenceSheetGate':'Root must inspect literal full-body images, bind image/receipt/package '
                                                   'hashes and set fullBodyReviewed only after actual review. '
                                                   'These plans contain no completed captures or test claims.',
                              'remainingClientGate':'Actual continuous playback, lighting, transitions, equipment, '
                                                    'stability and performance after complete offline readiness.'})
    for path,pin in frozen.items():
        require(sha(path)==pin, 'Immutable source changed during batch preparation')
    print(json.dumps({'batch':str(output/'batch.json'), 'sha256':sha(output/'batch.json'),
                      'primaryRenders':8, 'comparisonCases':len(diagnostic), 'rendersExecuted':False}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preview-receipt',type=Path,required=True)
    parser.add_argument('--preview-receipt-sha256',required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--camera-scale',type=float,required=True)
    parser.add_argument('--comparison-camera-scale',type=float)
    parser.add_argument('--skin-row',type=int,default=3)
    args=parser.parse_args()
    build(args.preview_receipt,args.preview_receipt_sha256,args.output,args.camera_scale,
          args.comparison_camera_scale,args.skin_row)
