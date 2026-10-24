"""Shared Pixal request construction. Asset runners own their manifest contracts."""
from pathlib import Path
import uuid
from .common import (read,write,pin,require,manifest,bindings,asset,source_version,code_pins,verification_pass)
from . import comfy


def apply_export_settings(graph, settings):
    """Apply bounded mesh-only settings; omitted options preserve the frozen CLI recipe."""
    require(isinstance(settings, dict)
            and {'remeshResolution', 'targetFaceCount'} <= set(settings)
            and set(settings) <= {'remeshResolution', 'targetFaceCount', 'signMode', 'manifold'},
            'Unsupported mesh export settings')
    resolution=settings['remeshResolution']; count=settings['targetFaceCount']
    require(type(resolution) is int and 128 <= resolution <= 1536
            and type(count) is int and 4 <= count <= 200000, 'Invalid item export settings')
    mode=settings.get('signMode')
    require(mode is None or mode in ('udf', 'sdf'), 'Unsupported remesh sign mode')
    require('manifold' not in settings or (mode == 'sdf' and type(settings['manifold']) is bool),
            'Manifold remeshing requires explicit SDF mode')
    for node in graph.values():
        if node['class_type'] == 'RemeshMesh':
            node['inputs']['resolution']=resolution
            if mode is not None:
                # DynamicCombo uses a scalar selector and flattened sub-widget
                # keys on the wire; Comfy assembles the execute() dictionary.
                for key in list(node['inputs']):
                    if key.startswith('sign_mode.'): del node['inputs'][key]
                node['inputs']['sign_mode']=mode
                node['inputs']['sign_mode.qef']=False
                if mode == 'sdf': node['inputs']['sign_mode.manifold']=settings.get('manifold', False)
                else:
                    node['inputs']['sign_mode.drop_inverted_components']=False
                    node['inputs']['sign_mode.drop_enclosed_components']=False
        if 'target_face_count' in node['inputs']: node['inputs']['target_face_count']=count
    return graph


def apply_geometry_seed_offset(graph, offset):
    """Vary geometry noise explicitly while preserving the frozen sampler recipe."""
    require(type(offset) is int and 0 <= offset <= 2147483647, 'Invalid geometry seed offset')
    samplers = [node['inputs'] for node in graph.values() if node['class_type'] == 'KSampler']
    require(len(samplers) == 3 and all(type(row.get('seed')) is int for row in samplers),
            'Expected exactly three frozen geometry samplers')
    for row in samplers: row['seed'] += offset
    return graph


def prepare_request(*args,**kwargs):
    with verification_pass('client-prepare') as session:
        result=_prepare_request(*args,**kwargs)
    output=kwargs.get('output',args[3] if len(args)>3 else None)
    write(Path(output).with_suffix('.verification.json'),session.report(),fresh=True)
    return result


