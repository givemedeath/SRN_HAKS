import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3]/'tools/phenotypes'))
from stage_stock_part import sha, save

goal=Path(__file__).resolve().parent
phenotypes=goal.parent
upper=phenotypes/'purposebuilt-upperarm-pilot-v1'
fore=phenotypes/'purposebuilt-forearm-pilot-v1'
u=upper/'current-material-cohorts-v1/measurement.json'
f=fore/'connector-material-cohorts-v1/measurement.json'
chest=upper/'accepted-chest-material-anchors-v1/measurement.json'
inputs={str(p):sha(p) for p in (u,f,chest)}
stages=[]
for part,stage,offset,calib,rationale in [
    ('bicepl','upperarm-left-raw-stage-v1',-10,u,'Current effective chest shoulder mean111.584 vs new upperarm121.078; integer-10 keeps front/rear residual within2.3 shades. Visible elbow becomes112.691.'),
    ('bicepr','upperarm-right-raw-stage-v1',-10,u,'Mirrored atlas is pixel-exact donor color; use same measured shoulder and elbow correction as left.'),
    ('forel','forearm-left-raw-stage-v2',11,f,'Actual0-20mm elbow source102.432..101.036 receives+11 to meet corrected upperarm112.691. Wrist becomes106.681..108.015 for later hand calibration.'),
    ('forer','forearm-right-raw-stage-v2',11,f,'Actual right connector cohort and mirrored atlas share donor palette; retain same+11 elbow/wrist correction.')]:
    path=goal/stage; receipt=path/'stock-part-stage.json'
    original=path/('human_male_fit/converted/resources/pmh0_'+part+'001.plt')
    stages.append({'part':part,'stage':str(path),'stageReceiptSha256':sha(receipt),
                   'originalPltSha256':sha(original),'shadeOffset':offset,
                   'calibrationReceipt':str(calib),'rationale':rationale})
save(goal/'arm-skin-calibration-config-v1.json', {'schemaVersion':1,
     'kind':'new-limb-skin-calibration','calibrationInputs':inputs,'stages':stages})
print('Pinned four new arm stages and actual adjoining-map measurements.')
