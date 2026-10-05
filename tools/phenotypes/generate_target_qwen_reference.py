"""Freeze, submit once, and recover target references using the saved Qwen 2.1 graph.

The saved workflow is never edited. Its single subgraph is expanded using named
interface slots, with the disabled prompt enhancer's unused branch omitted.
Native reference conditioning uses the first camera guide's matching latent.
This raster reference job is separate from the orthographic 3D reconstruction.
"""
from __future__ import annotations

import argparse
import copy
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import shutil
import sys
from datetime import datetime, timezone
import urllib.parse
import urllib.request
import uuid

from PIL import Image
from pipeline import Comfy, ancestors, save_json
from target_contract import binding, load, require, sha, verify_binding


EXPECTED = {451: 'UNETLoader', 452: 'TextEncodeQwenImage21', 453: 'CLIPLoader',
            454: 'VAELoader', 456: 'EmptyLatentImage', 457: 'VAEDecode',
            458: 'KSampler', 471: 'TextGenerate', 472: 'PreviewAny',
            473: 'CLIPLoader', 474: 'ComfySwitchNode',
            475: 'PrimitiveStringMultiline', 480: 'QwenImage21Cache'}


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def freeze(path, value):
    require(not Path(path).exists(), 'Frozen artifact already exists: ' + str(path))
    save_json(Path(path), value)


def pin(path):
    path = Path(path).resolve()
    return {'path': str(path), 'sha256': sha(path), 'bytes': path.stat().st_size}


def verify_pins(items):
    for item in items:
        require(sha(item['path']) == item['sha256'], 'Pinned input changed: ' + item['path'])


