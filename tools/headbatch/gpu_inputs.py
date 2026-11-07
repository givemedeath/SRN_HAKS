"""Verify the runner's current prepared dependency closure before GPU consumption."""
import sys
from pathlib import Path
from headkit.comfy import MULTIVIEW_VIEWS
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
    data=read(receipt['path'])
    multi = runner.data.get('profile') == 'pixal-multiview-v1'
    paired = multi or {'clay','detail'}<=set(runner.data['inputs'])
    if paired and (head/'design'/'design-receipt.json').is_file():
        front = result['views']['front'] if multi else result
        if set(front.get('eyeReview', {})) != {'left', 'right'}:
            raise ValueError('Paired front conditioning needs an eye review of both exact input images before GPU')
    if multi:
        if result['rigFovDegrees'] != 20 or result['independentCropping'] is not False:
            raise ValueError('Multiview needs the reviewed shared 20-degree prepare rig')
        images = {role+view: result['views'][view.lower()]['images'][role+'-pair.png']
                  for view in MULTIVIEW_VIEWS for role in ('geometry','detail')}
    else:
        roles={'geometry':'geometry-pair.png','detail':'detail-pair.png','mask':'common-mask.png'} if paired else {
            'geometry':'design-rgba.png','detail':'design-rgba.png','mask':'design-rgba.png'}
        images={role:result['images'][name] for role,name in roles.items()}
    pins=[pin(__file__),pin(head/'manifest.json'),pin(head/'bindings.json'),pin(runner.state_path),receipt,review,
          *data['inputs'],*data['outputs'],*stage_file_pins('prepare')]
    verify(pins,fresh=True)
    value={'attempt':Path(receipt['path']).parent.name,'receipt':receipt,'review':review,'pins':pins,
           'images':images,'paired':paired,'profile':runner.data.get('profile','pixal-single-v1')}
    write(output,value,fresh=True)
    return value

if __name__=='__main__':freeze(sys.argv[1],sys.argv[2])
