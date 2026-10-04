"""Freeze selected body materials and measure native-UV shade/AO/roughness.

Read-only relative to selected inputs. Source/atlas statistics include hidden
surfaces; they are diagnostic, not a client appearance assessment.
"""
import argparse
from io import BytesIO
import json
from pathlib import Path
import re
import shutil
import struct

import numpy as np
from PIL import Image, ImageDraw

from scale_fitted_body import read_glb
from stage_stock_part import arrays, sha, require, save
from adjust_pelvis_skin_plt import taps, stats


def extract_image(doc, blob, texture):
    require(texture.get('texCoord', 0) == 0 and not texture.get('extensions'),
            'Material operation requires untransformed TEXCOORD_0')
    image = doc['images'][doc['textures'][texture['index']]['source']]
    require('bufferView' in image and not image.get('uri'), 'Embedded image required')
    view = doc['bufferViews'][image['bufferView']]
    start = view.get('byteOffset', 0)
    return blob[start:start + view['byteLength']]


def plt_image(data):
    require(data[:8] == b'PLT V1  ', 'PLT header required')
    layers, reserved, w, h = struct.unpack_from('<IIII', data, 8)
    require(layers == 10 and reserved == 0 and len(data) == 24+w*h*2, 'Invalid PLT')
    return np.frombuffer(data[24:], np.uint8).reshape(h, w, 2)[::-1].copy()


def ascii_skin_samples(text, model):
    nodes = re.findall(r'(?ms)^node trimesh (\S+)\n(.*?)^endnode', text)
    result = []
    for name, body in nodes:
        bitmap = re.search(r'(?m)^\s*bitmap\s+(\S+)', body)
        if not bitmap or bitmap[1] != model:
            continue
        p = np.asarray(arrays(body, 'verts'))
        uv = np.asarray(arrays(body, 'tverts'))[:, :2]
        f = np.asarray(arrays(body, 'faces'), int)
        result.append((p[f[:, :3]], uv[f[:, 4:7]]))
    require(result, 'No native skin-UV triangles found')
    return np.concatenate([r[0] for r in result]), np.concatenate([r[1] for r in result])


def sampled(image, uv):
    values, weights, _, _ = taps(image, uv)
    return np.sum(values*weights, axis=1)