def expand_graph(workflow, schemas, prompt_text, seed, references, dimensions, prefix):
    """Expand this reviewed workflow, refusing unknown or unresolved graph edges."""
    require(isinstance(prompt_text, str) and bool(prompt_text.strip()), 'Explicit nonempty prompt required')
    require(type(seed) is int and 0 <= seed < 2**64, 'Explicit uint64 seed required')
    require(len(dimensions) == 2 and all(type(x) is int and x > 0 and x % 32 == 0 for x in dimensions),
            'Guide dimensions must be positive integer multiples of32')
    encode_schema = schemas.get('TextEncodeQwenImage21', {})
    require(encode_schema.get('output') == ['CONDITIONING', 'CONDITIONING', 'LATENT'],
            'Native Qwen conditioning/matching latent outputs changed')
    encode_inputs = encode_schema.get('input', {})
    require('images' in encode_inputs.get('required', {}) and
            'vae' in encode_inputs.get('optional', {}), 'Native Qwen image/VAE conditioning unavailable')
    groups = workflow.get('definitions', {}).get('subgraphs', [])
    require(len(groups) == 1, 'Exactly one reviewed Qwen subgraph required')
    group = groups[0]
    require(len({n['id'] for n in workflow['nodes']}) == len(workflow['nodes']),
            'Duplicate top-level node ID')
    require(len({n['id'] for n in group['nodes']}) == len(group['nodes']),
            'Duplicate subgraph node ID')
    require(len({item['name'] for item in group['inputs']}) == len(group['inputs']),
            'Duplicate subgraph interface name')
    parent = next((n for n in workflow['nodes'] if n['type'] == group['id']), None)
    require(parent is not None and parent.get('mode', 0) == 0, 'Active Qwen interface missing')
    top = {n['id']: n for n in workflow['nodes']}
    require(top.get(461, {}).get('type') == 'SaveImageAdvanced', 'Reviewed PNG save node missing')
    require(top.get(13, {}).get('type') == 'ResolutionSelector', 'Reviewed resolution node missing')
    nodes = {n['id']: n for n in group['nodes']}
    require({i: n['type'] for i, n in nodes.items()} == EXPECTED, 'Qwen subgraph inventory changed')
    require(all(n.get('mode', 0) == 0 for n in nodes.values()), 'Disabled/bypassed Qwen node')
    external = copy.deepcopy(parent['widgets_values_named'])
    require(external.get('switch') is False, 'Prompt enhancer must remain disabled')
    external.update(prompt=prompt_text, seed=seed, width=dimensions[0], height=dimensions[1])
    links = {link['id']: link for link in group['links']}
    require(len(links) == len(group['links']), 'Duplicate subgraph link ID')
    interface = group['inputs']
    graph = {}
    node_prefix = str(parent['id']) + ':'
    for number, node in nodes.items():
        kind = node['type']
        require(kind in schemas, 'Live node schema missing: ' + kind)
        schema = schemas[kind].get('input', {})
        permitted = set(schema.get('required', {})) | set(schema.get('optional', {}))
        values = node.get('widgets_values_named', {}) or {}
        inputs = {k: copy.deepcopy(v) for k, v in values.items() if k in permitted or '.' in k}
        for item in node.get('inputs', []):
            if item.get('link') is None:
                continue
            require(item['link'] in links, 'Unresolved subgraph input link')
            edge = links[item['link']]
            require(edge['target_id'] == number and
                    node['inputs'][edge['target_slot']]['name'] == item['name'],
                    'Subgraph link destination mismatch')
            if edge['origin_id'] == -10:
                slot = edge['origin_slot']
                require(0 <= slot < len(interface), 'Unknown interface slot')
                name = interface[slot]['name']
                require(name in external, 'Missing interface value: ' + name)
                inputs[item['name']] = copy.deepcopy(external[name])
            else:
                require(edge['origin_id'] in nodes, 'Unresolved internal Qwen source')
                outputs = nodes[edge['origin_id']].get('outputs', [])
                require(0 <= edge['origin_slot'] < len(outputs), 'Unknown Qwen output slot')
                inputs[item['name']] = [node_prefix + str(edge['origin_id']), edge['origin_slot']]
        graph[node_prefix + str(number)] = {'class_type': kind, 'inputs': inputs}
    switch = graph[node_prefix + '474']['inputs']
    require(switch.get('switch') is False and switch.get('on_false') == prompt_text,
            'Disabled enhancer does not select the original prompt')
    switch.pop('on_true', None)  # native lazy switch selects on_false exactly
    require(1 <= len(references) <= 16, 'At least one camera guide reference required')
    encode = graph[node_prefix + '452']['inputs']
    encode.update(vae=[node_prefix + '454', 0], resolution=0)
    for index, reference in enumerate(references, 1):
        require('LoadImage' in schemas, 'Native image loader missing')
        key = 'reference_' + str(index)
        graph[key] = {'class_type': 'LoadImage', 'inputs': {'image': reference}}
        encode['images.image_' + str(index)] = [key, 0]
    graph[node_prefix + '458']['inputs']['latent_image'] = [node_prefix + '452', 2]
    outer = next((link for link in workflow['links'] if link[0] == 672), None)
    require(outer is not None and outer[1:5] == [parent['id'], 0, 461, 0],
            'Saved image output binding changed')
    out_edges = [e for e in group['links'] if e['target_id'] == -20 and e['target_slot'] == 0]
    require(len(out_edges) == 1 and out_edges[0]['origin_id'] == 457 and
            out_edges[0]['origin_slot'] == 0, 'Subgraph image output changed')
    save_values = copy.deepcopy(top[461]['widgets_values_named'])
    require(save_values.get('format') == 'png', 'PNG save required for native alpha')
    save_values.update(images=[node_prefix + '457', 0], filename_prefix=prefix)
    graph['461'] = {'class_type': 'SaveImageAdvanced', 'inputs': save_values}
    graph = ancestors(graph, ('461',))
    require(not any(n['class_type'] == 'TextGenerate' for n in graph.values()),
            'Unused prompt enhancer remained executable')
    require(graph[node_prefix + '458']['inputs']['positive'] == [node_prefix + '452', 0]
            and graph[node_prefix + '458']['inputs']['negative'] == [node_prefix + '452', 1],
            'Positive/negative conditioning ownership changed')
    return graph


