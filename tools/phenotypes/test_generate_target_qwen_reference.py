"""Offline Qwen graph lineage and once-only dispatch/recovery regressions."""
import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

import generate_target_qwen_reference as qwen
import target_contract as contract


INTERFACE = ['prompt', 'switch', 'thinking', 'max_length', 'negative_prompt',
             'cfg', 'steps', 'width', 'height', 'scheduler', 'scheduler_1',
             'seed', 'unet_name', 'clip_name', 'vae_name', 'clip_name_1',
             'device', 'dtype_1']


def workflow_fixture():
    """A complete saved subgraph, including the unused enhancer branch."""
    values = dict(zip(INTERFACE, ['saved prompt', False, False, 4096, '', 1.0, 25,
        1024, 1024, 'euler', 'simple', 447606998181262, 'unet.safetensors',
        'clip.safetensors', 'vae.safetensors', 'enhancer.safetensors', 'auto', 'default']))
    ports = {
        451: ['MODEL'], 452: ['CONDITIONING', 'CONDITIONING', 'LATENT'],
        453: ['CLIP'], 454: ['VAE'], 456: ['LATENT'], 457: ['IMAGE'],
        458: ['LATENT'], 471: ['STRING'], 472: ['STRING'], 473: ['CLIP'],
        474: ['STRING'], 475: ['STRING'], 480: ['MODEL']}
    widgets = {
        451: {'weight_dtype': 'default'}, 452: {'resolution': 1024},
        453: {'type': 'qwen_image', 'device': 'default'},
        456: {'batch_size': 1}, 458: {'denoise': 1.0},
        471: {'sampling_mode': 'random'}, 473: {'type': 'qwen_image'},
        475: {'value': 'enhancer system instructions'}, 480: {'cache_threshold': .2}}
    nodes = {number: {'id': number, 'type': kind, 'mode': 0,
                     'inputs': [], 'outputs': [{'name': t, 'type': t} for t in ports[number]],
                     'widgets_values_named': widgets.get(number, {})}
             for number, kind in qwen.EXPECTED.items()}
    links = []

    def edge(origin, slot, destination, name):
        number = 600 + len(links)
        target_slot = len(nodes[destination]['inputs']) if destination in nodes else 0
        links.append({'id': number, 'origin_id': origin, 'origin_slot': slot,
                      'target_id': destination, 'target_slot': target_slot,
                      'type': 'test'})
        if destination in nodes:
            nodes[destination]['inputs'].append({'name': name, 'link': number})

    for source, slot, destination, name in [
        (453, 0, 452, 'clip'), (454, 0, 457, 'vae'), (458, 0, 457, 'samples'),
        (452, 0, 458, 'positive'), (452, 1, 458, 'negative'),
        (456, 0, 458, 'latent_image'), (474, 0, 472, 'source'),
        (472, 0, 452, 'prompt'), (480, 0, 458, 'model'), (451, 0, 480, 'model'),
        (471, 0, 474, 'on_true'), (473, 0, 471, 'clip'), (475, 0, 471, 'system_prompt')]:
        edge(source, slot, destination, name)
    for interface_name, destination, name in [
        ('prompt', 474, 'on_false'), ('switch', 474, 'switch'),
        ('negative_prompt', 452, 'negative_prompt'), ('cfg', 458, 'cfg'),
        ('steps', 458, 'steps'), ('width', 456, 'width'), ('height', 456, 'height'),
        ('scheduler', 458, 'sampler_name'), ('scheduler_1', 458, 'scheduler'),
        ('seed', 458, 'seed'), ('unet_name', 451, 'unet_name'),
        ('clip_name', 453, 'clip_name'), ('vae_name', 454, 'vae_name'),
        ('clip_name_1', 473, 'clip_name'), ('device', 480, 'device'),
        ('dtype_1', 480, 'dtype'), ('prompt', 471, 'prompt'),
        ('max_length', 471, 'max_length'), ('seed', 471, 'sampling_mode.seed'),
        ('thinking', 471, 'thinking')]:
        edge(-10, INTERFACE.index(interface_name), destination, name)
    edge(457, 0, -20, 'IMAGE')
    group = {'id': 'saved-qwen-group', 'nodes': list(nodes.values()), 'links': links,
             'inputs': [{'name': name} for name in INTERFACE]}
    workflow = {'definitions': {'subgraphs': [group]}, 'nodes': [
        {'id': 13, 'type': 'ResolutionSelector', 'mode': 0},
        {'id': 459, 'type': group['id'], 'mode': 0, 'widgets_values_named': values,
         'widgets_values': ['deliberately irrelevant positional widgets']},
        {'id': 461, 'type': 'SaveImageAdvanced', 'mode': 0,
         'widgets_values_named': {'format': 'png', 'filename_prefix': 'saved-prefix',
                                  'quality': 95, 'save_metadata': True}}],
        'links': [[672, 459, 0, 461, 0, 'IMAGE'], [670, 13, 0, 459, 7, 'INT'],
                  [671, 13, 1, 459, 8, 'INT']]}
    schemas = {}
    for node in nodes.values():
        permitted = set(node['widgets_values_named']) | {x['name'] for x in node['inputs']}
        schema = schemas.setdefault(node['type'], {'input': {'required': {}}, 'output': ports[node['id']]})
        schema['input']['required'].update({name: ['TEST'] for name in permitted})
    schemas['TextEncodeQwenImage21']['input']['required']['images'] = ['COMFY_AUTOGROW_V3']
    schemas['TextEncodeQwenImage21']['input']['optional'] = {'vae': ['VAE']}
    schemas['LoadImage'] = {'input': {'required': {'image': ['STRING']}}, 'output': ['IMAGE', 'MASK']}
    schemas['SaveImageAdvanced'] = {'input': {'required': {'images': ['IMAGE']}}, 'output': []}
    return workflow, schemas