def run(manifest_path, ascii_root, palette_path, output):
    require(not output.exists(), 'Fresh material inspection required')
    manifest = json.loads(manifest_path.read_text())
    body = manifest_path.parent/'body-resources'
    palette = np.asarray(Image.open(palette_path).convert('RGB'))
    inputs = {str(manifest_path.resolve()): sha(manifest_path),
              str(palette_path.resolve()): sha(palette_path)}
    require(palette.shape[1:] == (256, 3), 'Expected native 256-shade palette')
    for name, expected in manifest['resources'].items():
        require(sha(body/name) == expected, 'Body resource changed: '+name)
        inputs[str((body/name).resolve())] = expected
    output.mkdir(parents=True)
    rows = {}
    montage = Image.new('RGB', (1200, 8*235), '#222222')
    draw = ImageDraw.Draw(montage)
    for number, (part, selection) in enumerate(manifest['selectedGeometry'].items()):
        model = 'pmh0_'+part+'001'
        source = Path(selection['path'])
        require(sha(source) == selection['sha256'], 'Selected geometry changed: '+part)
        inputs[str(source)] = sha(source)
        doc, blob = read_glb(source)
        materials = [doc['materials'][p['material']] for mesh in doc['meshes'] for p in mesh['primitives']]
        directory = output/part
        directory.mkdir()
        first = materials[0]
        textures = {'color': first['pbrMetallicRoughness']['baseColorTexture'],
                    'normal': first['normalTexture'],
                    'ao': first['occlusionTexture'],
                    'orm': first['pbrMetallicRoughness']['metallicRoughnessTexture']}
        image_rows = {}
        images = {}
        for key, texture in textures.items():
            raw = extract_image(doc, blob, texture)
            for material in materials:
                other = {'color':material['pbrMetallicRoughness']['baseColorTexture'],
                         'normal':material['normalTexture'], 'ao':material['occlusionTexture'],
                         'orm':material['pbrMetallicRoughness']['metallicRoughnessTexture']}[key]
                require(extract_image(doc, blob, other) == raw,
                        'Per-primitive atlas differs; explicit separate ownership needed')
            path = directory/(key+'.png')
            path.write_bytes(raw)
            images[key] = np.asarray(Image.open(BytesIO(raw)).convert('RGB'))
            require(images[key].shape == (2048,2048,3), 'Expected selected 2K atlas')
            image_rows[key] = {'path':str(path.resolve()), 'sha256':sha(path),
                               'gltfTexture':texture, 'space':'sRGB' if key=='color' else 'linear-data'}
        require(first.get('normalTexture',{}).get('scale',1) == 1, 'Recorded normal strength required')
        text_path = ascii_root/(model+'.mdl')
        inputs[str(text_path.resolve())] = sha(text_path)
        p, uv = ascii_skin_samples(text_path.read_text(), model)
        area = np.linalg.norm(np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0]), axis=1)/2
        bary = np.array([[1/3]*3,[.6,.2,.2],[.2,.6,.2],[.2,.2,.6]])
        sample_uv = np.einsum('sc,tcd->tsd',bary,uv).reshape(-1,2)
        plt = plt_image((body/(model+'.plt')).read_bytes())
        shades = sampled(plt[:,:,0],sample_uv).reshape(-1,4)
        ao = sampled(images['ao'][:,:,0]/255.,sample_uv).reshape(-1,4)
        rough = sampled(images['orm'][:,:,1]/255.,sample_uv).reshape(-1,4)
        weights = np.repeat(area/4,4)
        def field_stats(field):
            a=field.reshape(-1); mean=float(np.average(a,weights=weights))
            return {'mean':mean,'std':float(np.sqrt(np.average((a-mean)**2,weights=weights))),
                    'range':[float(a.min()),float(a.max())]}
        np.savez_compressed(directory/'native-uv-samples.npz', position=p, uv=uv, area=area,
                            sampleUV=sample_uv, shade=shades, ao=ao, roughness=rough)
        rows[part] = {'model':model,'source':str(source),'sourceSha256':sha(source),
                     'images':image_rows,'material':first,'asciiSha256':sha(text_path),
                     'boundsMetres':[p.min((0,1)).tolist(),p.max((0,1)).tolist()],
                     'nativeUVShade':stats(shades,area,np.ones(len(p),bool),palette),
                     'nativeUVAO':field_stats(ao),'nativeUVRoughness':field_stats(rough),
                     'sampleSha256':sha(directory/'native-uv-samples.npz')}
        draw.text((10,number*235+5), part+' / color / AO / roughness / normal', fill='white')
        for i,key in enumerate(['color','ao','orm','normal']):
            im=Image.fromarray(images[key])
            if key=='orm': im=Image.fromarray(images[key][:,:,1]).convert('RGB')
            montage.paste(im.resize((220,200)),(170+i*240,number*235+25))
    for path, expected in inputs.items(): require(sha(path)==expected,'Input modified during audit')
    montage.save(output/'map-overview.jpg')
    shutil.copyfile(__file__,output/'executed-audit.py')
    save(output/'audit.json',{'schemaVersion':1,'frozenInputs':inputs,'parts':rows,
                             'limitations':'Native skin-node UV area samples include hidden caps; not visible-only calibration.'})
    print(json.dumps({k:{'bounds':v['boundsMetres'],'shade':v['nativeUVShade']['shadeMean'],
                         'shadeStd':v['nativeUVShade']['shadeStd'], 'ao':v['nativeUVAO'],
                         'rough':v['nativeUVRoughness']} for k,v in rows.items()},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('manifest','ascii-root','palette','output'): parser.add_argument('--'+key,type=Path,required=True)
    args=parser.parse_args();run(args.manifest,args.ascii_root,args.palette,args.output)
