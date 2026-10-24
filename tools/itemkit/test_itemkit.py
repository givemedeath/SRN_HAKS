"""Item contract, geometry, native naming and stale-lineage regression tests."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.headkit.common import digest, pin, read, write
from tools.itemkit import contracts
from tools.itemkit.__main__ import intake, consumed_inputs, consumed_pins
from tools.itemkit.generation import generation_manifest, shared_ledger, initialize_trial
from tools.itemkit.geometry import similarity_matrix, transform, topology, segment_hits, protected_checks, check_budgets, hidden_cap_faces
from tools.itemkit.fixture import blueprint, validate_evidence, CHECKS
from tools.itemkit.native import ascii_model
from tools.itemkit.runner import Runner,blender_environment


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        source = self.root/'reference.png'; Image.new('RGB', (512, 512), 'gray').save(source)
        intake(source, self.root/'asset'); self.path = self.root/'asset'/'asset.json'
        self.data = read(self.path); self.data['approval']['referenceDesignReviewed'] = True; write(self.path, self.data)
        self.profile_path = self.path.parent/'family.json'; self.profile = read(self.profile_path)
        self.local = self.root/'bindings.json'; write(self.local, {'schemaVersion': 1, 'toolsRoot': str(self.root)})
    def tearDown(self): self.temp.cleanup()
    def save_profile(self):
        write(self.profile_path, self.profile); self.data['familyProfile']['sha256'] = pin(self.profile_path)['sha256']; write(self.path, self.data)
    def native(self):
        self.profile['nativePackaging'] = 'enabled'
        stack_dir = self.path.parent/'stack'; stack_dir.mkdir()
        layer = stack_dir/'base'; layer.mkdir()
        table = layer/'baseitems.2da'; table.write_text('2DA V2.0\n\nLabel ItemClass ModelType\n0 shortsword WSwSs 2\n')
        names = ['baseitems.2da', 'wswss_b_011.mdl', 'wswss_m_011.mdl', 'wswss_t_011.mdl']
        for name in names[1:]: (layer/name).write_bytes(b'fixture donor bytes')
        stack = stack_dir/'stack.json'
        rows = [{'resource': n, 'file': {'path': 'base/'+n, 'sha256': pin(layer/n)['sha256']}} for n in names]
        write(stack, {'complete': True, 'order': 'low-to-high', 'layers': [{'resources': rows}]})
        self.profile['native'] = {'reviewed': True, 'stack': {'path': 'stack/stack.json', 'sha256': pin(stack)['sha256']},
            'baseItem': 0, 'baseitemsSha256': pin(table)['sha256'], 'itemClass': 'wswss', 'modelType': 2,
            'donors': dict(zip(contracts.PARTS, names[1:])), 'frame': np.eye(3).tolist(), 'gripOrigin': [0, 0, 0], 'gripLength': .12}
        self.save_profile(); return contracts.native_contract(self.profile_path, self.profile)


class ContractTests(Fixture):
    def test_consumed_pins_preserve_scope_without_repinning_dependencies(self):
        dependency=self.root/'dependency';dependency.write_bytes(b'bound bytes');expected=pin(dependency)
        with patch('tools.itemkit.__main__.bindings',return_value={}), \
             patch('tools.itemkit.__main__.python_package_pins',return_value=[]), \
             patch('tools.itemkit.__main__.all_pins',return_value=[expected,expected]), \
             patch('tools.itemkit.__main__.code_pins',return_value=[]), \
             patch('tools.itemkit.__main__.pin',wraps=pin) as repin:
            rows=consumed_pins(self.path,self.local,stage='donor')
            self.assertEqual(rows,[pin(self.local),expected] if str(self.local)<str(dependency) else [expected,pin(self.local)])
            self.assertEqual([args.args[0] for args in repin.call_args_list],[self.local])
            self.assertEqual([row['path'] for row in rows],consumed_inputs(self.path,self.local,stage='donor'))
    def test_resume_inputs_skip_superseded_attempts_and_keep_current_ancestors(self):
        run=self.root/'run';run.mkdir();receipts={}
        for stage in ('fit','reduce'):
            consumed=self.root/(stage+'-input');consumed.write_bytes(b'original '+stage.encode())
            output=self.root/(stage+'-output');output.write_bytes(b'output')
            write(run/(stage+'.json'),{'inputs':[pin(consumed)],'outputs':[pin(output)],'dependencies':{}});receipts[stage]=pin(run/(stage+'.json'))
        write(run/'state.json',{'stages':receipts,'reviews':{}})
        (self.root/'reduce-input').write_bytes(b'corrected helper')
        with patch('tools.itemkit.__main__.bindings',return_value={}), \
             patch('tools.itemkit.__main__.python_package_pins',return_value=[]), \
             patch('tools.itemkit.__main__.all_pins',return_value=[]), \
             patch('tools.itemkit.__main__.code_pins',return_value=[]):
            paths=consumed_inputs(self.path,self.local,run=run,stage='reduce')
            fit,reduce=(pin(self.root/(stage+'-input'))['path'] for stage in ('fit','reduce'))
            self.assertIn(fit,paths);self.assertNotIn(reduce,paths)
            self.assertNotIn(reduce,consumed_inputs(self.path,self.local,run=run))
    def test_consumed_pins_reject_conflicts_before_deduplication(self):
        dependency=self.root/'dependency';dependency.write_bytes(b'bound bytes');expected=pin(dependency)
        with patch('tools.itemkit.__main__.bindings',return_value={}), \
             patch('tools.itemkit.__main__.python_package_pins',return_value=[]), \
             patch('tools.itemkit.__main__.all_pins',return_value=[expected,{**expected,'sha256':'0'*64}]), \
             patch('tools.itemkit.__main__.code_pins',return_value=[]):
            with self.assertRaisesRegex(ValueError,'Stale file pin'):consumed_pins(self.path,self.local,stage='donor')
    def test_consumed_pins_recheck_changed_bytes_on_next_pass(self):
        dependency=self.root/'dependency';dependency.write_bytes(b'bound bytes');expected=pin(dependency)
        with patch('tools.itemkit.__main__.bindings',return_value={}), \
             patch('tools.itemkit.__main__.python_package_pins',return_value=[]), \
             patch('tools.itemkit.__main__.all_pins',return_value=[expected]), \
             patch('tools.itemkit.__main__.code_pins',return_value=[]):
            consumed_pins(self.path,self.local,stage='donor');dependency.write_bytes(b'changed bytes')
            with self.assertRaisesRegex(ValueError,'Stale file pin'):consumed_pins(self.path,self.local,stage='donor')
    def test_cpu_input_scope_omits_unused_generation_environment(self):
        unused={'path':str(self.root/'missing-generation-weight'),'sha256':'0'*64}
        local={'models':{'unused':unused},'comfySources':[unused],'comfyCustomNodes':str(self.root/'missing-adapter')}
        with patch('tools.itemkit.__main__.bindings',return_value=local), \
             patch('tools.itemkit.__main__.python_package_pins',return_value=[]), \
             patch('tools.itemkit.__main__.all_pins',return_value=[]), \
             patch('tools.itemkit.__main__.code_pins',return_value=[]):
            paths=consumed_inputs(self.path,self.local,stage='donor')
        self.assertNotIn(unused['path'],paths)
    def test_blender_child_does_not_inherit_the_cli_python_abi_bank(self):
        bank=str(self.root/'python312');other=str(self.root/'blender-packages')
        original={'PYTHONPATH':os.pathsep.join([bank,other,str(self.root)]),'UNCHANGED':'yes'}
        result=blender_environment({'pythonPackages':{'directory':bank}},original)
        self.assertEqual(result['PYTHONPATH'],os.pathsep.join([other,str(self.root)]))
        self.assertEqual(result['UNCHANGED'],'yes');self.assertIn(bank,original['PYTHONPATH'])
    def test_calibration_client_scope_binds_configuration_without_reading_server_weights(self):
        moge=self.root/'moge.safetensors';moge.write_bytes(b'moge')
        unet=self.root/'unet.safetensors';unet.write_bytes(b'unused generation model')
        background=self.root/'birefnet.safetensors';background.write_bytes(b'background model')
        local={'models':{'moge_2_vitl_normal_fp16.safetensors':pin(moge),
                         'birefnet.safetensors':pin(background),
                         'pixal3d_int8_convrot.safetensors':pin(unet)}}
        with patch('tools.itemkit.__main__.bindings',return_value=local), \
             patch('tools.itemkit.__main__.python_package_pins',return_value=[]), \
             patch('tools.itemkit.__main__.all_pins',return_value=[]), \
             patch('tools.itemkit.__main__.code_pins',return_value=[]):
            paths=consumed_inputs(self.path,self.local,stage='calibrate')
        self.assertIn(str(self.local.resolve()),paths)
        self.assertNotIn(str(moge.resolve()),paths)
        self.assertNotIn(str(background.resolve()),paths)
        self.assertNotIn(str(unet.resolve()),paths)
    def test_trial_initialization_never_overwrites_history(self):
        path=self.root/'trial.json';initialize_trial(path,'trial','User authorized five attempts per model')
        self.assertEqual(read(path)['itemTrial']['maximumGeometryAttempts'],5)
        with self.assertRaises(FileExistsError):initialize_trial(path,'replacement','Do not reset')
    def test_review_requires_measured_reference_landmarks(self):
        self.data['approval']['inputReviewComplete'] = True; write(self.path, self.data)
        with self.assertRaisesRegex(ValueError, 'four distinct'): contracts.manifest(self.path)
    def test_frozen_generation_settings_cannot_drift(self):
        self.data['generationSettings']['shapeCFG'] = 7.5; write(self.path, self.data)
        with self.assertRaisesRegex(ValueError, 'frozen preset'): contracts.manifest(self.path)
    def test_item_generation_uses_its_own_output_namespace(self):
        from tools.headkit.comfy import compile_graph
        graph = compile_graph('geometry', 'pixal-single-v1', {'geometry': 'itemkit/input.png'},
                              'itemkit/job', fov=40)
        prefixes = [n['inputs']['filename_prefix'] for n in graph.values() if 'filename_prefix' in n['inputs']]
        self.assertTrue(prefixes and all(p.startswith('itemkit/job/') for p in prefixes))
        for prefix in ('other/job', 'itemkit/../escape', 'itemkit/..\\escape'):
            with self.assertRaisesRegex(ValueError, 'Isolated'):
                compile_graph('geometry', 'pixal-single-v1', {'geometry': 'input.png'}, prefix, fov=40)
    def test_single_reference_has_no_clay_pair_requirement(self):
        data = generation_manifest(self.path)
        self.assertEqual(data['inputs']['geometry'], data['inputs']['detail'])
        self.assertEqual(data['inputs']['detail'], data['inputs']['reference'])
        self.assertNotIn('clay', data['inputs'])
    def test_intake_preserves_reference_bytes(self):
        self.assertEqual((self.root/'reference.png').read_bytes(), (self.path.parent/'intake/reference-original.png').read_bytes())
    def test_changed_reference_rejected(self):
        (self.path.parent/'intake/reference-original.png').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'Stale'): contracts.manifest(self.path)
    def test_different_geometry_and_appearance_rejected(self):
        self.data['inputs']['geometry'] = self.data['inputs']['reference']; self.data['inputs']['detail'] = self.data['familyProfile']
        write(self.path, self.data)
        with self.assertRaisesRegex(ValueError, 'same normalized'): contracts.manifest(self.path)
    def test_model_index_and_colour_encode_native_resrefs(self):
        native, resources = self.native()
        self.assertEqual(contracts.reserve(self.profile, resources)['models']['t'], 'wswss_t_021')
        names = contracts.model_names(self.profile, 25, 5); self.assertEqual(names['b'], 'wswss_b_255')
        with self.assertRaisesRegex(ValueError, 'UTI byte'): contracts.model_names(self.profile, 25, 6)
    def test_collision_is_case_insensitive(self):
        _, resources = self.native(); resources['WSWSS_T_021.MDL'] = {}
        self.assertEqual(contracts.reserve(self.profile, resources)['modelIndex'], 3)
        with self.assertRaisesRegex(ValueError, 'collision-free'): contracts.reserve(self.profile, resources, 1)
    def test_complete_effective_stack_required(self):
        self.native(); self.profile['native']['baseitemsSha256'] = '0'*64
        with self.assertRaisesRegex(ValueError, 'baseitems'): contracts.native_contract(self.profile_path, self.profile)
    def test_native_family_cannot_silently_change_model_type(self):
        self.native(); self.profile['native']['modelType'] = 0
        with self.assertRaisesRegex(ValueError, 'effective baseitems'): contracts.native_contract(self.profile_path, self.profile)
    def test_upper_stack_layer_controls_contract(self):
        self.native(); stack = self.path.parent/'stack/stack.json'; document = read(stack)
        override = stack.parent/'base/override.2da'; override.write_text('2DA V2.0\n\nLabel ItemClass ModelType\n0 shortsword other 2\n')
        document['layers'].append({'resources': [{'resource': 'baseitems.2da', 'file': {'path': 'base/override.2da', 'sha256': pin(override)['sha256']}}]})
        write(stack, document); self.profile['native']['stack']['sha256'] = pin(stack)['sha256']
        self.profile['native']['baseitemsSha256'] = pin(override)['sha256']
        with self.assertRaisesRegex(ValueError, 'effective baseitems'): contracts.native_contract(self.profile_path, self.profile)
    def test_single_declared_assembly_only(self):
        self.assertEqual(len(contracts.family(self.profile_path)['allowedAssemblies']), 1)
        self.profile['allowedAssemblies'] *= 2; self.save_profile()
        with self.assertRaisesRegex(ValueError, 'Duplicate'): contracts.family(self.profile_path)
    def test_part_limits_cannot_exceed_whole_budget(self):
        self.profile['budgets']['parts']['b']['visible'] += 1; self.save_profile()
        with self.assertRaisesRegex(ValueError, 'assembly budget'): contracts.family(self.profile_path)
    def test_firearm_native_export_blocked(self):
        data = read(Path(__file__).parent/'profiles/firearm-sling.json')
        with self.assertRaisesRegex(ValueError, 'blocked'): contracts.model_names(data, 1)
        data['nativePackaging'] = 'enabled'; write(self.profile_path, data)
        with self.assertRaisesRegex(ValueError, 'deferred'): contracts.family(self.profile_path)
    def test_shared_ledger_cannot_be_replaced_by_per_asset_ledger(self):
        ledger = self.root/'shared-ledger.json'; ledger.write_text('{}')
        local = {'submissionLedger': str(ledger)}
        self.assertEqual(shared_ledger(local), ledger.resolve())
        with self.assertRaisesRegex(ValueError, 'bound shared'): shared_ledger(local, self.root/'other.json')
    def test_blueprint_uses_encoded_appearance_byte(self):
        result = blueprint(0, {'modelIndex': 7, 'colourIndex': 3})
        self.assertEqual([result['ModelPart'+str(i)]['value'] for i in (1, 2, 3)], [73]*3)
        self.assertNotIn('Cloth1Color', result)


class GeometryTests(unittest.TestCase):
    def tetra(self):
        return np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1.]], float), np.array([[0, 2, 1], [0, 1, 3], [0, 3, 2], [1, 2, 3]])
    def test_uniform_fit_applies_identically_to_donor_and_target(self):
        matrix = np.eye(4); matrix[:3, :3] *= .12; matrix[:3, 3] = [0, -.1, .2]
        actual = similarity_matrix({'reviewed': True, 'sourceSha256': 'hash', 'matrix': matrix.tolist()}, 'hash')
        v, _ = self.tetra(); self.assertTrue(np.array_equal(transform(v, actual), v*.12+[0, -.1, .2]))
    def test_nonuniform_and_reflected_fits_rejected(self):
        for diagonal in ([1, 2, 1, 1], [-1, 1, 1, 1]):
            with self.assertRaisesRegex(ValueError, 'uniform similarity'):
                similarity_matrix({'reviewed': True, 'sourceSha256': 'hash', 'matrix': np.diag(diagonal)}, 'hash')
    def test_fit_cannot_reuse_other_donor(self):
        with self.assertRaisesRegex(ValueError, 'exact textured donor'):
            similarity_matrix({'reviewed': True, 'sourceSha256': 'old', 'matrix': np.eye(4)}, 'new')
    def test_shadow_requires_closed_outward_winding(self):
        v, f = self.tetra(); self.assertTrue(topology(v, f)['closedWound'])
        self.assertFalse(topology(v, f[:, ::-1])['closedWound']); self.assertFalse(topology(v, f[:-1])['closedWound'])
    def test_vertex_only_shell_contact_is_not_manifold(self):
        v,f=self.tetra(); vertices=np.vstack((v,-v))
        faces=np.vstack((f,(f+4)[:,::-1]))
        report=topology(vertices,faces)
        self.assertEqual(report['boundaryEdges'],0); self.assertEqual(report['nonmanifoldEdges'],0)
        self.assertEqual(report['invalidVertexLinks'],1); self.assertFalse(report['closedWound'])
    def test_opening_probe_detects_inserted_cap(self):
        v = np.array([[-1, -1, 0], [1, -1, 0], [0, 1, 0]])
        f = np.array([[0, 1, 2]])
        self.assertEqual(segment_hits(v, f, [2, 0, -1], [2, 0, 1]), 0)
        with self.assertRaisesRegex(ValueError, 'obstructed'):
            protected_checks(v, f, {'openingProbes': [{'name': 'loop', 'start': [0, 0, -1], 'end': [0, 0, 1]}]})
    def test_thin_blade_sample_cannot_collapse(self):
        v, f = self.tetra()
        cfg = {'thicknessProbes': [{'name': 'edge', 'points': [[0, 0, 0], [0, 0, 1]], 'minimum': .5, 'maximumSampleError': .1}]}
        protected_checks(v, f, cfg); v[3] = [0, 0, .01]
        with self.assertRaisesRegex(ValueError, 'thickness'): protected_checks(v, f, cfg)
    def test_caps_and_hardware_count_against_assembly(self):
        profile = read(Path(__file__).parent/'profiles/cougar-shortsword.json')
        counts = {part: row['visible'] for part, row in profile['budgets']['parts'].items()}
        check_budgets(counts, profile['budgets'], 'visible')
        counts['b'] += 1
        with self.assertRaisesRegex(ValueError, 'budget'): check_budgets(counts, profile['budgets'], 'visible')
    def test_thickness_sampling_uses_surface_not_reduction_vertex_density(self):
        vertices = np.array([[0,0,0],[1,0,0],[0,1,0],[0,0,.01],[1,0,.01],[0,1,.01]])
        faces = np.array([[0,1,2],[3,4,5]])
        result = protected_checks(vertices, faces, {'thicknessProbes': [{'name':'slab',
            'points': [[.25,.25,0],[.25,.25,.01]], 'minimum':.009,'maximumSampleError':1e-5}]})
        self.assertAlmostEqual(result['thickness'][0]['distance'], .01)
    def test_hidden_caps_require_all_corners_on_the_measured_join_plane(self):
        vertices=np.array([[0,0,0],[1,0,0],[0,0,1],[0,.01,1]])
        np.testing.assert_array_equal(hidden_cap_faces(vertices,np.array([[0,1,2],[0,1,3]]),[0,2]),[True,False])
    def test_cap_fan_preserves_collinear_rim_and_area(self):
        from .geometry import cap_fan_center
        rim=np.array([[0,0,0],[1,0,0],[2,0,0],[2,0,1],[0,0,1]],float)
        for points in (rim,rim[::-1]):
            center=cap_fan_center(points)
            self.assertIsNotNone(center)
            areas=np.linalg.norm(np.cross(points-center,np.roll(points,-1,axis=0)-center),axis=1)*.5
            self.assertTrue(np.all(areas>0));self.assertAlmostEqual(areas.sum(),2.)
    def test_cap_fan_rejects_outside_center_nonplanar_and_tiny_edges(self):
        from .geometry import cap_fan_center
        # U-shaped polygon's mean lies outside its interior kernel.
        points=np.array([[0,0,0],[3,0,0],[3,0,3],[2,0,3],[2,0,1],[1,0,1],[1,0,3],[0,0,3]],float)
        self.assertIsNone(cap_fan_center(points))
        square=np.array([[0,0,0],[1,0,0],[1,0,1],[0,0,1]],float)
        square[0,1]=.1;self.assertIsNone(cap_fan_center(square))
        square[0,1]=0;self.assertIsNone(cap_fan_center(np.insert(square,1,square[0],axis=0)))
    def test_uv_domain_gutter_rejects_close_unrelated_or_relocated_regions(self):
        from .atlas import region_gutters
        owners=np.full((16,16),-1,np.int32);owners[5:8,4:6]=0;owners[5:8,8:10]=1
        self.assertEqual(region_gutters(owners,np.array([0,0]))['nearbyChartPixelsByRadius']['2'],0)
        self.assertGreater(region_gutters(owners,np.array([0,1]))['nearbyChartPixelsByRadius']['2'],0)
        owners[:,8:10]=-1;owners[5:8,12:14]=1
        self.assertEqual(region_gutters(owners,np.array([0,1]))['nearbyChartPixelsByRadius']['2'],0)
    def test_donor_sampling_filters_linear_colour_and_respects_front_mask(self):
        from .transfer import sample_image,finished_colour,linear_rgb
        pixels=np.array([[[0.,0.,0.],[1.,1.,1.]]])
        np.testing.assert_allclose(sample_image(pixels,[[.5,.5]],decode_srgb=True),[[.5,.5,.5]])
        reference=np.full((4,4,3),.5)
        settings={'nativeY':[-1,1],'nativeZ':[-1,1],'frontPixelQuad':[[0,0],[4,0],[4,4],[0,4]],'backPixelStrip':[[0,0],[4,0],[4,4],[0,4]],'backRepeat':1}
        result=finished_colour(np.zeros((2,2,3)),np.array([[.5,.5],[.5,.5]]),np.zeros((2,3)),np.array([[1,0,0],[0,0,1]]),reference,settings)
        np.testing.assert_allclose(result[0],linear_rgb([.5,.5,.5]));np.testing.assert_array_equal(result[1],[0,0,0])
    def test_texture_patch_rejects_changed_geometry_and_overbroad_scope(self):
        import hashlib
        from .transfer import validate_texture_patch
        v,f=self.tetra();corners=np.tile(v[f],(10,1,1)).astype('<f8')
        patch={'reviewed':True,'notes':'Measured synthetic patch','targetCornerHash':hashlib.sha256(corners.tobytes()).hexdigest(),'maximumDistance':.0021,'maximumTextureFraction':.0001,'faces':[0]}
        self.assertEqual(validate_texture_patch(corners,patch),{0})
        changed=corners.copy();changed[0,0,0]+=.0001
        with self.assertRaisesRegex(ValueError,'different target'):validate_texture_patch(changed,patch)
        for changes in ({'maximumDistance':.003},{'maximumTextureFraction':.01},{'faces':[0,1]},{'faces':[0,0]}):
            with self.assertRaises(ValueError):validate_texture_patch(corners,{**patch,**changes})
        qualified={**patch,'maximumDistance':.00293}
        self.assertEqual(validate_texture_patch(corners,qualified,maximum_distance=.00293),{0})
        for bound in (.00292,.0031,0,float('nan')):
            with self.assertRaises(ValueError):validate_texture_patch(corners,qualified,maximum_distance=bound)
        with self.assertRaisesRegex(ValueError,'different target'):
            validate_texture_patch(changed,qualified,maximum_distance=.00293)
    def test_colour_range_normalization_is_bounded_and_recorded(self):
        from .textures import normalize_source_colour
        values=np.array([[-1e-6,1.0000068,.5]],np.float32);normalized,report=normalize_source_colour(values)
        np.testing.assert_array_equal(normalized,[[0,1,.5]]);self.assertEqual(report['clippedValuesByChannel'],[1,1,0])
        for bad in (np.array([[0.,1.001,.5]]),np.array([[0.,np.nan,.5]])):
            with self.assertRaises(ValueError):normalize_source_colour(bad)
    def test_shadow_loop_is_closed_within_budget_and_preserves_through_opening(self):
        from .geometry import loop_shadow_proxy
        vertices=[];faces=[]
        for i in range(8):
            theta=i*np.pi/4
            for j in range(4):
                phi=j*np.pi/2;radius=2+.2*np.cos(phi)
                vertices.append([.2*np.sin(phi),radius*np.cos(theta),radius*np.sin(theta)])
                a=i*4+j;b=((i+1)%8)*4+j;c=((i+1)%8)*4+(j+1)%4;d=i*4+(j+1)%4
                faces.extend([[a,b,c],[a,c,d]])
        probe={'name':'loop','start':[-1,0,0],'end':[1,0,0]}
        p,f,report=loop_shadow_proxy(np.array(vertices),np.array(faces),probe)
        self.assertLessEqual(len(f),100);self.assertTrue(topology(p,f)['closedWound'])
        self.assertEqual(protected_checks(p,f,{'openingProbes':[probe]})['openings'][0]['hits'],0)
        np.testing.assert_allclose(np.ptp(p[:,1:],axis=0),[4.4,4.4])
        angle=.53;rotation=np.array([[np.cos(angle),-np.sin(angle),0],[np.sin(angle),np.cos(angle),0],[0,0,1]])
        offset=np.array([.2,-.1,.4]);tilted=np.array(vertices)@rotation.T+offset
        tilted_probe={**probe,'start':(rotation@np.array(probe['start'])+offset).tolist(),
                      'end':(rotation@np.array(probe['end'])+offset).tolist()}
        q,g,oblique=loop_shadow_proxy(tilted,np.array(faces),tilted_probe)
        np.testing.assert_array_equal(g,f);np.testing.assert_allclose(q,p@rotation.T+offset,atol=1e-12)
        self.assertTrue(topology(q,g)['closedWound']);self.assertIn('axisFrame',oblique)
        self.assertEqual(protected_checks(q,g,{'openingProbes':[tilted_probe]})['openings'][0]['hits'],0)
        for bad in ({'start':[0,0,0],'end':[0,0,0]},{'start':[0,0,0],'end':[float('nan'),0,0]}):
            with self.assertRaises(ValueError):loop_shadow_proxy(tilted,np.array(faces),bad)
    def test_camera_basis_keeps_native_blade_vertical_in_inventory(self):
        from .geometry import camera_basis
        basis=camera_basis([1,0,0],[0,0,0],[0,1,0])
        np.testing.assert_allclose(basis[:,1],[0,1,0]);np.testing.assert_allclose(-basis[:,2],[-1,0,0])
        for axis in np.eye(3):
            basis=camera_basis(axis,np.zeros(3),axis)
            np.testing.assert_allclose(basis.T@basis,np.eye(3),atol=1e-12);self.assertAlmostEqual(np.linalg.det(basis),1)
    def test_reverse_weave_is_dark_bounded_and_has_no_tiling_seam(self):
        from .transfer import finished_colour
        count=100;positions=np.zeros((count,3));positions[:,1]=np.linspace(-.9,.9,count);positions[:,2]=.2
        settings={'nativeY':[-1,1],'nativeZ':[-1,1],'frontPixelQuad':[[0,0],[4,0],[4,4],[0,4]],'backPattern':'carbon-weave','backFrequency':[40,12],'backBaseLinear':.015,'backAmplitudeLinear':.0025}
        result=finished_colour(np.zeros((2,2,3)),np.full((count,2),.5),positions,np.tile([-1.,0,0],(count,1)),np.ones((4,4,3)),settings)
        self.assertGreaterEqual(result.min(),.0125-1e-12);self.assertLessEqual(result.max(),.0175+1e-12)
    def test_export_separates_visible_and_shadow_nodes(self):
        v, f = self.tetra(); p = v[f]; n = np.cross(p[:, 1]-p[:, 0], p[:, 2]-p[:, 0]); n /= np.linalg.norm(n, axis=1)[:, None]
        text = ascii_model('wswss_t_021', 'sr_cfl_02', p, np.repeat(n[:, None, :], 3, axis=1), np.zeros((4, 3, 2)), v, f)
        self.assertIn('classification ITEM', text); self.assertIn('  render 1\n  shadow 0', text)
        self.assertIn('  render 0\n  shadow 1', text)


class ReceiptTests(Fixture):
    def setUp(self):
        super().setUp()
        self.runtime = {'toolchain': pin(self.local), 'migrationReceipt': pin(self.local), 'python': pin(sys.executable)}
        self.patches = [patch('tools.itemkit.runner.python_package_pins', return_value=[]),
                        patch('tools.itemkit.runner.code_pins', return_value=[]),
                        patch('tools.itemkit.runner.source_version', return_value='fixture-version')]
        for item in self.patches: item.start(); self.addCleanup(item.stop)
        self.runner = Runner(self.path, self.local, self.root/'run', runtime=self.runtime)
    def test_unreviewed_stage_cannot_feed_dependents(self):
        self.runner.execute('prepare')
        with self.assertRaisesRegex(ValueError, 'Review pending'): self.runner.result('prepare')
        self.runner.review('prepare', 'approved', 'Inspected the original reference')
        self.runner.result('prepare')
    def test_changed_output_invalidates_resume(self):
        result = self.runner.execute('prepare')['result']
        self.runner.review('prepare', 'approved', 'Viewed reference')
        Path(result['reference']['path']).write_bytes(b'altered')
        with self.assertRaisesRegex(ValueError, 'Stale'): self.runner.result('prepare')
    def test_rejected_dependency_invalidates_existing_descendant(self):
        def compute(stage, folder, **kwargs):
            file = folder/'output.txt'; file.write_text(stage); return {'artifact': pin(file)}
        with patch.object(self.runner, '_execute', side_effect=compute):
            self.runner.execute('fit'); self.runner.review('fit', 'approved', 'Reviewed fit')
            self.runner.execute('reduce'); self.runner.review('reduce', 'approved', 'Reviewed reduction')
            self.runner.review('fit', 'rejected', 'Found a pommel defect')
            with self.assertRaisesRegex(ValueError, 'rejected'): self.runner.result('reduce')
    def test_code_change_invalidates_cached_stage(self):
        self.runner.execute('prepare')
        with patch('tools.itemkit.runner.source_version', return_value='new-version'):
            with self.assertRaisesRegex(ValueError, 'Stale'): self.runner.result('prepare', review=False)
    def test_two_failed_attempts_stop_repeated_processing(self):
        with patch.object(self.runner, '_execute', side_effect=ValueError('fixture failure')):
            for _ in range(2):
                with self.assertRaisesRegex(ValueError, 'fixture failure'): self.runner.execute('prepare')
            with self.assertRaisesRegex(ValueError, 'Two failures'): self.runner.execute('prepare')
    def test_corrected_separate_input_permits_another_attempt(self):
        # Like --evidence: a consumed file outside the manifest, bindings and code version.
        evidence = self.root/'evidence.json'; evidence.write_text('{"version": 1}')
        with patch('tools.itemkit.runner.code_pins', side_effect=lambda: [pin(evidence)]), \
             patch.object(self.runner, '_execute', side_effect=ValueError('fixture failure')):
            for _ in range(2):
                with self.assertRaisesRegex(ValueError, 'fixture failure'): self.runner.execute('prepare')
            with self.assertRaisesRegex(ValueError, 'Two failures'): self.runner.execute('prepare')
            evidence.write_text('{"version": 2}')
            with self.assertRaisesRegex(ValueError, 'fixture failure'): self.runner.execute('prepare')

    def test_changed_ancestor_during_stage_fails_completion(self):
        def compute(stage, folder, **kwargs):
            file = folder/'output.txt'; file.write_text(stage)
            if stage == 'unwrap':
                row = self.runner.state['stages']['fit']
                ancestor = read(row['path'])['result']['artifact']['path']
                Path(ancestor).write_text('changed during child')
            return {'artifact': pin(file)}
        with patch.object(self.runner, '_execute', side_effect=compute):
            self.runner.execute('fit'); self.runner.review('fit', 'approved', 'Reviewed')
            self.runner.execute('reduce'); self.runner.review('reduce', 'approved', 'Reviewed')
            with self.assertRaisesRegex(ValueError, 'Stale'):
                self.runner.execute('unwrap')

    def test_history_does_not_repeat_source_inventory(self):
        for i in range(12):
            write(self.runner.run/'prepare'/f'attempt-old-{i}'/'receipt.json',
                  {'state':'failed','manifestHash':digest(self.runner.data),'codeVersion':'old'})
        with patch('tools.itemkit.runner.source_version', return_value='fixture-version') as version:
            self.runner.execute('prepare')
        self.assertEqual(version.call_count, 1)
    def test_status_is_read_only(self):
        run = self.root/'not-created'; Runner(self.path, self.local, run).status(); self.assertFalse(run.exists())
    def test_client_evidence_must_bind_complete_matrix_and_package(self):
        module = self.root/'a.mod'; module.write_bytes(b'module'); hak = self.root/'a.hak'; hak.write_bytes(b'hak')
        fixture = {'module': pin(module), 'hak': pin(hak), 'fixtureHaks': [pin(hak)]}
        evidence = self.root/'client.json'; write(evidence, {**fixture, 'observations': []})
        with self.assertRaisesRegex(ValueError, 'matrix'): validate_evidence(evidence, fixture)
        screenshot = self.root/'view.png'; screenshot.write_bytes(b'view'); log = self.root/'client.log'; log.write_bytes(b'log')
        observations = [{'body': body, 'check': check, 'result': 'pass', 'reviewedBy': 'fixture-reviewer', 'notes': 'Synthetic contract test only',
            'screenshots': [{'path': screenshot.name, 'sha256': pin(screenshot)['sha256']}],
            'logs': [{'path': log.name, 'sha256': pin(log)['sha256']}]} for body in ('human-male', 'human-female') for check in CHECKS]
        write(evidence, {**fixture, 'observations': observations})
        self.assertFalse(validate_evidence(evidence, fixture)['productionAccepted'])
        hak.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'Stale'): validate_evidence(evidence, fixture)


if __name__ == '__main__': unittest.main()
