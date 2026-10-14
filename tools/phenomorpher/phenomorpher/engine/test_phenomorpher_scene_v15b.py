import tempfile,unittest
from pathlib import Path
import numpy as np
from .phenomorpher_scene_v15b import glb_document,export_glb,read_attributes,derived_normals
from .test_phenomorpher_scene_v15a import fixture


def values(doc,binary,index):
    a=doc['accessors'][index];v=doc['bufferViews'][a['bufferView']]
    dtype={5126:'<f4',5123:'<u2',5125:'<u4'}[a['componentType']]
    width={'SCALAR':1,'VEC2':2,'VEC3':3}[a['type']]
    return np.frombuffer(binary,dtype,count=a['count']*width,offset=v['byteOffset']).reshape(a['count'],width)


class GltfLineageTests(unittest.TestCase):
    def test_unused_vertices_recover_exactly_without_fabricated_normals(self):
        p=np.array([[0,0,0],[1,0,0],[0,0,1],[9,8,7]],float);f=np.array([[0,1,2]])
        normals=derived_normals(p,f);np.testing.assert_array_equal(normals[3],[0,0,0])
        a={'position':p.copy(),'faces':f.copy()};candidate=p+[.2,.3,.4]
        m={'name':'mesh','part':'chest','position':candidate,'faces':f,'render':True,'sourceAttributes':a}
        frames={'torso_g':np.eye(4)};parents={'torso_g':'null'}
        doc,b=glb_document([m],frames,parents);attrs=doc['meshes'][0]['primitives'][0]['attributes']
        self.assertEqual(doc['accessors'][attrs['NORMAL']]['count'],3)
        self.assertEqual(doc['meshes'][0]['extras']['sourceVertexCount'],4)
        with tempfile.TemporaryDirectory() as tmp:
            out=export_glb([m],frames,parents,Path(tmp)/'scene.glb')
            with np.load(out['sourceAttributeArchive']['path']) as data:
                np.testing.assert_array_equal(data['mesh0_position'],p)
                np.testing.assert_array_equal(data['mesh0_current_position'],candidate)
                np.testing.assert_array_equal(data['mesh0_current_faces'],f)

    def test_referenced_zero_or_cancelling_normals_reject(self):
        p=np.array([[0,0,0],[1,0,0],[0,0,1]],float)
        with self.assertRaisesRegex(ValueError,'referenced'):derived_normals(p,np.array([[0,1,2],[2,1,0]]))
        with self.assertRaisesRegex(ValueError,'referenced'):derived_normals(p,np.array([[0,0,1]]))

    def test_unsigned_int_used_only_for_indices_and_half_words_recover_exact_colors(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'test.mdl';p.write_bytes(fixture());_,attrs,_=read_attributes(p);a=attrs['mesh']
            mesh={**a,'part':'chest','sourceAttributes':a};frames={'torso_g':np.eye(4)};parents={'torso_g':'null'}
            doc,binary=glb_document([mesh],frames,parents);primitive=doc['meshes'][0]['primitives'][0]
            indices={primitive['indices']}
            for i,accessor in enumerate(doc['accessors']):
                self.assertGreater(accessor['count'],0)
                if accessor['componentType']==5125:self.assertIn(i,indices)
            attr=primitive['attributes'];self.assertNotIn('COLOR_0',attr)
            vi=values(doc,binary,attr['_NWN_VERTEX_INDEX']).reshape(-1).astype(int)
            ui=values(doc,binary,attr['_NWN_UV_INDEX']).reshape(-1).astype(int)
            triangles=values(doc,binary,primitive['indices']).reshape(-1,3)
            np.testing.assert_array_equal(vi[triangles],a['faces'])
            np.testing.assert_array_equal(ui[triangles],a['uvFaces'])
            c=doc['accessors'][attr['_NWN_PACKED_COLOR_HALVES']];self.assertEqual(c['componentType'],5123);self.assertEqual(c['type'],'VEC2');self.assertFalse(c.get('normalized',False))
            halves=values(doc,binary,attr['_NWN_PACKED_COLOR_HALVES']).astype(np.uint32)
            np.testing.assert_array_equal(halves[:,0]|(halves[:,1]<<16),a['color'][vi].reshape(-1))
            out=export_glb([mesh],frames,parents,Path(tmp)/'scene.glb')
            with np.load(out['sourceAttributeArchive']['path']) as data:np.testing.assert_array_equal(data['mesh0_color'],a['color'])

    def test_uv_representation_split_preserves_lineage_counts(self):
        p=np.array([[0,0,0],[1,0,0],[1,0,1],[0,0,1]],float);f=np.array([[0,1,2],[0,2,3]])
        a={'position':p,'faces':f,'uv':np.array([[0,0],[1,0],[1,1],[0,1],[.2,.2]]),'uvFaces':np.array([[0,1,2],[4,2,3]])}
        m={'name':'mesh','part':'chest','position':p,'faces':f,'render':True,'sourceAttributes':a}
        doc,b=glb_document([m],{'torso_g':np.eye(4)},{'torso_g':'null'});primitive=doc['meshes'][0]['primitives'][0]
        self.assertEqual({doc['accessors'][i]['count'] for i in primitive['attributes'].values()},{5})
        indices=values(doc,b,primitive['indices']).reshape(-1,3)
        vi=values(doc,b,primitive['attributes']['_NWN_VERTEX_INDEX']).reshape(-1).astype(int)
        np.testing.assert_array_equal(vi[indices],f)

if __name__=='__main__':unittest.main()
