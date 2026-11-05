"""Hash-bound capture coverage, separate from human appearance acceptance."""
from pathlib import Path
from head_workflow import read, pin, require
from verify_head_trial import last_session, FIELDS

REQUIRED_VIEWS={'three','threeleft','backright','backleft'}

def check_captures(manifest_path,log_path,record_path,log_report):
    manifest_path=Path(manifest_path);log_path=Path(log_path);record_path=Path(record_path)
    manifest=read(manifest_path);record=read(record_path)
    require(record.get('kind')=='head-client-captures-v1','Client capture record required')
    require(record.get('manifest')==pin(manifest_path) and record.get('log')==pin(log_path),'Capture record names another manifest/log')
    require(log_report['passed'],'Client slot/colour log must pass before capture coverage')
    for row in manifest['files']:
        path=(manifest_path.parent/row['relativePath']).resolve()
        require(path.is_relative_to(manifest_path.parent.resolve()),'Trial file escapes its folder')
        require(pin(path)['sha256']==row['sha256'],'Trial asset changed since build')
    _,lines=last_session(log_path.read_text(encoding='utf-8',errors='replace'))
    actors={row['tag']:row for row in manifest['actors']}
    spawned={row['tag'] for row in log_report['actors'] if row['status']=='spawned'}
    captures=record.get('captures');require(isinstance(captures,list) and captures,'Nonempty client captures required')
    hashes=set();seen={}
    for capture in captures:
        actor=actors.get(capture.get('actor'));require(actor is not None and actor['tag'] in spawned,'Capture actor was not verified in this log')
        frame=capture.get('frame',{});path=(record_path.parent/frame.get('path','')).resolve()
        require(path.is_file() and pin(path)['sha256']==frame.get('sha256'),'Missing or changed captured frame')
        from PIL import Image
        with Image.open(path) as image:
            require(image.width>=64 and image.height>=64,'Captured frame is too small')
            image.verify()
        require(frame['sha256'] not in hashes,'One frame cannot stand for several captures');hashes.add(frame['sha256'])
        index=capture.get('inspectionEvent')
        require(type(index) is int and 0<=index<len(lines),'Capture needs a valid zero-based inspectionEvent in the parsed last session')
        fields=dict(FIELDS.findall(lines[index]))
        require(lines[index].startswith('HEAD_INSPECT ') and fields.get('actor')==actor['tag'] and fields.get('view')==capture.get('view'),
                'Capture camera/actor differs from the logged inspection event')
        motion=capture.get('motionEvent')
        if motion is not None:
            require(type(motion) is int and 0<=motion<len(lines) and lines[motion].startswith('HEAD_MOTION ')
                    and dict(FIELDS.findall(lines[motion])).get('actor')==actor['tag'],'Motion frame needs the matching logged animation event')
        seen.setdefault(actor['headId'],[]).append((actor,capture))
    problems=[]
    for head in manifest['heads']:
        rows=seen.get(head['id'],[]);primary=[c for a,c in rows if a.get('column',0)==0]
        missing=REQUIRED_VIEWS-{c['view'] for c in primary}
        if missing:problems.append(head['id']+': missing primary-look views '+','.join(sorted(missing)))
        if not any(c.get('motionEvent') is not None for _,c in rows):problems.append(head['id']+': missing motion frame')
        looks={tuple(a[k] for k in ('skin','hair','tattoo1','tattoo2')) for a,_ in rows}
        if len(looks)<2:problems.append(head['id']+': missing second palette look')
    return {'kind':'head-client-capture-coverage','manifest':pin(manifest_path),'log':pin(log_path),'captures':pin(record_path),
            'passed':not problems,'problems':problems,'visualApprovalRequired':True,'productionAccepted':False,
            'limitation':'Hash and log coverage cannot establish visible anatomy, motion quality or appearance acceptance.'}
