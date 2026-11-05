"""gamesize.py HEAD ATTEMPT: immutable small palette/view sheet from that exact palette attempt."""
import sys
from pathlib import Path
from headkit.runner import Runner
from headkit.common import read, write, pin, verify, require
from headkit.diagnostics import palette_sheet

def run(head,attempt):
    head=Path(head);runner=Runner(head/'manifest.json',head/'bindings.json',head/'run')
    result=runner.result('palette',require_review=False)
    receipt=runner.state['stages']['palette']
    require(Path(receipt['path']).parent.name==attempt,'Game-size sheet must name the current exact palette attempt')
    source=runner.source('uvMesh','unwrap','mesh')
    palettes={k:runner.input(role) for k,role in runner.data['palette']['inputs'].items()}
    embree=runner.bindings['embree'];verify([embree],fresh=True)
    folder=head/'review-evidence'/('gamesize-'+attempt);number=1
    while folder.exists():
        number+=1;folder=head/'review-evidence'/f'gamesize-{attempt}-{number:02d}'
    result=palette_sheet(source,result['shades']['path'],result['ownership']['path'],palettes,result['rows'],embree['path'],folder)
    result.update(stageReceipt=receipt,attempt=attempt)
    verify([receipt],fresh=True);write(folder/'stage.json',result,fresh=True)
    print(result['sheet']['path'])
    return result

if __name__=='__main__':run(sys.argv[1],sys.argv[2])
