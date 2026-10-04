"""Prepare a pinned fresh-map graph; never submit or modify the Comfy queue.

Template mode freezes supported installed schemas and the unchanged v6 latent
ancestry. Instantiate mode additionally requires root-reviewed clean-source
gates and byte-identical local/server geometry. No template is dispatchable.
"""
import argparse
import copy
import hashlib
import json
import re
import shutil
import urllib.request
from pathlib import Path

P = Path(__file__).resolve().parent
COMFY = Path('F:/Comfy-Desktop/ComfyUI-Installs/ComfyUI/ComfyUI')
SHARED = Path('F:/Comfy-Desktop/ComfyUI-Shared')
PARENT = P / 'comfy-v6/workflow-api.json'
PARENT_SHA = '4fdeb6375e706e0c4b8c8d708989c66f9f8d2bd979f0ca12178c09ec787f6ea2'
RAW_SHA = '9392865b50dd48400a415e1bd2f7e7255cf17b47bc292a005fe858042610037d'
REJECTED = {
    RAW_SHA,
    '02d51a168c6cf40ad49c10066ed638c3bb2159d5f1c1e02630acc5e8b1b84b0d',
    '8dab9ee5a3a6a1596b0577693e3321f23634976f04fc255a1e1c8204a21d9559',
    '449390eab7a81816817a4b15d60cc439e21ddb39c134819fb0858abca2dcad62',
    '400deaad37c71c7ce13bf5b19fff31b67773ff613f32054191eb034642b23821',
}


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while block := stream.read(4 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def links(node):
    for key, value in node['inputs'].items():
        if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str) and isinstance(value[1], int):
            yield key, value


def closure(graph, roots):
    needed = set()
    def visit(key):
        require(key in graph, 'Absent graph dependency ' + key)
        if key in needed:
            return
        needed.add(key)
        for _, (parent, _) in links(graph[key]):
            visit(parent)
    for root in roots:
        visit(root)
    return {key: node for key, node in graph.items() if key in needed}


def graph_for(model_file, prefix):
    require(sha(PARENT) == PARENT_SHA, 'Original accepted conditioning graph changed')
    graph = json.loads(PARENT.read_text())
    # Replace the UDF source entirely; the decoded shape mesh is used only for
    # voxel texture subdivision ancestry, never as final geometry authority.
    graph['241'] = {'class_type': 'Get3DComponents', 'inputs': {'model_3d': ['2000', 0]}}
    graph['2000'] = {'class_type': 'Load3DAdvanced', 'inputs': {
        'model_file': model_file, 'viewport_state': '', 'width': 1024, 'height': 1024}}
    graph['210']['inputs'].update(base_color=['147', 0], metallic=['147', 1],
        roughness=['147', 2], occlusion=['233', 0], normal_map=['224', 0])
    # ApplyTextureToMesh exports the exact normal/TBN used by the fresh bake.
    # The actual original hand/arm stage audit disproved a basis mismatch:
    # final smoothing reproduced every measured normal exactly. Omit that
    # redundant operation here to make the fresh hand bake/export basis explicit.
    graph['285']['inputs']['mesh'] = ['210', 0]
    graph['372']['inputs']['filename_prefix'] = prefix + '/textured'
    graph['2001'] = {'class_type': 'MeshToFile3D', 'inputs': {'mesh': ['196', 0]}}
    graph['2002'] = {'class_type': 'Save3DAdvanced', 'inputs': {
        'model_3d': ['2001', 0], 'filename_prefix': prefix + '/uv-master',
        'viewport_state': '', 'width': 1024, 'height': 1024}}
    graph = closure(graph, ['372', '2002'])
    require(not any(n['class_type'] == 'RemeshMesh' for n in graph.values()), 'Legacy UDF remesh remains')
    require('252' not in graph and '1014' not in graph, 'Unrelated historic mesh save remains')
    require('260' not in graph, 'Redundant post-bake normal operation remains in this fresh hand graph')
    require(graph['147']['inputs']['reference_mesh'] == ['241', 0] and
        graph['224']['inputs']['high_poly'] == ['241', 0] and
        graph['233']['inputs']['high_poly'] == ['241', 0], 'Fresh map high-poly ownership failed')
    return graph


def validate(graph, schemas):
    checked = []
    for key, node in graph.items():
        cls = node['class_type']
        require(cls in schemas, 'Installed node absent ' + cls)
        schema = schemas[cls]
        required = schema['input'].get('required', {})
        optional = schema['input'].get('optional', {})
        require(set(required) <= set(node['inputs']), 'Required inputs absent ' + key)
        # Original graph has no conditional-remesh widgets after replacement.
        require(set(node['inputs']) <= set(required) | set(optional), 'Unknown installed inputs ' + key)
        for input_key, (upstream, output) in links(node):
            outputs = schemas[graph[upstream]['class_type']]['output']
            require(0 <= output < len(outputs), 'Invalid linked output ' + key)
            expected = (required | optional)[input_key][0]
            actual = outputs[output]
            require(expected == actual or expected == '*' or actual == '*' or
                (isinstance(expected, str) and actual in expected.split(',')),
                f'Installed link type mismatch {key}.{input_key}: {actual} -> {expected}')
            checked.append([key, input_key, upstream, output, actual])
    return checked


