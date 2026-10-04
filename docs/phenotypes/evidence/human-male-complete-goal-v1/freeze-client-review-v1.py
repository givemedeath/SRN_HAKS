"""Freeze root-observed client evidence; captures and selected native bytes stay immutable."""
from pathlib import Path
import datetime,hashlib,json

ROOT=Path(__file__).resolve().parent
FIX=ROOT/'client-fourteen-skin3-motion-v2'
OUT=ROOT/'client-reviewed-evidence-v1'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def save(p,v):Path(p).write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8')

assert not OUT.exists(), 'Fresh evidence output required'
OUT.mkdir()
native=ROOT/'native-fourteen-v1/human_male_fit/converted'
body=ROOT/'native-fourteen-v1/human_male_body.hak'
assert sha(body)=='01524cd39ad111021d30ba9a7c2241fdf8ef3afc7eb77f04346907d423d9f7c2'
pins={str(native/'effective-material-inventory.json'):sha(native/'effective-material-inventory.json'),str(body):sha(body)}
runs=[]
for pid in (40868,26740,48948):
    launch=FIX/f'client-launch-{pid}.json';archive=FIX/f'client-evidence-run-{pid}'
    receipt=archive/'receipt.json';settings=archive/'settings.tml'
    lr=read(launch);fr=read(receipt);metrics=FIX/f'runtime-metrics-{pid}.json'
    assert sha(receipt)==lr['fixtureReceiptSha256']
    assert fr['hakSha256']==lr['hakSha256']=='1af9fe160af8be024c3ffe761a2c7dd746a89eee3c1d7ad5117cd09e5b8ac245'
    assert fr['moduleSha256']==lr['moduleSha256']
    source_logs=list((archive/'logs').glob('*.txt'))
    filtered=[]
    for log in source_logs:
        filtered.extend(line for line in log.read_text(errors='replace').splitlines() if 'PHENOTYPE_' in line)
    (OUT/f'run-{pid}-phenotype.log').write_text('\n'.join(filtered)+'\n',encoding='utf-8')
    record={'processId':pid,'launch':str(launch),'launchSha256':sha(launch),
            'fixtureReceipt':str(receipt),'fixtureReceiptSha256':sha(receipt),
            'testHakSha256':fr['hakSha256'],'moduleSha256':fr['moduleSha256'],
            'configuration':fr['configuration'],'settings':str(settings),'settingsSha256':sha(settings),
            'runtimeMetrics':read(metrics),'runtimeMetricsSha256':sha(metrics),
            'sourceLogs':{str(p):sha(p) for p in source_logs},
            'filteredPhenotypeLog':str(OUT/f'run-{pid}-phenotype.log'),
            'filteredPhenotypeLogSha256':sha(OUT/f'run-{pid}-phenotype.log')}
    runs.append(record)

specs=[
 ('idle',40868,'008-continuous-gameplay-2','Idle','Post-gameplay idle; skin3; original lighting',[350,180,680,635]),
 ('walk',26740,'008-walk-return-0','Walk','Actual outward walk; skin8; directional lighting',[450,280,596,618]),
 ('run',26740,'011-walk-return-3','Run','Actual return run; skin8; directional lighting',[460,295,600,625]),
 ('cast',40868,'003-corpse-fullbody','Cast','Actual Magic Missile; skin3; original lighting',[350,180,680,630]),
 ('combat',40868,'005-wide-floor-contact','Combat','Actual equipped combat; skin3; original lighting',[360,170,710,635]),
 ('crouch',26740,'031-live-low-poses-0','Crouch','GET_LOW; skin8; inherited deep-hip overlap',[460,440,650,620]),
 ('kneel',48948,'002-kneel-hold-side-0','Kneel','Held WORSHIP; skin3; side view; original lighting',[470,320,630,601]),
 ('death',40868,'018-final-gameplay-stability','Death','Actual gameplay corpse; skin3; original lighting',[420,460,670,636]),
]
cases=[]
for category,pid,stem,label,caption,crop in specs:
    capture=ROOT/f'client-evidence-v1/run-{pid}/{stem}.json';cr=read(capture)
    image=Path(cr['images'][0]['path'])
    assert sha(image)==cr['images'][0]['sha256'] and cr['processId']==pid
    run=next(r for r in runs if r['processId']==pid)
    observation=OUT/f'{category}-observation.json'
    save(observation,{'category':category,'observedDescription':caption,'processId':pid,
                     'capture':str(capture),'captureSha256':sha(capture),
                     'sourceImage':str(image),'sourceImageSha256':sha(image),
                     'captureStarted':cr['captureStarted'],'captureEnded':cr['captureEnded'],
                     'fixtureReceipt':run['fixtureReceipt'],'fixtureReceiptSha256':run['fixtureReceiptSha256'],
                     'moduleSha256':run['moduleSha256'],'testHakSha256':run['testHakSha256'],
                     'bodyHakSha256':sha(body),'fullBodyReviewed':True,
                     'presentationCrop':crop,'pixelAdjustment':'None: literal crop only; full original retained',
                     'timingScope':'Observed frame and timestamp, not a measured animation clip position.'})
    cases.append({'category':category,'label':label,'caption':caption,'image':str(image),'imageSha256':sha(image),
                  'receipt':str(observation),'receiptSha256':sha(observation),'fullBodyReviewed':True,'captureCrop':crop})
