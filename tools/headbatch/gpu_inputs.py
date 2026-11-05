"""Verify the runner's current prepared dependency closure before GPU consumption."""
import sys
from pathlib import Path
from headkit.runner import Runner
from headkit.common import pin, read, verify, write, stage_file_pins

def freeze(head, output):
    from headkit.comfy import locked
    with locked(Path(head)/'run'/'runner'):
        return _freeze(head,output)

def _freeze(head, output):
    head=Path(head)
    runner=Runner(head/'manifest.json',head/'bindings.json',head/'run')
    result=runner.result('prepare')
    receipt=runner.state['stages']['prepare'];review=runner.state['reviews']['prepare']
    data=read(receipt['path']);images=result['images']
    paired={'clay','detail'}<=set(runner.data['inputs'])
    roles={'geometry':'geometry-pair.png','detail':'detail-pair.png','mask':'common-mask.png'} if paired else {
        'geometry':'design-rgba.png','detail':'design-rgba.png','mask':'design-rgba.png'}
    pins=[pin(__file__),pin(head/'manifest.json'),pin(head/'bindings.json'),pin(runner.state_path),receipt,review,
          *data['inputs'],*data['outputs'],*stage_file_pins('prepare')]
    verify(pins,fresh=True)
    value={'attempt':Path(receipt['path']).parent.name,'receipt':receipt,'review':review,'pins':pins,
           'images':{role:images[name] for role,name in roles.items()},'paired':paired}
    write(output,value,fresh=True)
    return value

if __name__=='__main__':freeze(sys.argv[1],sys.argv[2])
