import unittest
import numpy as np
from repair_troll_pelvis_opposite_pairs import active_inventory, index_child, pair_equivalence, preservation, primitives
from write_bounded_pelvis_diagnostic import append_accessor


class OppositePairRepairTests(unittest.TestCase):
    def original(self):
        doc={'asset':{'version':'2.0'},'buffers':[{'byteLength':0}],'accessors':[],'bufferViews':[],
            'materials':[{'name':'original-body'},{'name':'protected-caps'}],'nodes':[{'mesh':0,'name':'detached_geometry'}],
            'scenes':[{'nodes':[0]}],'scene':0,'meshes':[{'primitives':[]}]}
        binary=b'PROTECTED_BINARY';attrs={}
        data={'POSITION':np.array([[0.,0.,0.],[1.,0.,0.],[0.,0.,1.],[1.,0.,1.],[.5,.1,.5]]),
              'NORMAL':np.array([[0.,-1.,0.]]*4+[[0.,0.,0.]]),
              'TEXCOORD_0':np.array([[0.,0.],[1.,0.],[0.,1.],[1.,1.],[.5,.5]]),
              'TANGENT':np.array([[1.,0.,0.,1.]]*5)}
        for key,rows in data.items():binary,index=append_accessor(doc,binary,rows,key);attrs[key]=index
        body=np.array([[0,1,2],[1,3,2],[0,4,1],[0,1,4],[1,4,3],[1,3,4]])
        binary,index=append_accessor(doc,binary,body,'indices')
        doc['meshes'][0]['primitives'].append({'attributes':attrs.copy(),'indices':index,'material':0,'mode':4})
        for side in ('left','right'):
            binary,index=append_accessor(doc,binary,np.array([[0,1,2]]),'indices')
            doc['meshes'][0]['primitives'].append({'attributes':attrs.copy(),'indices':index,'material':1,'mode':4,'extras':{'cap':side}})
        binary+=b'\0'*(-len(binary)%4);doc['buffers'][0]['byteLength']=len(binary)
        return doc,binary

    def test_append_only_four_face_removal_preserves_caps_and_original_bin(self):
        doc,blob=self.original();mask=np.array([True,True,False,False,False,False])
        child,binary=index_child(doc,blob,mask);proof=preservation(doc,blob,child,binary,mask)
        self.assertTrue(proof['allOriginalBinBytesExact']);self.assertTrue(proof['bothCapPrimitivesAndAllCapCornerBytesExact'])
        self.assertEqual(len(child['accessors']),len(doc['accessors'])+1)
        self.assertEqual(len(primitives(child,binary)[0]['faces']),2)

    def test_unreferenced_bad_normal_explicitly_retained_and_active_rows_clean(self):
        doc,blob=self.original();child,binary=index_child(doc,blob,[True,True,False,False,False,False])
        inventory,arrays=active_inventory(primitives(child,binary))
        self.assertEqual(inventory[0]['storedNearZeroNormalRows'],[4]);self.assertEqual(inventory[0]['activeNearZeroNormalRows'],[])
        self.assertNotIn(4,arrays['primitive0ReferencedOriginalAccessorRows'])
        self.assertTrue(np.array_equal(primitives(child,binary)[0]['attributes']['NORMAL'][4],[0,0,0]))

    def test_active_bad_normal_rejected(self):
        doc,blob=self.original()
        with self.assertRaisesRegex(ValueError,'Referenced invalid'):active_inventory(primitives(doc,blob))

    def test_wrong_removal_count_rejected(self):
        doc,blob=self.original()
        with self.assertRaisesRegex(ValueError,'four'):index_child(doc,blob,[True,True,False,False,False,True])

    def test_changed_cap_index_binding_rejected(self):
        doc,blob=self.original();mask=np.array([True,True,False,False,False,False]);child,binary=index_child(doc,blob,mask)
        child['meshes'][0]['primitives'][1]['material']=0
        with self.assertRaisesRegex(ValueError,'cap'):preservation(doc,blob,child,binary,mask)

    def test_changed_original_bin_rejected(self):
        doc,blob=self.original();mask=np.array([True,True,False,False,False,False]);child,binary=index_child(doc,blob,mask)
        with self.assertRaisesRegex(ValueError,'prefix'):preservation(doc,blob,child,b'X'+binary[1:],mask)

    def test_retained_corner_reordering_rejected(self):
        doc,blob=self.original();mask=np.array([True,True,False,False,False,False]);child,binary=index_child(doc,blob,mask)
        with self.assertRaisesRegex(ValueError,'corner'):preservation(doc,blob,child,binary,np.array([True,False,True,False,False,False]))

    def test_opposite_duplicate_corner_equivalence(self):
        doc,blob=self.original();rows=primitives(doc,blob)[0]
        result=pair_equivalence(rows['attributes'],rows['faces'][2],rows['faces'][3]);self.assertTrue(result['oppositeWinding'])

    def test_same_winding_rejected(self):
        doc,blob=self.original();row=primitives(doc,blob)[0]
        with self.assertRaisesRegex(ValueError,'winding'):pair_equivalence(row['attributes'],row['faces'][2],row['faces'][2])

    def test_distinct_painted_duplicate_corner_rejected(self):
        doc,blob=self.original();row=primitives(doc,blob)[0];attrs={key:np.concatenate((v,v[[4]])) for key,v in row['attributes'].items()}
        attrs['TEXCOORD_0'][5]=[.1,.2]
        with self.assertRaisesRegex(ValueError,'TEXCOORD'):pair_equivalence(attrs,np.array([0,4,1]),np.array([0,1,5]))


if __name__=='__main__':unittest.main()
