"""Protect original workflow behavior and the explicit six-camera contract."""
import copy
import unittest
from generate_purpose_built_part import configure_projection, recorded_views, VIEW_ORDER, ORTHO_VIEW_ORDER

class ProjectionTests(unittest.TestCase):
    def source(self):
        return {'324':{'class_type':'Pixal3DMultiViewConditioning','inputs':{'clip_vision_model':['120',0],'fov':30,'front':['123',0]}},'3':{'seed':44}}

    def schema(self):
        return {'SRNOrthographicMultiViewConditioning':{'input':{'required':{key:[] for key in ('clip_vision_model','ortho_span','front')},'optional':{key:[] for key in ORTHO_VIEW_ORDER[1:]}}}}

    def test_original_branch_unchanged_except_declared_fov(self):
        graph=self.source(); expected=copy.deepcopy(graph); expected['324']['inputs']['fov']=20
        self.assertEqual(configure_projection(graph,{'viewOrder':list(VIEW_ORDER),'fovDegrees':20},{}),VIEW_ORDER)
        self.assertEqual(graph,expected)

    def test_orthographic_changes_only_conditioning_not_source(self):
        source=self.source(); graph=copy.deepcopy(source)
        order=configure_projection(graph,{'projection':'orthographic-six-view','viewOrder':list(ORTHO_VIEW_ORDER),'orthoSpan':1.1},self.schema())
        self.assertEqual(order,ORTHO_VIEW_ORDER)
        self.assertEqual(graph['3'],source['3'])
        self.assertEqual(source,self.source())
        self.assertEqual(graph['324']['inputs'],{'clip_vision_model':['120',0],'ortho_span':1.1})

    def test_missing_camera_schema_or_wrong_order_rejected(self):
        config={'projection':'orthographic-six-view','viewOrder':list(ORTHO_VIEW_ORDER),'orthoSpan':1.1}
        schema=self.schema(); del schema['SRNOrthographicMultiViewConditioning']['input']['optional']['bottom']
        with self.assertRaisesRegex(RuntimeError,'schema'):configure_projection(self.source(),config,schema)
        config['viewOrder']=list(VIEW_ORDER)
        with self.assertRaisesRegex(RuntimeError,'view order'):configure_projection(self.source(),config,self.schema())

    def test_legacy_receipt_order_and_incomplete_receipt(self):
        self.assertEqual(recorded_views({'views':{k:{} for k in VIEW_ORDER}}),VIEW_ORDER)
        with self.assertRaises(RuntimeError):recorded_views({'viewOrder':list(ORTHO_VIEW_ORDER),'views':{k:{} for k in VIEW_ORDER}})

if __name__=='__main__':unittest.main()