config=ROOT/'client-reference-config-v1.json'
save(config,{'title':'Muscular Human male — NWN:EE animation reference','evidenceKind':'nwn-ee-client',
             'effectiveBodyConverted':str(native),'packagePins':pins,'cases':cases})
validation={'schemaVersion':1,'created':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'scope':'Practical complete Human male validation pass; hands cosmetic work closed by user.',
            'packagePins':pins,'completeBodySelected':True,'nativeModels':14,'bodyResources':72,
            'clientObserved':True,'clientPassCompleted':True,'runs':runs,
            'observed':{
              'materials':'Skin3/original and skin8/directional: anatomical definition visible, adjoining skin broadly coherent, fixed dark pelvis cloth preserved. Hover highlights excluded from assessment.',
              'motion':'Actual walk/run start, outward route, return and idle; casting, equipped melee, damage, death and resurrection; GET_LOW entry/hold/recovery and held WORSHIP kneeling cycle inspected.',
              'joints':'No newly detached parts or empty openings observed in inspected frames. Rounded overlaps/wrist cap remain visible in some extremes.',
              'floor':'Feet and corpse inspected; walk/run plants appear practical. No collision or continuous floor-height instrumentation was used.',
              'equipment':'Rigid armor, sleeves/boots coverage and actual sword/shield behavior inspected at stock identity scaling. Full armor hides many custom surfaces; it is fallback/coverage evidence.',
              'views':'Front/rear route, equipped front/rear, side kneeling, close/gameplay views; offline front/rear/side/top comparisons supplement engine captures.',
              'camera':'Distance wheel changed visible framing. Camera locking disabled in all receipts. Keyboard camera-pan injection did not independently establish a reliable turning control; side view uses explicit fixture facing.',
              'stability':'Three completed root-owned runs with no crash reports produced; skin3 gameplay >17min, skin8 motion >7min, held-kneel inspection several minutes. Process responding at each metric sample.',
              'performance':'Steady screenshot overlay typically61FPS under adaptive-vsync, 3 specimen actors plus PC (7 actors during gameplay targets). Small isolated test, not a crowd/frametime benchmark.'},
            'acceptedLimitations':[
              'Inherited deep-crouch pelvis/thigh overlap and rounded cap prominence; user explicitly tolerates crouching weirdness.',
              'Practical hand source retains eight submillimetre crossing pairs and one pinched vertex link; no extra cosmetic loop required.',
              'Forearm cap can show through the wrist crown and extreme stock held-dummy shaft can enter palm, also present on stock mitten.',
              'Not all armor/robes/glove/helmet combinations, skin palettes, quality levels or production scenes were exhaustively client-tested.',
              'No GPU residency/frame-time capture or crowded scene benchmark. Serialized costs/texture estimates are separate from actual process memory.',
              'Nonfatal Empty field label in MODULE.ifo log warnings remain in archived engine logs; no reported missing-body-resource error or crash in these runs.'],
            'clientReferenceConfig':str(config),'clientReferenceConfigSha256':sha(config),
            'offlineValidation':str(ROOT/'offline-validation-v1.json'),
            'offlineValidationSha256':sha(ROOT/'offline-validation-v1.json'),
            'frozenReviewCodeSha256':sha(__file__),'purgePerformed':False,
            'acceptance':'Ready for user review, with disclosed practical limits; no claim of exhaustive production certification.'}
save(ROOT/'client-validation-v1.json',validation)
print(json.dumps({'clientValidation':str(ROOT/'client-validation-v1.json'),'referenceConfig':str(config),'cases':len(cases)}))
