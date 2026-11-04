import copy
import unittest
from .generation import apply_export_settings,appearance_donor_graph


class ExportSettingsTests(unittest.TestCase):
    def test_combined_appearance_retains_outputs_and_exact_donor_recipe(self):
        from . import comfy
        from .common import pin
        g=comfy.compile_graph('appearance','pixal-single-v1',{'detail':'detail.png'},
                              'itemkit/test',fov=54,shape=pin(__file__))
        original=copy.deepcopy(g)
        settings={'remeshResolution':768,'targetFaceCount':200000,'signMode':'udf'}
        combined=appearance_donor_graph(g,settings,'itemkit/test')
        self.assertEqual(g,original)
        self.assertEqual({k:combined[k] for k in g},original)
        export=comfy.compile_graph('export','pixal-single-v1',{},'itemkit/test',source=pin(__file__))
        apply_export_settings(export,settings);export['241']['inputs']['mesh']=['92',0]
        self.assertEqual({k:combined[k] for k in ('241','186','187','188','922')},
                         {k:export[k] for k in ('241','186','187','188','922')})
        for node in combined.values():
            for value in node['inputs'].values():
                if isinstance(value,list) and len(value)==2 and isinstance(value[0],str):
                    self.assertIn(value[0],combined)
        for bad in (settings | {'targetFaceCount':20000},settings | {'signMode':'solid'}):
            with self.assertRaisesRegex(ValueError,'qualified'):appearance_donor_graph(g,bad,'itemkit/test')
        with self.assertRaisesRegex(ValueError,'saved-shape'):appearance_donor_graph({},settings,'itemkit/test')

    def graph(self):
        return {'r': {'class_type':'RemeshMesh', 'inputs':{'resolution':512,
                'sign_mode':'udf','sign_mode.qef':False,'sign_mode.drop_inverted_components':False,
                'sign_mode.drop_enclosed_components':False, 'project_back':0.0}},
                'd': {'class_type':'DecimateMesh', 'inputs':{'target_face_count':100000}}}

    def test_legacy_options_preserve_recipe(self):
        graph=self.graph(); before=copy.deepcopy(graph['r']['inputs'])
        apply_export_settings(graph, {'remeshResolution':768,'targetFaceCount':200000})
        before['resolution']=768
        self.assertEqual(graph['r']['inputs'], before)
        self.assertEqual(graph['d']['inputs']['target_face_count'], 200000)

    def test_manifold_is_explicit_sdf_only(self):
        graph=self.graph()
        apply_export_settings(graph, {'remeshResolution':768,'targetFaceCount':200000,
                                     'signMode':'sdf','manifold':True})
        self.assertEqual(graph['r']['inputs']['sign_mode'],'sdf')
        self.assertIs(graph['r']['inputs']['sign_mode.manifold'],True)
        self.assertFalse(any(k.startswith('sign_mode.drop_') for k in graph['r']['inputs']))
        self.assertEqual(graph['r']['inputs']['project_back'],0.0)

    def test_real_template_uses_flat_dynamic_combo_wire_inputs(self):
        from . import comfy
        from .common import pin
        graph=comfy.compile_graph('export','pixal-single-v1',{},'itemkit/test',source=pin(__file__))
        apply_export_settings(graph,{'remeshResolution':768,'targetFaceCount':200000,
                                     'signMode':'sdf','manifold':True})
        remesh=next(n['inputs'] for n in graph.values() if n['class_type']=='RemeshMesh')
        self.assertEqual(remesh['sign_mode'],'sdf')
        self.assertEqual({k:v for k,v in remesh.items() if k.startswith('sign_mode.')},
                         {'sign_mode.qef':False,'sign_mode.manifold':True})

    def test_solid_working_export_removes_incompatible_combo_fields(self):
        graph=self.graph()
        apply_export_settings(graph,{'remeshResolution':768,'targetFaceCount':200000,
                                     'signMode':'solid','fill':40.0})
        remesh=graph['r']['inputs']
        self.assertEqual(remesh['sign_mode'],'solid')
        self.assertEqual({k:v for k,v in remesh.items() if k.startswith('sign_mode.')},
                         {'sign_mode.qef':False,'sign_mode.fill':40.0})
        self.assertEqual(remesh['project_back'],0.0)

    def test_invalid_settings_cannot_partly_mutate_graph(self):
        base={'remeshResolution':768,'targetFaceCount':200000}
        for extra in ({'manifold':True},{'signMode':'udf','manifold':True},
                      {'signMode':'sdf','manifold':1},{'signMode':'invalid'},
                      {'targetFaceCount':200001},{'remeshResolution':True},{'sampler':'x'},
                      {'signMode':'solid','manifold':True},{'signMode':'udf','fill':20},
                      {'signMode':'solid','fill':True},{'signMode':'solid','fill':-1},
                      {'signMode':'solid','fill':float('nan')},{'signMode':'solid','fill':float('inf')}):
            graph=self.graph(); before=copy.deepcopy(graph)
            with self.assertRaises(ValueError): apply_export_settings(graph,base | extra)
            self.assertEqual(graph,before)
