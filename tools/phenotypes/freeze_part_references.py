"""Copy a reviewed normalized reference bundle byte-exact to the user's bank."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--normalized', type=Path, required=True)
    parser.add_argument('--design', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--audit', type=Path, required=True)
    parser.add_argument('--request', type=Path,
                        help='Optional root-reviewed request with explicit ancestry inputs and SHA256 pins.')
    parser.add_argument('--lineage-root', type=Path,
                        help='Owned pilot root for request ancestors; required with --request.')
    args=parser.parse_args()
    normalized=args.normalized.resolve(); design=args.design.resolve()
    provenance=json.loads((normalized/'provenance.json').read_text())
    expected={name+'.png' for name in provenance['views']}
    if len(expected) not in (4,6) or args.destination.exists() or args.audit.exists():
        raise RuntimeError('Reviewed four/six views and fresh destination/audit required')
    for name,row in provenance['views'].items():
        if sha(normalized/(name+'.png')) != row['sha256']:
            raise RuntimeError('Normalized view changed: '+name)
    if sha(design/'source.png') != provenance['sourceSha256']:
        raise RuntimeError('Design source differs from normalization')
    files={Path('normalized')/p.name:p for p in normalized.iterdir() if p.is_file()}
    files.update({Path('design')/p.name:p for p in design.iterdir() if p.is_file()})
    files[Path('generation-config.json')]=args.config.resolve()
    files[Path('executed-reference-freezer.py')]=Path(__file__).resolve()
    if bool(args.request) != bool(args.lineage_root):
        raise RuntimeError('Request and lineage-root must be supplied together')
    if args.request:
        request=json.loads(args.request.read_text()); lineage_root=args.lineage_root.resolve()
        if Path(request['references']).resolve()!=normalized or Path(request['config']).resolve()!=args.config.resolve():
            raise RuntimeError('Reviewed request is not the selected reference/config bundle')
        for source_name, expected_pin in request['inputs'].items():
            source=Path(source_name).resolve()
            if not source.is_relative_to(lineage_root) or sha(source)!=expected_pin:
                raise RuntimeError('Stale or out-of-pilot lineage input: '+source_name)
            files[Path('lineage')/source.relative_to(lineage_root)]=source
        files[Path('lineage')/args.request.name]=args.request.resolve()
    pins={relative:sha(path) for relative,path in files.items()}
    args.destination.mkdir(parents=True)
    rows=[]
    for relative,source in files.items():
        target=args.destination/relative; target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,target)
        if sha(source)!=pins[relative] or sha(target)!=pins[relative]:
            raise RuntimeError('Reference changed during copy: '+str(relative))
        rows.append({'source':str(source),'destination':str(target.resolve()),'sha256':pins[relative]})
    args.audit.parent.mkdir(parents=True,exist_ok=True)
    args.audit.write_text(json.dumps({'pass':True,'files':rows,'pixelEdits':False,
        'sharedScale':provenance['scale'],'sourceSha256':provenance['sourceSha256']},indent=2)+'\n')
    print(json.dumps({'pass':True,'files':len(rows),'destination':str(args.destination.resolve())}))


if __name__=='__main__': main()
