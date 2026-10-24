import copy
import unittest
from .generation import apply_export_settings


class ExportSettingsTests(unittest.TestCase):
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

    def test_invalid_settings_cannot_partly_mutate_graph(self):
        base={'remeshResolution':768,'targetFaceCount':200000}
        for extra in ({'manifold':True},{'signMode':'udf','manifold':True},
                      {'signMode':'sdf','manifold':1},{'signMode':'invalid'},
                      {'targetFaceCount':200001},{'remeshResolution':True},{'sampler':'x'}):
            graph=self.graph(); before=copy.deepcopy(graph)
            with self.assertRaises(ValueError): apply_export_settings(graph,base | extra)
            self.assertEqual(graph,before)
