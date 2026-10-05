"""Exact native UV table owner restoration: no guessing, splitting or index edits."""
import unittest
import numpy as np
from restore_provisional_head_native_uv import uv_owners, replace_uv_table
from audit_geometry import arrays


class RestoreProvisionalHeadUvTests(unittest.TestCase):
    def fixture(self):
        original = np.array([[.1250000149,.2],[.3,.4000000298],[.5,.6],[.1250000149,.2]],dtype=np.float32)
        native_faces = np.array([[0,1,2],[3,2,1]])
        ascii_faces = np.array([[0,1,2,1,0,1,2,1],[0,2,1,1,0,2,1,1]])
        tverts = np.array([[.125,.2,0],[.3,.4,0],[.5,.6,0],[.8,.9,3.25]])
        return original,native_faces,ascii_faces,tverts

    def test_every_used_index_has_one_native_float32_owner_and_unused_rows_stay(self):
        original,native_faces,ascii_faces,tverts=self.fixture()
        restored,proof=uv_owners(original,native_faces,ascii_faces,tverts)
        self.assertEqual(proof['usedTvertIndices'],[0,1,2]);self.assertEqual(proof['unusedTvertIndicesPreserved'],[3])
        self.assertTrue(np.array_equal(restored[:3,:2].astype(np.float32).view(np.uint32),original[:3].view(np.uint32)))
        self.assertTrue(np.array_equal(restored[:,2],tverts[:,2]));self.assertTrue(np.array_equal(restored[3],tverts[3]))
        self.assertEqual(proof['orderedFaceCornerUsesByTvertIndex'],{'0':2,'1':2,'2':2})
        self.assertTrue(np.array_equal(tverts,self.fixture()[3]))

    def test_conflicting_native_values_for_reused_index_fail_closed(self):
        original,native_faces,ascii_faces,tverts=self.fixture()
        original[3,0]=np.nextafter(original[3,0],np.float32(1))
        with self.assertRaisesRegex(ValueError,'Ambiguous'):
            uv_owners(original,native_faces,ascii_faces,tverts)

    def test_signed_zero_owners_are_compared_as_original_bits(self):
        original,native_faces,ascii_faces,tverts=self.fixture()
        original[0,0]=np.float32(0);original[3,0]=np.float32(-0.)
        with self.assertRaisesRegex(ValueError,'Ambiguous'):
            uv_owners(original,native_faces,ascii_faces,tverts)

    def test_out_of_range_noninteger_and_changed_coverage_rejected(self):
        fixture=self.fixture()
        for label in ('native-range','uv-range','coverage','noninteger','nonfinite'):
            values=[item.copy() for item in fixture]
            if label=='native-range':values[1][0,0]=99
            elif label=='uv-range':values[2][0,4]=99
            elif label=='coverage':values[1]=values[1][:1]
            elif label=='noninteger':values[2]=values[2].astype(float)
            else:values[0][0,0]=np.nan
            with self.subTest(label=label),self.assertRaises(ValueError):uv_owners(*values)

    def test_literal_table_restoration_changes_only_uv_values_preserving_indices_and_third_tokens(self):
        original,native_faces,ascii_faces,tverts=self.fixture()
        restored,proof=uv_owners(original,native_faces,ascii_faces,tverts)
        before='node trimesh pmh0_head001g\n bitmap pmg0_head001\n verts 3\n 1 0 0\n 0 1 0\n 0 0 1\n tverts 4\n  .125  .2   0\n  .3 .4 0\n  .5 .6 0\n  .8 .9 3.25\n faces 2\n 0 1 2 1 0 1 2 1\n 0 2 1 1 0 2 1 1\n normals 0\n position .02 .03 .04\nendnode\n'
        after=replace_uv_table(before,tverts,restored,proof['usedTvertIndices'])
        self.assertEqual(after[:after.index(' tverts')],before[:before.index(' tverts')])
        self.assertEqual(after[after.index(' faces'):],before[before.index(' faces'):])
        self.assertIn('  .8 .9 3.25\n',after)
        observed=np.asarray(arrays(after,'tverts'))
        self.assertTrue(np.array_equal(observed,restored))
        self.assertTrue(np.array_equal(observed[:3,:2].astype(np.float32).view(np.uint32),original[:3].view(np.uint32)))

    def test_precision_format_roundtrips_small_native_floats(self):
        values=np.array([[np.nextafter(np.float32(0),np.float32(1)),np.float32(-0.)],
                         [np.float32(.99999994),np.float32(-.33333334)],
                         [np.float32(1e-20),np.float32(.10000001)]],dtype=np.float32)
        tverts=np.column_stack([values.astype(float),[0,0,0]])
        before=' tverts 3\n'+''.join('  '+ ' '.join(str(float(x)) for x in row)+'\n' for row in tverts)+' faces 1\n 0 1 2 1 0 1 2 1\n'
        after=replace_uv_table(before,tverts,tverts,[0,1,2])
        actual=np.asarray(arrays(after,'tverts'))[:,:2].astype(np.float32)
        self.assertTrue(np.array_equal(actual.view(np.uint32),values.view(np.uint32)))

    def test_missing_duplicate_or_modified_base_table_rejected(self):
        _,_,_,tverts=self.fixture()
        text=' tverts 4\n .125 .2 0\n .3 .4 0\n .5 .6 0\n .8 .9 3.25\n'
        for bad in (text.replace(' tverts',' unknown'),text+text,text.replace('.125','.126')):
            with self.assertRaises(ValueError):replace_uv_table(bad,tverts,tverts,[0,1,2])
        with self.assertRaisesRegex(ValueError,'outside table'):replace_uv_table(text,tverts,tverts,[99])


if __name__=='__main__':unittest.main()