def target_fixture():
    identity = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
    frames = {name: copy.deepcopy(identity) for name in contract.PART_JOINTS.values()}
    return {'schemaVersion': 2, 'kind': 'phenotype-target', 'id': 'qwen-test-troll',
        'identity': {'gender': 'male', 'phenotype': 0, 'prefix': 'pmg0', 'raceId': 2, 'appearanceRow': 2},
        'workingHeightMeters': 1.9339157, 'heightMeters': 1.9339157 * 10 / 7,
        'models': {part: 'pmg0_' + part + '001' for part in contract.PART_JOINTS},
        'rig': {'revision': 'test-frozen-rig', 'runtimeScale': 10 / 7, 'pilotAccepted': False,
            'positionPolicy': 'bind-relative', 'preserveRotations': True, 'preserveTimingEvents': True,
            'frames': {'working': frames, 'runtime': copy.deepcopy(frames)},
            'privateAliases': {'pmh0': 'pmg0', 'a_ba': 'sr_tmg0_01'}}, 'frozenInputs': {}}


class GraphExpansionTests(unittest.TestCase):
    def setUp(self):
        self.workflow, self.schemas = workflow_fixture()
        self.references = ['guide.png', 'fit.png', 'image-c.png', 'accepted-neighbour.png']

    def expand(self, workflow=None, schemas=None, **overrides):
        args = dict(prompt_text='explicit anatomical prompt', seed=987654321,
                    references=self.references, dimensions=[1536, 1024], prefix='test/thigh')
        args.update(overrides)
        return qwen.expand_graph(self.workflow if workflow is None else workflow,
                                 self.schemas if schemas is None else schemas, **args)

    def test_duplicate_graph_inventories_rejected(self):
        for scope in ('subgraph', 'top-level', 'interface'):
            with self.subTest(scope=scope):
                workflow = copy.deepcopy(self.workflow)
                group = workflow['definitions']['subgraphs'][0]
                rows = group['nodes'] if scope == 'subgraph' else workflow['nodes'] if scope == 'top-level' else group['inputs']
                rows.append(copy.deepcopy(rows[0]))
                with self.assertRaisesRegex(ValueError, 'Duplicate'):
                    self.expand(workflow)

    def test_core_graph_preserved_and_inputs_not_mutated(self):
        before = copy.deepcopy((self.workflow, self.schemas))
        graph = self.expand()
        self.assertEqual((self.workflow, self.schemas), before)
        self.assertEqual(len(graph), 14)
        self.assertEqual(graph['459:451']['inputs'], {'weight_dtype': 'default', 'unet_name': 'unet.safetensors'})
        self.assertEqual(graph['459:453']['inputs'], {'type': 'qwen_image', 'device': 'default', 'clip_name': 'clip.safetensors'})
        self.assertEqual(graph['459:454']['inputs'], {'vae_name': 'vae.safetensors'})
        self.assertEqual(graph['459:480']['inputs'], {'cache_threshold': .2, 'model': ['459:451', 0], 'device': 'auto', 'dtype': 'default'})
        self.assertEqual(graph['459:458']['inputs'], {'denoise': 1.0, 'positive': ['459:452', 0],
            'negative': ['459:452', 1], 'latent_image': ['459:452', 2], 'model': ['459:480', 0],
            'cfg': 1.0, 'steps': 25, 'sampler_name': 'euler', 'scheduler': 'simple', 'seed': 987654321})
        self.assertEqual(graph['459:457']['inputs'], {'vae': ['459:454', 0], 'samples': ['459:458', 0]})
        self.assertEqual(graph['461']['inputs'], {'format': 'png', 'filename_prefix': 'test/thigh',
            'quality': 95, 'save_metadata': True, 'images': ['459:457', 0]})

    def test_named_interface_survives_slot_reordering(self):
        reordered = copy.deepcopy(self.workflow)
        group = reordered['definitions']['subgraphs'][0]
        group['inputs'].reverse()
        for edge in group['links']:
            if edge['origin_id'] == -10:
                edge['origin_slot'] = len(INTERFACE) - 1 - edge['origin_slot']
        self.assertEqual(self.expand(), self.expand(reordered))

    def test_native_reference_conditioning_uses_first_guide_matching_latent(self):
        graph = self.expand()
        encode = graph['459:452']['inputs']
        self.assertEqual(encode['vae'], ['459:454', 0])
        self.assertEqual(encode['resolution'], 0)
        for index, reference in enumerate(self.references, 1):
            self.assertEqual(graph['reference_' + str(index)], {'class_type': 'LoadImage', 'inputs': {'image': reference}})
            self.assertEqual(encode['images.image_' + str(index)], ['reference_' + str(index), 0])
        self.assertEqual(graph['459:458']['inputs']['latent_image'], ['459:452', 2])
        self.assertNotIn('459:456', graph)

    def test_disabled_enhancer_selects_original_prompt_and_prunes_dependencies(self):
        graph = self.expand()
        self.assertEqual(graph['459:474']['inputs'], {'on_false': 'explicit anatomical prompt', 'switch': False})
        self.assertEqual(graph['459:472']['inputs']['source'], ['459:474', 0])
        self.assertEqual(graph['459:452']['inputs']['prompt'], ['459:472', 0])
        for number in (471, 473, 475):
            self.assertNotIn('459:' + str(number), graph)
        self.workflow['nodes'][1]['widgets_values_named']['switch'] = True
        with self.assertRaisesRegex(ValueError, 'enhancer must remain disabled'):
            self.expand()

    def test_reject_native_schema_without_matching_latent_or_image_vae_conditioning(self):
        mutations = [lambda s: s['TextEncodeQwenImage21'].update(output=['CONDITIONING', 'CONDITIONING']),
                     lambda s: s['TextEncodeQwenImage21'].update(output=['CONDITIONING', 'CONDITIONING', 'IMAGE']),
                     lambda s: s['TextEncodeQwenImage21']['input']['required'].pop('images'),
                     lambda s: s['TextEncodeQwenImage21']['input']['optional'].pop('vae')]
        for mutate in mutations:
            schemas = copy.deepcopy(self.schemas); mutate(schemas)
            with self.subTest(mutation=mutate), self.assertRaises(ValueError):
                self.expand(schemas=schemas)

    def test_reject_bad_prompt_seed_dimensions_and_reference_count(self):
        for overrides in [dict(prompt_text='  '), dict(prompt_text=None), dict(seed=-1),
                          dict(seed=2**64), dict(seed=True), dict(seed=1.5),
                          dict(dimensions=[1535, 1024]), dict(dimensions=[0, 1024]),
                          dict(dimensions=[1536, True]), dict(references=[]),
                          dict(references=['x'] * 17)]:
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                self.expand(**overrides)

    def test_reject_missing_or_unknown_schema_and_node(self):
        for kind in ('UNETLoader', 'LoadImage', 'TextEncodeQwenImage21'):
            schemas = copy.deepcopy(self.schemas); schemas.pop(kind)
            with self.subTest(schema=kind), self.assertRaises(ValueError):
                self.expand(schemas=schemas)
        for mode in ('missing', 'unknown', 'bypassed'):
            workflow = copy.deepcopy(self.workflow)
            nodes = workflow['definitions']['subgraphs'][0]['nodes']
            if mode == 'missing': nodes.pop(0)
            elif mode == 'unknown': nodes.append({'id': 999, 'type': 'InventedNode', 'mode': 0})
            else: nodes[0]['mode'] = 2
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                self.expand(workflow)

    def test_reject_missing_link_unresolved_source_unknown_slot_and_destination(self):
        def mutate_missing(group): group['links'].pop(0)
        def mutate_source(group): group['links'][0]['origin_id'] = 999
        def mutate_slot(group): group['links'][0]['origin_slot'] = 999
        def mutate_destination(group): group['links'][0]['target_id'] = 999
        def mutate_interface(group):
            next(x for x in group['links'] if x['origin_id'] == -10)['origin_slot'] = 999
        for mutate in (mutate_missing, mutate_source, mutate_slot, mutate_destination, mutate_interface):
            workflow = copy.deepcopy(self.workflow); mutate(workflow['definitions']['subgraphs'][0])
            with self.subTest(mutation=mutate), self.assertRaises(ValueError): self.expand(workflow)

    def test_reject_duplicate_link_ids(self):
        workflow = copy.deepcopy(self.workflow); group = workflow['definitions']['subgraphs'][0]
        group['links'].append(copy.deepcopy(group['links'][0]))
        with self.assertRaisesRegex(ValueError, 'Duplicate subgraph link ID'):
            self.expand(workflow)

    def test_reject_missing_interface_values_and_altered_image_outputs(self):
        mutations = [lambda w: w['nodes'][1]['widgets_values_named'].pop('unet_name'),
                     lambda w: w['links'][0].__setitem__(1, 999),
                     lambda w: w['definitions']['subgraphs'][0]['links'][-1].__setitem__('origin_id', 452),
                     lambda w: w['nodes'][2]['widgets_values_named'].__setitem__('format', 'jpeg')]
        for mutate in mutations:
            workflow = copy.deepcopy(self.workflow); mutate(workflow)
            with self.subTest(mutation=mutate), self.assertRaises(ValueError): self.expand(workflow)

    def test_actual_frozen_saved_workflow_preserves_core_settings(self):
        frozen = Path(__file__).resolve().parents[2] / 'output/phenotypes/troll-male-purposebuilt-v1/reference-attempts/thigh-qwen-v1'
        if not (frozen / 'workflow-source.json').exists():
            self.skipTest('Actual frozen workflow is an external generation artifact')
        workflow = qwen.read(frozen / 'workflow-source.json'); schemas = qwen.read(frozen / 'object-info.json')
        graph = self.expand(workflow, schemas)
        self.assertEqual(len(graph), 14)
        self.assertEqual(graph['459:458']['inputs']['sampler_name'], 'euler')
        self.assertEqual(graph['459:458']['inputs']['scheduler'], 'simple')
        self.assertEqual(graph['459:458']['inputs']['steps'], 25)
        self.assertEqual(graph['459:451']['inputs']['unet_name'], 'qwen_image_2.1_int8_convrot.safetensors')
        self.assertEqual(graph['459:453']['inputs']['clip_name'], 'qwen3vl_8b_int8_convrot.safetensors')
        self.assertEqual(graph['459:454']['inputs']['vae_name'], 'qwen_image_2.1_vae_bf16.safetensors')
        self.assertEqual(graph['459:452']['inputs']['resolution'], 0)
        self.assertEqual(graph['459:458']['inputs']['latent_image'], ['459:452', 2])
        self.assertEqual(graph['459:474']['inputs']['on_false'], 'explicit anatomical prompt')
        self.assertFalse(any(n['class_type'] == 'TextGenerate' for n in graph.values()))


class PreparationAndDispatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.args = SimpleNamespace(output=self.root)
        self.target = self.root / 'target-contract.json'
        self.target.write_text(json.dumps(target_fixture()), encoding='utf-8')
        self.source = self.root / 'guide.png'; self.source.write_bytes(b'frozen-reference-input')
        self.snapshot = self.root / 'helper-snapshot.py'; self.snapshot.write_bytes(Path(qwen.__file__).read_bytes())
        workflow, schemas = workflow_fixture()
        graph = qwen.expand_graph(workflow, schemas, 'prompt', 42, ['PENDING_REFERENCE_1'], [1536, 1024], 'test')
        qwen.save_json(self.root / 'workflow-api-template.json', graph)
        self.record = {**contract.binding(self.target, contract.load(self.target), 'working'),
            'schemaVersion': 1, 'kind': 'target-qwen-reference-preparation', 'service': 'http://mock.invalid',
            'references': [{**qwen.pin(self.source), 'role': 'camera-guide', 'order': 1}],
            'dimensions': [1536, 1024], 'pins': [qwen.pin(self.source), qwen.pin(self.snapshot),
                qwen.pin(self.root / 'workflow-api-template.json')],
            'referenceAccepted': False, 'geometryAccepted': False, 'clientAccepted': False}
        self.save_preparation()
        self.quiet = contextlib.redirect_stdout(io.StringIO()); self.quiet.__enter__()

    def tearDown(self):
        self.quiet.__exit__(None, None, None); self.tmp.cleanup()

    def save_preparation(self): qwen.save_json(self.root / 'preparation.json', self.record)

    def dispatch_receipt(self, client='our-client', prompt_id=None):
        qwen.save_json(self.root / 'workflow-api.json', {'reference_1': {'class_type': 'LoadImage', 'inputs': {'image': 'server/guide.png'}}})
        receipt = {**contract.binding(self.target, contract.load(self.target), 'working'),
            'schemaVersion': 1, 'kind': 'target-qwen-reference-generation', 'service': 'http://mock.invalid',
            'clientId': client, 'state': 'submission-uncertain',
            'preparationSha256': contract.sha(self.root / 'preparation.json'),
            'apiSha256': contract.sha(self.root / 'workflow-api.json'), 'outputs': [],
            'referenceAccepted': False, 'geometryAccepted': False, 'clientAccepted': False}
        if prompt_id: receipt['promptId'] = prompt_id
        qwen.save_json(self.root / 'generation.json', receipt)
        return receipt

    def test_preparation_checks_pins_current_helper_and_target_binding(self):
        self.assertEqual(qwen.checked_preparation(self.root), self.record)
        self.source.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'Pinned input changed'):
            qwen.checked_preparation(self.root)

    def test_reject_changed_executing_helper_even_if_snapshot_pin_is_updated(self):
        self.snapshot.write_bytes(b'changed executable snapshot')
        self.record['pins'][1] = qwen.pin(self.snapshot); self.save_preparation()
        with self.assertRaisesRegex(ValueError, 'Executing Qwen helper changed'):
            qwen.checked_preparation(self.root)

    def test_reject_stale_rig_or_coordinate_binding(self):
        for key, value in [('rigRevision', 'old-rig'), ('coordinateSpace', 'runtime'), ('targetContractSha256', 'wrong')]:
            record = copy.deepcopy(self.record); record[key] = value
            qwen.save_json(self.root / 'preparation.json', record)
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'another target, rig revision or coordinate space'):
                qwen.checked_preparation(self.root)

    def test_existing_dispatch_guard_runs_before_preparation_or_any_network(self):
        (self.root / 'generation.json').write_bytes(b'even-an-unreadable-receipt-blocks')
        with patch.object(qwen, 'checked_preparation') as check, patch.object(qwen, 'Comfy') as network:
            with self.assertRaisesRegex(ValueError, 'never resubmit'): qwen.submit(self.args)
            check.assert_not_called(); network.assert_not_called()

    def test_occupied_queue_blocks_upload_and_post(self):
        service = MagicMock(); service.request.return_value = {'queue_running': [[1, 'other-job']], 'queue_pending': []}
        with patch.object(qwen, 'Comfy', return_value=service):
            with self.assertRaisesRegex(ValueError, 'occupied'): qwen.submit(self.args)
        service.upload.assert_not_called()
        self.assertEqual([c.args[0] for c in service.request.call_args_list], ['/queue'])
        self.assertFalse((self.root / 'generation.json').exists())

    def submit_service(self, response=None, timeout=False):
        service = MagicMock(); service.upload.return_value = 'unique-client/guide.png'
        def request(route, payload=None):
            if route == '/queue': return {'queue_running': [], 'queue_pending': []}
            self.assertEqual(route, '/prompt')
            before_post = qwen.read(self.root / 'generation.json')
            self.assertEqual(before_post['state'], 'submission-uncertain')
            self.assertEqual(before_post['clientId'], payload['client_id'])
            self.assertEqual(before_post['preparationSha256'], contract.sha(self.root / 'preparation.json'))
            self.assertEqual(before_post['apiSha256'], contract.sha(self.root / 'workflow-api.json'))
            self.assertEqual(payload['prompt']['reference_1']['inputs']['image'], service.upload.return_value)
            self.assertEqual(payload['extra_data']['extra_pnginfo']['srn_preparation_sha256'], before_post['preparationSha256'])
            if timeout: raise TimeoutError('POST outcome unknown')
            return response
        service.request.side_effect = request
        return service

    def test_timeout_receipt_precedes_post_and_prevents_second_submission(self):
        service = self.submit_service(timeout=True)
        with patch.object(qwen, 'Comfy', return_value=service):
            with self.assertRaisesRegex(TimeoutError, 'outcome unknown'): qwen.submit(self.args)
        receipt = qwen.read(self.root / 'generation.json')
        self.assertEqual(receipt['state'], 'submission-uncertain'); self.assertNotIn('promptId', receipt)
        self.assertFalse(receipt['referenceAccepted']); self.assertFalse(receipt['geometryAccepted']); self.assertFalse(receipt['clientAccepted'])
        frozen_receipt_bytes = (self.root / 'generation.json').read_bytes()
        with patch.object(qwen, 'checked_preparation') as check, patch.object(qwen, 'Comfy') as network:
            with self.assertRaisesRegex(ValueError, 'never resubmit'): qwen.submit(self.args)
            check.assert_not_called(); network.assert_not_called()
        self.assertEqual([c.args[0] for c in service.request.call_args_list].count('/prompt'), 1)
        self.assertEqual((self.root / 'generation.json').read_bytes(), frozen_receipt_bytes)

    def test_dispatch_success_and_rejection_remain_once_only(self):
        service = self.submit_service(response={'prompt_id': 'submitted-id', 'node_errors': {}})
        with patch.object(qwen, 'Comfy', return_value=service): qwen.submit(self.args)
        receipt = qwen.read(self.root / 'generation.json')
        self.assertEqual(receipt['state'], 'submitted'); self.assertEqual(receipt['promptId'], 'submitted-id')
        self.assertEqual(service.upload.call_args.args[1], receipt['clientId'])
        self.assertEqual(len(qwen.read(self.root / 'uploads.json')), 1)
        with patch.object(qwen, 'Comfy') as network:
            with self.assertRaisesRegex(ValueError, 'never resubmit'): qwen.submit(self.args)
            network.assert_not_called()

    def test_dispatch_node_errors_preserve_uncertain_receipt_for_inspection(self):
        service = self.submit_service(response={'node_errors': {'459:452': {'error': 'invalid input'}}})
        with patch.object(qwen, 'Comfy', return_value=service):
            with self.assertRaisesRegex(ValueError, 'dispatch rejected'): qwen.submit(self.args)
        self.assertEqual(qwen.read(self.root / 'generation.json')['state'], 'submission-uncertain')
        self.assertTrue((self.root / 'dispatch-response.json').exists())
        with patch.object(qwen, 'Comfy') as network:
            with self.assertRaisesRegex(ValueError, 'never resubmit'): qwen.submit(self.args)
            network.assert_not_called()

    def test_status_recovers_by_client_identity_without_post_or_upload(self):
        self.dispatch_receipt()
        queue = {'queue_running': [], 'queue_pending': [[2, 'recovered-id', {}, {'client_id': 'our-client'}]]}
        service = MagicMock()
        service.request.side_effect = [queue, {}, {}, queue]
        with patch.object(qwen, 'Comfy', return_value=service), patch.object(qwen.urllib.request, 'urlopen') as download:
            qwen.status(self.args); download.assert_not_called()
        self.assertEqual(qwen.read(self.root / 'generation.json')['promptId'], 'recovered-id')
        self.assertEqual(len(list(self.root.glob('recovery-*.json'))), 1)
        self.assertEqual([c.args[0] for c in service.request.call_args_list], ['/queue', '/history', '/history/recovered-id', '/queue'])
        service.upload.assert_not_called()

    def test_status_no_client_match_retains_uncertainty_and_never_resubmits(self):
        original = self.dispatch_receipt()
        queue = {'queue_running': [[1, 'other-id', {}, {'client_id': 'other-client'}]], 'queue_pending': []}
        service = MagicMock(); service.request.side_effect = [queue, {}]
        with patch.object(qwen, 'Comfy', return_value=service):
            with self.assertRaisesRegex(ValueError, 'do not resubmit'): qwen.status(self.args)
        self.assertEqual(qwen.read(self.root / 'generation.json'), original)
        self.assertEqual([c.args[0] for c in service.request.call_args_list], ['/queue', '/history'])
        service.upload.assert_not_called()

    def test_status_dispatch_artifact_mutation_blocks_network(self):
        self.dispatch_receipt(prompt_id='id'); (self.root / 'workflow-api.json').write_text('{}')
        with patch.object(qwen, 'Comfy') as network:
            with self.assertRaisesRegex(ValueError, 'Dispatch artifacts changed'): qwen.status(self.args)
            network.assert_not_called()