def prepare(args):
    root = args.output.resolve()
    require(not (root / 'preparation.json').exists(), 'Preparation already frozen')
    root.mkdir(parents=True, exist_ok=True)
    config = read(args.config)
    target_path = Path(config['targetContract'])
    require(sha(target_path) == config['targetContractSha256'], 'Configured target changed')
    target = load(target_path)
    require(config['part'] in ('legl', 'shinl', 'footl', 'forel', 'handl'),
            'Declared individual limb donor required')
    require(config.get('schemaVersion') == 1 and config.get('workflow') == 'image_qwen_image_2_1_t2i.json',
            'Explicit reviewed Qwen2.1 configuration required')
    service = Comfy(config['service'])
    workflow = service.request('/userdata/' + urllib.parse.quote('workflows/' + config['workflow'], safe=''))
    schemas = service.request('/object_info')
    queue = service.request('/queue')
    prompt_text = Path(config['prompt']).read_text(encoding='utf-8')
    reference_pins = []
    for index, item in enumerate(config['references'], 1):
        require(sha(item['path']) == item['sha256'], 'Reference changed: ' + item['path'])
        with Image.open(item['path']) as image:
            size, mode = image.size, image.mode
        reference_pins.append({**pin(item['path']), 'role': item['role'], 'order': index,
                               'dimensions': list(size), 'mode': mode})
    dimensions = reference_pins[0]['dimensions']
    require(all(x > 0 and x % 32 == 0 for x in dimensions), 'Camera guide size must be a multiple of32')
    graph = expand_graph(workflow, schemas, prompt_text, config['seed'],
                         ['PENDING_REFERENCE_' + str(i) for i in range(1, len(reference_pins)+1)],
                         dimensions, config['outputPrefix'])
    dependencies = [Path(p).resolve() for p in config['dependencyPaths']]
    with ThreadPoolExecutor(max_workers=3) as pool:
        dependency_pins = list(pool.map(pin, dependencies))
    for name, value in (('workflow-source.json', workflow), ('object-info.json', schemas),
                        ('queue-before-preparation.json', queue), ('config.json', config),
                        ('workflow-api-template.json', graph)):
        freeze(root / name, value)
    (root / 'prompt.txt').write_text(prompt_text, encoding='utf-8')
    snapshot = root / 'helper-snapshot.py'
    require(not snapshot.exists(), 'Helper snapshot exists')
    shutil.copyfile(__file__, snapshot)
    all_pins = [pin(args.config), pin(root/'config.json'), pin(root/'workflow-source.json'),
                pin(root/'object-info.json'), pin(root/'workflow-api-template.json'),
                pin(root/'prompt.txt'), pin(snapshot), pin(Path(__file__).with_name('pipeline.py')),
                pin(Path(__file__).with_name('target_contract.py'))] + reference_pins + dependency_pins
    receipt = {**binding(target_path, target, 'working'), 'schemaVersion': 1,
               'kind': 'target-qwen-reference-preparation', 'createdUtc': now(),
               'part': config['part'], 'service': config['service'],
               'savedWorkflow': config['workflow'], 'pins': all_pins,
               'references': reference_pins, 'dimensions': dimensions,
               'settings': graph[str(next(n['id'] for n in workflow['nodes']
                                          if n['type'] == workflow['definitions']['subgraphs'][0]['id']))+':458']['inputs'],
               'changes': ['named subgraph expansion', 'native reference images and VAE conditioning',
                           'matching first-reference latent replaces EmptyLatentImage',
                           'disabled enhancer unused branch omitted', 'explicit prompt/seed/output prefix'],
               'cameraLimitation': 'Generated raster views approximate the frozen orthographic guide; inspect before reconstruction.',
               'orthographic3dAdapterRequired': True, 'referenceAccepted': False,
               'geometryAccepted': False, 'clientAccepted': False}
    freeze(root/'preparation.json', receipt)
    print(json.dumps({'prepared': str(root), 'references': len(reference_pins),
                      'dimensions': dimensions, 'nodes': len(graph),
                      'dependencies': len(dependency_pins), 'preparationSha256': sha(root/'preparation.json')}))


def checked_preparation(root):
    record = read(root/'preparation.json')
    verify_pins(record['pins'])
    require(sha(__file__) == sha(root/'helper-snapshot.py'),
            'Executing Qwen helper changed after preparation; preserve history and prepare a fresh job')
    target = load(record['targetContract'])
    verify_binding(record, record['targetContract'], target, 'working')
    return record


def submit(args):
    root = args.output.resolve()
    require(not (root/'generation.json').exists(), 'Dispatch receipt exists: recover/status; never resubmit')
    record = checked_preparation(root)
    service = Comfy(record['service'])
    queue = service.request('/queue')
    require(not queue.get('queue_running') and not queue.get('queue_pending'), 'ComfyUI occupied; preserve other jobs')
    freeze(root/'queue-before-submission.json', queue)
    graph = read(root/'workflow-api-template.json')
    uploads = []
    unique_id = 'srn-troll-qwen-' + uuid.uuid4().hex
    for index, item in enumerate(record['references'], 1):
        name = service.upload(Path(item['path']), unique_id)
        graph['reference_'+str(index)]['inputs']['image'] = name
        uploads.append({'source': item, 'serverPath': name})
    freeze(root/'uploads.json', uploads)
    freeze(root/'workflow-api.json', graph)
    receipt = {k: record[k] for k in ('targetContract', 'targetContractSha256', 'targetId', 'rigRevision', 'coordinateSpace')}
    receipt.update(schemaVersion=1, kind='target-qwen-reference-generation', createdUtc=now(),
                   service=record['service'], clientId=unique_id, state='submission-uncertain',
                   preparationSha256=sha(root/'preparation.json'), apiSha256=sha(root/'workflow-api.json'),
                   outputs=[], referenceAccepted=False, geometryAccepted=False, clientAccepted=False)
    freeze(root/'generation.json', receipt)  # must exist before any possibly uncertain POST
    response = service.request('/prompt', {'prompt': graph, 'client_id': unique_id,
                                          'extra_data': {'extra_pnginfo': {'srn_preparation_sha256': receipt['preparationSha256']}}})
    freeze(root/'dispatch-response.json', response)
    require(not response.get('node_errors') and response.get('prompt_id'), 'ComfyUI dispatch rejected; inspect receipt')
    receipt.update(promptId=response['prompt_id'], state='submitted')
    save_json(root/'generation.json', receipt)
    print(json.dumps({'state': receipt['state'], 'promptId': receipt['promptId'], 'clientId': unique_id}))


