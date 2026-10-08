"""Explicit native mesh seam preserves authored corner samples and face lineage."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

import numpy as np

from diagnose_native_tangent_seam import face_groups, inspect_split_ascii, write_split_ascii
from stage_stock_part import geometry


def source():
    # Three connected triangles share exact vertex samples but the final cap
    # sliver has reversed UV handedness. Mesh separation must never repair those.
    p=np.asarray([[[0,0,0],[1,0,0],[0,1,0]],
                  [[0,0,0],[0,1,0],[-1,0,0]],
                  [[0,0,0],[-1,0,0],[-.5,.01,0]]],dtype=float)
    n=np.tile([0,0,1],(3,3,1)).astype(float)
    uv=np.asarray([[[.5,.5],[1,.5],[.5,1]],
                   [[.5,.5],[.5,1],[0,.5]],
                   [[.5,.5],[0,.5],[.25,.51]]],dtype=float)
    return p,n,uv


class NativeTangentSeamTests(unittest.TestCase):
    def test_complete_mesh_partition_preserves_every_corner_and_welded_surface(self):
        p,n,uv=source();model='pfh0_bicepl001'
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'seam.mdl';meshes=write_split_ascii(path,model,p,n,uv,[2])
            rows=inspect_split_ascii(path,model,p,n,uv,meshes)
            self.assertEqual(list(meshes),[model+'p0',model+'p1'])
            self.assertEqual(meshes[model+'p0']['sourceFaceIds'],[0,1])
            self.assertEqual(meshes[model+'p1']['sourceFaceIds'],[2])
            np.testing.assert_array_equal(rows[model+'p0']['position'],p[:2])
            np.testing.assert_array_equal(rows[model+'p1']['position'],p[2:])
            result=np.empty_like(p)
            for name,row in rows.items():
                ids=meshes[name]['sourceFaceIds'];result[ids]=row['position']
                np.testing.assert_array_equal(row['normal'],n[ids])
                np.testing.assert_array_equal(row['uv'],uv[ids])
                self.assertEqual(meshes[name]['material'],model)
            self.assertEqual(geometry(result),geometry(p))
            # Every mesh has its own copies of both exact boundary samples.
            main=set(map(tuple,np.concatenate([p[:2],n[:2],uv[:2]],axis=2).reshape(-1,8)))
            cap=set(map(tuple,np.concatenate([p[2:],n[2:],uv[2:]],axis=2).reshape(-1,8)))
            self.assertEqual(len(main & cap),2)
            d=rows[model+'p1']['uv'][0];self.assertLess(np.linalg.det([d[1]-d[0],d[2]-d[0]]),0)

    def test_subset_must_be_explicit_unique_sorted_integer_and_proper(self):
        for ids in ([],[True],[1.0],[-1],[3],[1,1],[2,1],[0,1,2],None,'2'):
            with self.subTest(ids=ids),self.assertRaises(ValueError):face_groups(3,ids)

    def test_changed_material_transform_hierarchy_or_corner_rejects(self):
        p,n,uv=source();model='pfh0_bicepl001'
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'seam.mdl';meshes=write_split_ascii(path,model,p,n,uv,[2]);original=path.read_text()
            changes=[original.replace('bitmap '+model,'bitmap changed',1),
                     original.replace('materialname '+model,'materialname changed',1),
                     original.replace('position 0 0 0','position .1 0 0',1),
                     original.replace('position 0 0 0','position 0 0 0\n  scale 1',1),
                     original.replace('node trimesh '+model+'p1','node skin '+model+'p1'),
                     original.replace('parent '+model,'parent unrelated',1),
                     original.replace('setsupermodel '+model+' NULL','setsupermodel '+model+' private'),
                     original.replace('  1 0 0','  .9 0 0',1)]
            for index,text in enumerate(changes):
                self.assertNotEqual(text,original)
                path.write_text(text)
                with self.subTest(change=index),self.assertRaises(ValueError):inspect_split_ascii(path,model,p,n,uv,meshes)

    def test_face_lineage_duplicates_omissions_and_stale_uv_reject(self):
        p,n,uv=source();model='pfh0_bicepl001'
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'seam.mdl';meshes=write_split_ascii(path,model,p,n,uv,[2])
            for ids in ([1],[3],[-1],[2.0],[]):
                changed=deepcopy(meshes);changed[model+'p1']['sourceFaceIds']=ids
                with self.subTest(ids=ids),self.assertRaises(ValueError):inspect_split_ascii(path,model,p,n,uv,changed)
            changed=uv.copy();changed[2,0,0]+=1e-8
            with self.assertRaisesRegex(ValueError,'source-corner'):inspect_split_ascii(path,model,p,n,changed,meshes)

    def test_normal_and_nonfinite_samples_reject(self):
        p,n,uv=source();model='pfh0_bicepl001'
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'seam.mdl';meshes=write_split_ascii(path,model,p,n,uv,[2])
            changed=n.copy();changed[2,0,0]=.1
            with self.assertRaisesRegex(ValueError,'source-corner'):inspect_split_ascii(path,model,p,changed,uv,meshes)
            path.write_text(path.read_text().replace('  1 0 0','  nan 0 0',1))
            with self.assertRaisesRegex(ValueError,'Finite'):inspect_split_ascii(path,model,p,n,uv,meshes)

    def test_existing_diagnostic_never_overwritten(self):
        p,n,uv=source();model='pfh0_bicepl001'
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'seam.mdl';write_split_ascii(path,model,p,n,uv,[2]);before=path.read_bytes()
            with self.assertRaisesRegex(ValueError,'Fresh'):write_split_ascii(path,model,p,n,uv,[1])
            self.assertEqual(path.read_bytes(),before)


if __name__=='__main__':unittest.main()