class ClientIdentityRecoveryTests(unittest.TestCase):
    def row(self, prompt_id, client='our-client'):
        return [0, prompt_id, {'graph': 'identical'}, {'client_id': client}, ['461']]

    def test_queue_and_history_recovery_and_duplicate_observation(self):
        receipt = {'clientId': 'our-client'}
        queue = {'queue_running': [self.row('id')], 'queue_pending': [self.row('id')]}
        history = {'id': {'prompt': self.row('id')}}
        self.assertEqual(qwen.recover_prompt_id(receipt, queue, history), 'id')
        self.assertEqual(qwen.recover_prompt_id(receipt, {}, history), 'id')
        self.assertEqual(qwen.recover_prompt_id(receipt, queue, {}), 'id')

    def test_never_match_prompt_content_or_different_client(self):
        queue = {'queue_running': [self.row('other', 'other-client')], 'queue_pending': []}
        history = {'same-graph-other': {'prompt': self.row('same-graph-other', 'other-client')}}
        self.assertIsNone(qwen.recover_prompt_id({'clientId': 'our-client'}, queue, history))

    def test_multiple_matching_prompt_ids_are_ambiguous_and_rejected(self):
        queue = {'queue_pending': [self.row('id-a')]}
        history = {'id-b': {'prompt': self.row('id-b')}}
        with self.assertRaisesRegex(ValueError, 'Multiple prompts share dispatch client identity'):
            qwen.recover_prompt_id({'clientId': 'our-client'}, queue, history)


if __name__ == '__main__': unittest.main()