def recover_prompt_id(receipt, queue, history):
    matches = set()
    for row in queue.get('queue_running', []) + queue.get('queue_pending', []):
        if len(row) > 3 and row[3].get('client_id') == receipt['clientId']:
            matches.add(row[1])
    for key, item in history.items():
        row = item.get('prompt', [])
        if len(row) > 3 and row[3].get('client_id') == receipt['clientId']:
            matches.add(key)
    require(len(matches) <= 1, 'Multiple prompts share dispatch client identity')
    return next(iter(matches), None)


def status(args):
    root = args.output.resolve()
    receipt = read(root/'generation.json')
    record = checked_preparation(root)
    require(sha(root/'preparation.json') == receipt['preparationSha256'] and
            sha(root/'workflow-api.json') == receipt['apiSha256'], 'Dispatch artifacts changed')
    target = load(record['targetContract'])
    verify_binding(receipt, record['targetContract'], target, 'working')
    service = Comfy(receipt['service'])
    if 'promptId' not in receipt:
        queue, history = service.request('/queue'), service.request('/history')
        prompt_id = recover_prompt_id(receipt, queue, history)
        require(prompt_id is not None, 'Submission remains uncertain: no matching queue/history entry; do not resubmit')
        receipt['promptId'] = prompt_id
        freeze(root/('recovery-'+uuid.uuid4().hex+'.json'), {'queue': queue, 'history': history, 'promptId': prompt_id})
        save_json(root/'generation.json', receipt)
    history = service.request('/history/'+receipt['promptId'])
    if receipt['promptId'] not in history:
        queue = service.request('/queue')
        print(json.dumps({'state': 'queued-or-running', 'promptId': receipt['promptId'],
                          'running': [r[1] for r in queue.get('queue_running', [])],
                          'pending': [r[1] for r in queue.get('queue_pending', [])]}))
        return
    entry = history[receipt['promptId']]
    history_path = root/'history.json'
    if history_path.exists():
        require(read(history_path) == entry, 'Historical completed job changed')
    else:
        freeze(history_path, entry)
    state = entry.get('status', {}).get('status_str', 'unknown')
    if state == 'success':
        files = entry.get('outputs', {}).get('461', {}).get('images', [])
        require(len(files) == 1, 'Exactly one reference sheet expected')
        outputs = []
        for item in files:
            query = urllib.parse.urlencode({k: item[k] for k in ('filename', 'subfolder', 'type') if k in item})
            with urllib.request.urlopen(service.base+'/view?'+query, timeout=120) as response:
                data = response.read()
            path = root/'generated'/Path(item['filename']).name
            path.parent.mkdir(exist_ok=True)
            digest = hashlib.sha256(data).hexdigest()
            if path.exists():
                require(sha(path) == digest, 'Downloaded output changed')
            else:
                path.write_bytes(data)
            with Image.open(path) as image:
                require(list(image.size) == record['dimensions'], 'Output dimensions differ from camera guide')
                details = {'mode': image.mode, 'dimensions': list(image.size)}
                if image.mode == 'RGBA':
                    details['alphaRange'] = list(image.getchannel('A').getextrema())
            outputs.append({**item, **pin(path), **details})
        receipt['outputs'] = outputs
    receipt['state'] = state
    save_json(root/'generation.json', receipt)
    errors = [data for event, data in entry.get('status', {}).get('messages', [])
              if event in ('execution_error', 'execution_interrupted')]
    print(json.dumps({'state': state, 'promptId': receipt['promptId'], 'outputs': receipt['outputs'], 'errors': errors}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'submit', 'status'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--config', type=Path)
    args = parser.parse_args()
    if args.action == 'prepare':
        require(args.config is not None, 'Preparation requires explicit configuration')
    {'prepare': prepare, 'submit': submit, 'status': status}[args.action](args)


if __name__ == '__main__':
    main()
