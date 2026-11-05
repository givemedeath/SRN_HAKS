"""Calibration/shape lineage and exact-submission visual gates. No implicit approvals."""
from pathlib import Path
from headkit.common import digest, pin, read, require, verify, write
from head_files import write_json

ORDER=('calibrate','geometry','appearance')

def stages(value):
    selected=value.split(',')
    require(selected and len(set(selected))==len(selected) and all(s in ORDER for s in selected)
            and selected==sorted(selected,key=ORDER.index),'GPU stages must be unique and in pipeline order')
    require(not ('calibrate' in selected and 'appearance' in selected and 'geometry' not in selected),
            'Recalibration requires new geometry before appearance')
    return selected

def calibration_id(row):
    require(isinstance(row.get('prepared'),dict) and isinstance(row.get('conditioning'),dict),'Legacy calibration has no verified conditioning lineage; recalibrate')
    return digest({'prepared':row['prepared'],'fov':row['fov'],'sharedFov':row['sharedFov'],
                   'conditioning':{k:v['sha256'] for k,v in row['conditioning'].items()}})

def validate_geometry(ledger):
    row=ledger['stages']['geometry']
    require(row.get('conditioningDigest')==calibration_id(ledger['stages']['calibrate']),
            'Saved geometry differs from current conditioning/camera; regenerate geometry')
    require(row.get('fov')==ledger['stages']['calibrate']['sharedFov'],'Saved geometry camera changed')
    verify(list(row['files'].values()),fresh=True)
    return row

def geometry_id(row):
    return digest({key:row[key] for key in ('files','fov','conditioningDigest','submission')})

def evidence_path(head,row):
    return Path(head)/'gpu'/'geometry-review'/f"geometry-{row['submission']:04d}"/'evidence.json'

def review_geometry(head,attempt,approval):
    require(isinstance(approval,str) and approval.strip(),'Pass the user review words as --approval')
    head=Path(head);ledger=read(head/'gpu'/'gpu.json');row=validate_geometry(ledger)
    expected=f"geometry-{row['submission']:04d}"
    require(attempt==expected,'Geometry approval must name the current exact submission')
    evidence=evidence_path(head,row);data=read(evidence)
    require(data['geometryDigest']==geometry_id(row),'Geometry review sheet is stale')
    verify(data['inputs']+[data['sheet']],fresh=True)
    folder=head/'gpu'/'reviews';folder.mkdir(exist_ok=True)
    target=folder/(attempt+'-approval.json')
    record={'attempts':{head.name:attempt},'geometryDigest':geometry_id(row),'evidence':pin(evidence),
            'decision':'approved','approval':approval,'productionAccepted':False}
    write(target,record,fresh=True)
    ledger['geometryReview']=pin(target);write_json(head/'gpu'/'gpu.json',ledger)
    return record

def require_geometry_review(head,ledger):
    row=validate_geometry(ledger);review=ledger.get('geometryReview')
    require(review is not None,'WAITING ON REVIEW: raw geometry sheet before appearance')
    verify([review],fresh=True);data=read(review['path']);attempt=f"geometry-{row['submission']:04d}"
    require(data.get('attempts')=={Path(head).name:attempt} and data.get('geometryDigest')==geometry_id(row)
            and data.get('decision')=='approved' and bool(data.get('approval','').strip()),
            'WAITING ON REVIEW: approval does not name current geometry')
    verify([data['evidence']],fresh=True);evidence=read(data['evidence']['path'])
    require(evidence.get('geometryDigest')==geometry_id(row),'Geometry sheet names another submission')
    verify(evidence['inputs']+[evidence['sheet']],fresh=True)
    return row

def make_geometry_evidence(head,ledger):
    from headkit.diagnostics import geometry_sheet
    head=Path(head);row=validate_geometry(ledger);target=evidence_path(head,row)
    require(not target.exists(),'Geometry evidence is immutable; use the saved sheet')
    source=next(v for k,v in row['files'].items() if k.startswith('961:'))
    bindings=read(head/'bindings.json');embree=bindings['embree'];verify([embree,source],fresh=True)
    target.parent.mkdir(parents=True,exist_ok=True)
    sheet=geometry_sheet(source['path'],embree['path'],target.parent/'sheet.png')
    data={'geometryDigest':geometry_id(row),'attempt':target.parent.name,'inputs':[source,embree],
          'sheet':sheet,'visualReviewRequired':True,'checks':['horn counts and curves','jaw and chin','neck absence','rear skull','stray shells']}
    verify(data['inputs'],fresh=True)
    require(geometry_id(validate_geometry(read(head/'gpu'/'gpu.json')))==data['geometryDigest'],
            'Geometry changed during evidence generation')
    write(target,data,fresh=True)
    return target
