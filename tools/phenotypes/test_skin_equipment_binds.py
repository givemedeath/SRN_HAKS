"""Verify skin bind-relative widening and exactly-once stature conversion."""
import unittest
import struct
import numpy as np
from audit_skin_equipment_binds import parse_weights, retarget_skin_points
from measure_held_equipment import bounds
from audit_stock_equipment_palettes import read_stock_plt


def frame(position=(0,0,0),rotation=None):
    result=np.eye(4);result[:3,3]=position
    if rotation is not None:result[:3,:3]=rotation
    return result


class SkinEquipmentTests(unittest.TestCase):
    def test_identity_preserves_blended_vertices(self):
        frames={'left':frame([-1,0,0]),'right':frame([1,0,0])}
        points=np.array([[.1,.2,.3],[-.4,.5,.6]])
        weights=[[('left',.25),('right',.75)],[('left',1)]]
        np.testing.assert_allclose(retarget_skin_points(points,weights,frames,frames,1),points,atol=1e-12)

    def test_widening_follows_same_source_weight_correspondence(self):
        source={'left':frame([-1,0,0]),'right':frame([1,0,0])}
        target={'left':frame([-1.2,0,0]),'right':frame([1.2,0,0])}
        result=retarget_skin_points([[.5,.7,.9]],[ [('left',.25),('right',.75)] ],source,target,1)
        np.testing.assert_allclose(result,[[.6,.7,.9]],atol=1e-12)

    def test_final_scale_changes_bind_and_displacement_once(self):
        scale=10/7
        source={'left':frame([-1,0,0]),'right':frame([1,0,0])}
        target={'left':frame(np.array([-1.2,0,0])*scale),'right':frame(np.array([1.2,0,0])*scale)}
        result=retarget_skin_points([[.5,.7,.9]],[ [('left',.25),('right',.75)] ],source,target,scale)
        np.testing.assert_allclose(result,np.array([[.6,.7,.9]])*scale,atol=1e-12)

    def test_parent_local_basis_is_resolved_through_world_frames(self):
        source={'bone':frame([1,2,3],np.array([[0,-1,0],[1,0,0],[0,0,1]]))}
        target={'bone':frame([4,5,6])}
        result=retarget_skin_points([[1,3,3]],[ [('bone',1)] ],source,target,2)
        np.testing.assert_allclose(result,[[6,5,6]],atol=1e-12)

    def test_rejects_unresolved_binds_nonrigid_frames_bad_weights_and_correspondence(self):
        source={'bone':frame()}
        with self.assertRaisesRegex(RuntimeError,'Unresolved'):retarget_skin_points([[0,0,0]],[ [('absent',1)] ],source,source,1)
        with self.assertRaisesRegex(RuntimeError,'one-to-one'):retarget_skin_points([[0,0,0]],[],source,source,1)
        invalid=frame();invalid[0,0]=2
        with self.assertRaisesRegex(RuntimeError,'proper/rigid'):retarget_skin_points([[0,0,0]],[ [('bone',1)] ],source,{'bone':invalid},1)
        for weight in [1.1,-.1,float('nan')]:
            with self.assertRaises(RuntimeError):retarget_skin_points([[0,0,0]],[ [('bone',weight)] ],source,source,1)
        with self.assertRaises(RuntimeError):retarget_skin_points([[0,0,0]],[ [('bone',1)] ],source,source,0)

    def test_parse_retains_bone_names_order_and_weights(self):
        parsed=parse_weights(' weights 2\n left .25 right .75\n left 1 right 0\n',2)
        self.assertEqual(parsed,[[('left',.25),('right',.75)],[('left',1),('right',0)]])
        with self.assertRaisesRegex(RuntimeError,'counts'):parse_weights(' weights 1\n left 1\n',2)
        with self.assertRaisesRegex(RuntimeError,'Unnormalized'):parse_weights(' weights 1\n left .8\n',1)

    def test_bound_measurement_skips_nonrendering_bone_geometry(self):
        text='''newmodel model
beginmodelgeom model
node dummy model
 parent NULL
endnode
node trimesh hidden
 parent model
 render 0
 verts 3
 100 100 100
 101 100 100
 100 101 100
endnode
node trimesh actual
 parent model
 position 1 2 3
 verts 3
 0 0 0
 1 0 0
 0 1 0
endnode
endmodelgeom model
'''
        result=bounds(text)
        self.assertEqual(result['minimumModelLocalNwn'],[1,2,3])
        self.assertEqual(result['maximumModelLocalNwn'],[2,3,3])
        self.assertEqual(result['renderedVertices'],3)


class StockEquipmentPaletteTests(unittest.TestCase):
    def test_unused_header_dwords_are_not_material_channel_count(self):
        blob=b'PLT V1  '+struct.pack('<IIII',4,17,2,2)+bytes([10,0,20,9,30,2,40,1])
        before=bytes(blob);result=read_stock_plt(blob)
        self.assertEqual(result['unusedHeaderDwords'],[4,17])
        self.assertEqual(result['materialChannelPixelCounts'],{'0':1,'1':1,'2':1,'9':1})
        self.assertEqual(blob,before)

    def test_custom_writer_header_and_native_stock_header_are_both_supported(self):
        for unused in [4,10,0]:
            result=read_stock_plt(b'PLT V1  '+struct.pack('<IIII',unused,0,1,1)+bytes([128,9]))
            self.assertEqual(result['width'],1)
            self.assertEqual(result['materialChannelPixelCounts'],{'9':1})

    def test_rejects_invalid_material_index_or_payload_length(self):
        prefix=b'PLT V1  '+struct.pack('<IIII',4,0,1,1)
        for blob in [prefix+bytes([128,10]),prefix+bytes([128]),b'wrong'+prefix[5:]+bytes([128,9])]:
            with self.assertRaises(RuntimeError):read_stock_plt(blob)


if __name__=='__main__':unittest.main()
