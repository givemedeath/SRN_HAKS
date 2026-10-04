"""CPU-only Blender evaluation of stock equipment dummies versus hand frames."""
from pathlib import Path
import hashlib,json,re,sys
import numpy as np
P=Path(__file__).resolve().parent;R=P.parents[2]
sys.path.insert(0,str(R/'tools/phenotypes'))
from pose_preview import pose
from retarget import nodes,transforms
STOCK=R/'output/phenotypes/purposebuilt-stock-inputs-v1/stock/ascii'
OUT=P/'wrist-motion-dense-v2';OUT.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
bind=transforms(nodes((STOCK/'pmh0.mdl').read_text()));cases=[]
clips=['pause1','pause2','walk','run','walk_swordr','walk_swordl','walk_shieldl','run_shieldl','1hreadyr','1hreadyl','1hslashr','1hslashl','1hstab','1hparryr','1hparryl','2wreadyr','2wreadyl','2wslashr','2wslashl','xbowr','conjure2','castout','getlowlp','kneel','deadfnt','nwreadyr','nwreadyl']
for clip in clips:
    try:_,base=pose(STOCK,'pmh0',clip,0)
    except RuntimeError as error:
        cases.append({'clip':clip,'unavailable':str(error)});continue
    for fraction in tuple(np.linspace(0.,1.,9)):
        t=fraction*base['length'];world,receipt=pose(STOCK,'pmh0',clip,t);hands=[]
        for s in ('l','r'):
            joint=s+'hand_g';equip=s+'hand';fore=s+'forearm_g'
            relative=np.linalg.inv(world[joint])@world[equip]
            expected=np.linalg.inv(bind[joint])@bind[equip]
            angle=float(np.degrees(np.arccos(np.clip((np.trace(relative[:3,:3]@expected[:3,:3].T)-1)/2,-1,1))))
            wr=np.linalg.inv(world[fore])@world[joint];wb=np.linalg.inv(bind[fore])@bind[joint]
            wristangle=float(np.degrees(np.arccos(np.clip((np.trace(wr[:3,:3]@wb[:3,:3].T)-1)/2,-1,1))))
            hands.append({'side':s,'forearmJointWorld':world[fore].tolist(),'forearmToHandLocal':(np.linalg.inv(world[joint])@world[fore]).tolist(),'handJointWorld':world[joint].tolist(),'equipmentWorld':world[equip].tolist(),'equipmentInHandFrame':relative.tolist(),'equipmentTranslationDifferenceFromBindMm':((relative[:3,3]-expected[:3,3])*1000).tolist(),'equipmentRotationDifferenceFromBindDegrees':angle,'wristFromBindDegrees':wristangle})
        cases.append({'clip':clip,'fraction':fraction,'controllerReceipt':receipt,'hands':hands})
summary={'schemaVersion':1,'readOnly':True,'geometryChanged':False,'clientTested':False,'inputs':{str(p):sha(p) for p in [STOCK/'pmh0.mdl',*[STOCK/x for x in ['a_ba.mdl','a_ba_non_combat.mdl','a_ba_med_weap.mdl','a_ba_custom.mdl','a_ba_casts.mdl']],R/'tools/phenotypes/pose_preview.py',R/'tools/phenotypes/retarget.py']},'cases':cases,'scope':'Finite exact stock ASCII-controller pose samples and actual held child transforms. No equipment geometry or live engine behavior inferred.'}
hands=[h for c in cases for h in c.get('hands',[])]
summary['maximumEquipmentRotationFromBindDegrees']=max(h['equipmentRotationDifferenceFromBindDegrees'] for h in hands)
summary['maximumEquipmentTranslationFromBindMm']=max(float(np.linalg.norm(h['equipmentTranslationDifferenceFromBindMm'])) for h in hands)
summary['maximumWristRotationFromBindDegrees']=max(h['wristFromBindDegrees'] for h in hands)
(OUT/'measurement.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({k:summary[k] for k in ['maximumEquipmentRotationFromBindDegrees','maximumEquipmentTranslationFromBindMm','maximumWristRotationFromBindDegrees']}))