def frozen_dependencies():
    prep = json.loads((P / 'comfy-v6/preparation.json').read_text())
    deps = {Path(p): h for p, h in prep['externalDependencies'].items()}
    relative = ['folder_paths.py', 'comfy_extras/nodes_load_3d.py',
        'comfy_extras/nodes_mesh_io.py', 'comfy_extras/nodes_mesh_postprocess.py',
        'comfy_extras/nodes_save_3d.py', 'comfy_extras/nodes_trellis2.py',
        'comfy_extras/mesh3d/postprocess/qem_decimate.py',
        'comfy_extras/mesh3d/postprocess/remesh.py',
        'comfy_extras/mesh3d/fileio/gltf_read.py',
        'comfy_extras/mesh3d/fileio/mesh_file_read.py',
        'comfy_extras/mesh3d/uv_unwrap/mesh.py',
        'comfy_extras/mesh3d/uv_unwrap/segment.py',
        'comfy_extras/mesh3d/uv_unwrap/parameterize.py',
        'comfy_extras/mesh3d/uv_unwrap/pack.py']
    for rel in relative:
        path = COMFY / rel
        require(path.is_file(), 'Installed implementation missing ' + str(path))
        deps[path] = sha(path)
    for path, digest in deps.items():
        require(sha(path) == digest, 'Conditioning implementation drift ' + str(path))
    return deps


def reference_pins(graph):
    prep = json.loads((P / 'comfy-v6/preparation.json').read_text())
    result = []
    for key, node in graph.items():
        if node['class_type'] != 'LoadImage':
            continue
        filename = node['inputs']['image']
        view = Path(filename).stem
        local = Path(prep['views'][view]['source'])
        server = SHARED / 'input' / filename
        digest = prep['views'][view]['sha256']
        require(sha(local) == sha(server) == digest, 'Accepted six-view references changed ' + view)
        result.append({'view': view, 'localPath': str(local), 'serverPath': str(server), 'sha256': digest})
    require(len(result) == 6, 'Exactly six original views required')
    return result