def _prepare_request(manifest_path, bindings_path, stage, output, *, runtime=None, comfy_runtime=None,
                    manifest_reader=manifest, extra_pins=(), namespace="headkit",
                    version=None, read_json=read, export_settings=None, generation_subject=None,background=None,
                    geometry_seed_offset=0, model_verification=None):
    require(namespace in ("headkit", "itemkit"), "Unsupported generation namespace")
    data=manifest_reader(manifest_path);local=bindings(bindings_path)
    require(data.get('approval',{}).get('inputReviewComplete') is True,'Review measured input overlays and feature inventory before GPU preparation')
    profile=data.get('profile','pixal-single-v1');camera=data.get('camera',{})
    if stage in ('geometry','appearance'):
        require(camera.get('reviewed') is True,'Reviewed camera calibration required')
    names={'calibrate':['geometry','detail','mask'],'geometry':['geometry'],'appearance':['detail'],'export':[]}[stage]
    if profile=='pixal-multiview-v1' and stage=='geometry':names=['front','left','back','right']
    require(stage!='geometry' or (data.get('features') and all(x.get('placementReviewed') is True for x in data['features'])),
            'Review hairstyle routing, all accessories and counts before generation')
    shape=asset(manifest_path,data['inputs']['shape']) if stage=='appearance' else None
    expected_mesh=asset(manifest_path,data['inputs']['geometryRaw']) if stage=='appearance' else None
    if stage=='appearance':
        review=data.get('approval',{}).get('generatedGeometry',{})
        require(review.get('decision')=='approved' and bool(review.get('notes','').strip())
                and review.get('geometryRawSha256')==expected_mesh['sha256']
                and review.get('shapeSha256')==shape['sha256'],
                'Approve generated clay with geometryRaw and shape hashes before appearance preparation')
    export_source=asset(manifest_path,data['inputs']['exportSource']) if stage=='export' else None
    if stage=='export':
        review=data.get('approval',{}).get('exportGeometry',{})
        require(review.get('decision')=='approved' and bool(review.get('notes','').strip())
                and review.get('exportSourceSha256')==export_source['sha256'],
                'Approve generated clay with the exact exportSource hash before export preparation')
    binding_pin=pin(bindings_path)
    images={};pins=[pin(manifest_path),binding_pin]+code_pins()+list(extra_pins)
    if runtime is not None:pins.extend(runtime[name] for name in ('toolchain','migrationReceipt','python'))
    from .source_inventory import freeze_sources,validate_comfy_runtime
    inventory=freeze_sources(local)
    comfy_runtime=validate_comfy_runtime(comfy_runtime,inventory['roots'],inventory)
    # Runtime dependency bytes are checked in the owning Comfy process at
    # preparation and again under the submission lock. Do not make the client
    # and its launcher read that same environment several more times.
    pins+=inventory['files']
    adapter=Path(local['comfyCustomNodes'])/'srn_headkit'
    source_config=adapter/'source-roots.json'
    require(read_json(source_config)=={'schemaVersion':1,'inventory':inventory},
            'Installed Comfy source snapshot differs; reinstall the current adapter and restart ComfyUI')
    pins.append(pin(source_config))
    for code in (Path(__file__).parent/'comfy_nodes').glob('*.py'):
        installed=adapter/code.name;require(pin(installed)['sha256']==pin(code)['sha256'],'Installed headkit nodes differ; install current adapters and restart ComfyUI')
        pins.append(pin(installed))
    root=Path(local['comfyInput']).resolve();token=uuid.uuid4().hex;staging=root/namespace/token;staging.mkdir(parents=True,exist_ok=False)
    for name in names:
        source=asset(manifest_path,data['inputs'][name]);pins.append(source)
        target=staging/(name+'.png')
        from PIL import Image
        image=Image.open(source['path']).convert('RGBA')
        if name=='mask':image.save(target)
        elif background is not None:
            # The calibration crop applies its selected mask once. Preserve
            # unassociated source RGB here, especially on existing soft alpha.
            image.convert('RGB').save(target)
        else:
            canvas=Image.new('RGBA',image.size,(0,0,0,255));canvas.alpha_composite(image);canvas.convert('RGB').save(target)
        images[name]=target.relative_to(root).as_posix();pins.append(pin(target))
    pins += [p for p in (shape,export_source) if p]
    if expected_mesh:pins.append(expected_mesh)
    graph=comfy.compile_graph(stage,profile,images,namespace+'/'+token,fov=camera.get('fovDegrees'),shape=shape,source=export_source,background=background)
    if stage == 'geometry':
        apply_geometry_seed_offset(graph, geometry_seed_offset)
    if export_settings is not None:
        require(stage == 'export', 'Export settings apply only to mesh export')
        apply_export_settings(graph, export_settings)
    from .comfy_nodes.model_resolution import loader_models,bind_loader_models
    from .model_contract import model_contract, SERVER_MODEL_VERIFICATION
    require(model_verification in (None, SERVER_MODEL_VERIFICATION), 'Unsupported model verification protocol')
    checkpoints=read_json(Path(__file__).parent/'checkpoints.json')
    if model_verification == SERVER_MODEL_VERIFICATION:
        models, model_inputs=model_contract(graph,local.get('models',{}),checkpoints)
    else:
        models=loader_models(graph,local.get('models',{}),checkpoints)
        model_inputs=[local['models'][model['name']] for model in models]
    graph=bind_loader_models(graph,models)
    # Pin each model's filename, Comfy folder category, resolved path identity and bytes.
    if model_verification is None:
        for row in model_inputs:
            if row not in pins:pins.append(row)
    result={'stage':stage,'profile':profile,'token':token,'prompt':graph,'inputs':pins,'codeVersion':version or source_version(),
            'timeoutSeconds':2700,'generationCeiling':100,'expectedGeometry':expected_mesh,'comfySourceInventory':inventory,
            'comfyRuntimeIdentity':comfy_runtime,'runtimeIdentity':runtime,'bindings':binding_pin,'comfyEndpoint':comfy.Client(local['comfyUrl']).url,
            'loaderModels':models}
    result['outputNamespace']=namespace
    result['runtimeVerification']='server-owned'
    if model_verification is not None:
        result['modelVerification']=model_verification
        result['modelInputs']=model_inputs
        # The client launcher does not consume model bytes. The server resolves
        # and hashes them freshly here and again at dispatch and completion.
        result['modelPreparationProof']=comfy.verify_loader_models(comfy.Client(local['comfyUrl']),result)
    if background is not None:result['backgroundDecision']=background
    if generation_subject is not None: result['generationSubject']=generation_subject
    if stage == 'geometry' and geometry_seed_offset: result['geometrySeedOffset']=geometry_seed_offset
    write(output,result,fresh=True);return result
