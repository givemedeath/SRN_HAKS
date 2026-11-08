"""Render the raw GPU shape, or a named precluster attempt with the same overview and bilateral temple views."""
import argparse
from pathlib import Path
import re
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gpu_contract
from headkit.common import pin, read, verify


def field_sheet(source, field_path, dll, destination, allow_overshoot, result):
    """Project the saved appearance directly at the mesh surface before UV work."""
    import numpy as np
    from PIL import Image
    from headkit.diagnostics import views, sheet
    from headkit.field import load_generated_field
    from headkit.gltf import mesh
    value = mesh(source)
    field = load_generated_field(field_path, allow_overshoot)
    from contextlib import ExitStack
    from headkit.scalp_appearance import ScalpDonor
    tiles = []
    names = ('front','left temple 50 degrees','left temple profile','right temple 50 degrees','right temple profile')
    with ExitStack() as stack:
        donor = None
        if 'scalpPatch' in result:
            donor = ScalpDonor(result,dll)
            stack.callback(donor.close)
        for name, view in views(value,dll,320,names):
            hit = view['hit']
            corners = value['positions'][value['faces'][view['face'][hit]]]
            positions = (corners*view['bary'][hit,:,None]).sum(axis=1)
            values, fallback = field.sample(positions)
            if donor is not None:
                donor.transfer(field,positions,values,fallback)
            pixels = np.full((len(hit),3),32,np.uint8)
            pixels[hit] = np.rint(values[:,:3]*255).astype(np.uint8)
            tiles.append((name,Image.fromarray(pixels.reshape(320,320,3))))
    return sheet(tiles,destination,320,columns=len(tiles))


def precluster_sheet(head, attempt, output, field_preview=False):
    from headkit.diagnostics import geometry_sheet
    if not re.fullmatch(r'attempt-[0-9]+', attempt):
        raise ValueError('Explicit precluster attempt required')
    folder = head.resolve()/'run'/'precluster'/attempt
    receipt_pin = pin(folder/'receipt.json')
    receipt = read(receipt_pin['path'])
    source = receipt['result']['output']
    if (receipt.get('state') != 'complete' or Path(source['path']).resolve() != folder/'oriented.glb'
            or source not in receipt['outputs']):
        raise ValueError('Expected the pinned oriented mesh from this complete precluster attempt')
    embree = read(head/'bindings.json')['embree']
    inputs = [receipt_pin, source, embree]
    if field_preview:
        manifest = pin(head/'manifest.json')
        data = read(manifest['path'])
        field = data['inputs']['field']
        field = dict(field, path=str(head/field['path']))
        inputs.extend([manifest, field])
    verify(inputs, fresh=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as scratch:
        preview = Path(scratch)/'sheet.png'
        if field_preview:
            field_sheet(source['path'],field['path'],embree['path'],preview,data['mesh'].get('allowDecoderOvershoot',False),receipt['result'])
        else:
            geometry_sheet(source['path'], embree['path'], preview)
        verify(inputs, fresh=True)
        preview.replace(output)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--rejected-geometry', metavar='SUBMISSION', help='diagnostic views for an open-occiput rejection')
    modes.add_argument('--camera', action='store_true', help='render the paired calibration sheet')
    parser.add_argument('head', type=Path)
    parser.add_argument('camera_attempt', nargs='?')
    modes.add_argument('--precluster', nargs=2, metavar=('ATTEMPT', 'OUT.png'))
    parser.add_argument('--field', action='store_true', help='preview the bound appearance field on the named precluster')
    args = parser.parse_args()
    if args.field and not args.precluster:
        parser.error('--field requires --precluster')
    if args.camera:
        if not args.camera_attempt or args.precluster:
            parser.error('--camera requires HEAD and its calibration attempt')
        print(gpu_contract.calibration_evidence(args.head, args.camera_attempt)['sheet']['path'])
    elif args.camera_attempt:
        parser.error('Unexpected calibration attempt without --camera')
    elif args.precluster:
        attempt, output = args.precluster
        print(precluster_sheet(args.head, attempt, Path(output), args.field))
    else:
        print(gpu_contract.make_geometry_evidence(args.head, read(args.head/'gpu'/'gpu.json'), args.rejected_geometry))


if __name__ == '__main__':
    main()