def resolve_clean(cfg):
    require(cfg.get('schemaVersion') == 1, 'Source acceptance contract version required')
    source = cfg['source']
    local, server = Path(source['localPath']), Path(source['serverPath'])
    digest = source['sha256']
    require(re.fullmatch('[0-9a-f]{64}', digest) and digest not in REJECTED,
        'A separately gated clean exterior is required; known rejected masters cannot be textured')
    require(sha(local) == sha(server) == digest, 'Exact local/server clean-source hashes differ')
    accept = cfg['acceptance']
    require(accept.get('sourceSha256') == digest and accept.get('rawAncestorSha256') == RAW_SHA,
        'Clean exterior/raw ancestry not pinned')
    gates = ['topologyPassed', 'singleExteriorPassed', 'gripPreserved',
        'anatomyReviewed', 'coordinateFramePreserved']
    require(all(accept.get(g) is True for g in gates), 'All measured clean-source gates must pass')
    require(len(accept.get('reviewEvidence', '')) > 100 and len(accept.get('receipts', [])) >= 3,
        'Actual topology, occupancy/opening and anatomy/frame receipts required')
    receipts = []
    for receipt in accept['receipts']:
        path = Path(receipt['path'])
        require(sha(path) == receipt['sha256'], 'Clean-source review receipt changed')
        receipts.append({'path': str(path.resolve()), 'sha256': receipt['sha256']})
    annotation = source['modelFileAnnotated']
    require(annotation.endswith(' [output]') or annotation.endswith(' [input]'), 'Explicit server path annotation required')
    folder = 'output' if annotation.endswith(' [output]') else 'input'
    name = annotation.rsplit(' [', 1)[0]
    resolved = (SHARED / folder / name).resolve()
    require(resolved == server.resolve(), 'Annotated Comfy source resolves to a different file')
    prefix = cfg['outputPrefix']
    require(re.fullmatch(r'srn_purpose_built_parts/[A-Za-z0-9_/-]+', prefix) and '..' not in prefix
        and not prefix.startswith('srn_purpose_built_parts/purpose-built-human-male-gripping-hand-orthographic-v6-'),
        'Fresh safe output prefix required')
    return annotation, prefix, {'source': source, 'acceptance': accept, 'verifiedReceipts': receipts}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['template', 'instantiate'])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source-contract', type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    require(out.parent == P.resolve() and not out.exists(), 'Fresh owned output directory required')
    if args.mode == 'instantiate':
        require(args.source_contract is not None, 'Pinned clean-source contract required')
        model_file, prefix, acceptance = resolve_clean(json.loads(args.source_contract.read_text()))
    else:
        model_file, prefix = '__CLEAN_HIGH_POLY_ANNOTATED_PATH__', '__FRESH_OUTPUT_PREFIX__'
        acceptance = None
    graph = graph_for(model_file, prefix)
    with urllib.request.urlopen('http://127.0.0.1:8188/object_info', timeout=30) as response:
        live = json.load(response)
    schemas = {n['class_type']: live[n['class_type']] for n in graph.values()}
    link_proof = validate(graph, schemas)
    dependencies = frozen_dependencies()
    references = reference_pins(graph)
    out.mkdir()
    write(out / ('workflow-api.json' if acceptance else 'workflow-api-template.json'), graph)
    write(out / 'installed-node-schemas.json', schemas)
    write(out / 'link-type-proof.json', link_proof)
    if acceptance:
        shutil.copy2(args.source_contract, out / 'executed-source-contract.json')
    else:
        write(out / 'source-contract-template.json', {'schemaVersion': 1,
            'source': {'localPath': '__CLEAN_HIGH_POLY_LOCAL__', 'serverPath': '__BYTE_IDENTICAL_COMFY_COPY__',
                'sha256': '__ACTUAL_CLEAN_HASH__', 'modelFileAnnotated': '__RELATIVE_PATH__ [output]'},
            'acceptance': {'sourceSha256': '__ACTUAL_CLEAN_HASH__', 'rawAncestorSha256': RAW_SHA,
                'topologyPassed': False, 'singleExteriorPassed': False, 'gripPreserved': False,
                'anatomyReviewed': False, 'coordinateFramePreserved': False,
                'reviewEvidence': '__ROOT_REVIEW_OF_MEASURED_PASSED_GATES__',
                'receipts': [{'path': '__TOPOLOGY_RECEIPT__', 'sha256': '__ACTUAL_HASH__'},
                    {'path': '__OCCUPANCY_AND_OPENING_RECEIPT__', 'sha256': '__ACTUAL_HASH__'},
                    {'path': '__ANATOMY_AND_FRAME_RECEIPT__', 'sha256': '__ACTUAL_HASH__'}]},
            'outputPrefix': 'srn_purpose_built_parts/__FRESH_CLEAN_HAND_TEXTURE_PREFIX__'})
    tools = out / 'frozen-tools'; tools.mkdir()
    for number, (path, digest) in enumerate(dependencies.items()):
        require(sha(path) == digest, 'Installed texture dependency changed while freezing')
        shutil.copy2(path, tools / f'{number:02d}-{path.name}')
    shutil.copy2(__file__, out / 'executed-builder.py')
    write(out / 'preparation.json', {'schemaVersion': 1,
        'state': 'prepared-not-submitted' if acceptance else 'parameterized-template-not-dispatchable',
        'queueChanged': False, 'submitted': False, 'sourceAdopted': False,
        'parentApi': str(PARENT), 'parentApiSha256': PARENT_SHA,
        'parentGeneration': str(P / 'comfy-v6/generation.json'),
        'parentGenerationSha256': sha(P / 'comfy-v6/generation.json'),
        'geometryAuthority': 'Exact separately gated clean high-poly loaded in unchanged source glTF frame',
        'textureLatentAuthority': 'Original v13 six-view neural ancestor closure; exact parent samplers and seeds',
        'latentReplayLimitation': 'Unsaved hidden latents may recompute; new texture output must be reviewed. Final geometry is loaded exact clean source, not recomputed decoded mesh.',
        'maps': {'baseColor': 2048, 'metallic': 2048, 'roughness': 2048,
            'normal': 2048, 'ao': 1024, 'normalStrength': 1, 'normalAtlasReused': False},
        'normalBasisPolicy': 'Smooth before UV/bake; final serialization uses exact ApplyTextureToMesh normals and tangents, with no post-bake normal recomputation',
        'graphNodes': len(graph), 'saveNodes': ['372', '2002'],
        'cleanSourceAcceptance': acceptance, 'references': references,
        'installedDependencies': {str(p): h for p, h in dependencies.items()},
        'builderSha256': sha(__file__),
        'frozenFiles': {str(p.relative_to(out)): sha(p) for p in out.rglob('*') if p.is_file()},
        'postJobGates': ['Verify exact geometry lineage after decimation/unwrap and material application',
            'Full manifold, winding, intersections, degeneracy and authored attribute audit',
            'Recheck wrist two-hit/solid section and four grip-core clear lines',
            'Five-digit anatomy/chirality review before strict stock fit',
            'Actual native UV/normal/tangent transport and forearm skin/roughness calibration by root'],
        'clientAccepted': False})
    print(json.dumps({'mode': args.mode, 'output': str(out), 'nodes': len(graph),
        'linksChecked': len(link_proof), 'queueChanged': False}))


if __name__ == '__main__':
    main()
