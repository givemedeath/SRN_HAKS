"""Face selection must preserve encoded attributes and reject ambiguous caps."""
import copy
from pathlib import Path
import tempfile
import unittest

import numpy as np

from conservative_face_selection import descendant, mesh_arrays, topology, face_components, cap_one_micro_boundary
from place_purposebuilt_pelvis import read_glb, write_glb
from test_mirror_stock_limb_part import fixture


class ConservativeFaceSelectionTests(unittest.TestCase):
    def test_index_only_descendant_preserves_nonunit_normals_uv_color_and_maps(self):
        document,binary=fixture()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'source.glb';output=root/'trial.glb'
            write_glb(source,document,binary);original=source.read_bytes()
            proof=descendant(source,output,[0,1,2])
            changed,blob=read_glb(output)
            self.assertEqual(source.read_bytes(),original)
            self.assertEqual(blob[:len(binary)],binary)
            self.assertEqual(changed['materials'],document['materials'])
            self.assertEqual(changed['meshes'][0]['primitives'][0]['attributes'],
                             document['meshes'][0]['primitives'][0]['attributes'])
            self.assertTrue(proof['keptCornerEncodedBytesExact'])
            self.assertEqual(proof['afterTopology']['boundaryEdges'],3)
            self.assertEqual(proof['positionMovement'],0)
            self.assertEqual(proof['normalChanges'],0)

    def test_reuses_exact_source_vertex_rows_to_close_a_measured_micro_hole(self):
        document,binary=fixture();positions,faces,_=mesh_arrays(document,binary)
        positions=positions*.001
        added,proof=cap_one_micro_boundary(positions,faces[:3],.002,.000001)
        self.assertEqual(len(added),1)
        self.assertEqual(set(added[0]),set(faces[3]))
        self.assertEqual(proof['afterTopology']['boundaryEdges'],0)
        self.assertEqual(proof['afterTopology']['nonmanifoldVertexLinks'],0)
        self.assertGreater(proof['afterTopology']['signedVolume'],0)
        self.assertEqual(proof['attributePolicy'],
                         'Only existing neighboring source vertex rows reused; no new UV/normal/position data')

    def test_cap_rejects_broad_connector_or_area_bound(self):
        document,binary=fixture();positions,faces,_=mesh_arrays(document,binary)
        with self.assertRaisesRegex(RuntimeError,'repair bound'):
            cap_one_micro_boundary(positions,faces[:3],.002,.001)
        with self.assertRaisesRegex(RuntimeError,'triangulation'):
            cap_one_micro_boundary(positions*.001,faces[:3],.002,1e-10)

    def test_vertex_pinches_and_independent_components_are_not_closed_body_proof(self):
        document,binary=fixture();positions,faces,_=mesh_arrays(document,binary)
        # Two tetrahedra touch at exactly one coordinate but share no edge.
        p=np.concatenate((positions,positions+np.array([0,0,.4],dtype=np.float32)))
        f=np.concatenate((faces,faces+4))
        proof=topology(p,f)
        self.assertEqual(proof['boundaryEdges'],0)
        self.assertEqual(proof['nonmanifoldEdges'],0)
        self.assertEqual(proof['nonmanifoldVertexLinks'],1)
        self.assertEqual(sorted(map(len,face_components(p,f))),[4,4])

    def test_coordinate_seam_weld_is_diagnostic_and_does_not_replace_rows(self):
        document,binary=fixture();positions,faces,_=mesh_arrays(document,binary)
        split=positions[faces].reshape(-1,3);indices=np.arange(len(split)).reshape(-1,3)
        proof=topology(split,indices)
        self.assertEqual(proof['exactPositionVertices'],4)
        self.assertEqual(proof['referencedSerializedVertices'],12)
        self.assertEqual(proof['boundaryEdges'],0)
        self.assertEqual(len(face_components(split,indices)),1)

    def test_rejects_transformed_source_duplicate_face_selection_and_overwrite(self):
        document,binary=fixture()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'source.glb';output=root/'trial.glb'
            write_glb(source,document,binary)
            with self.assertRaisesRegex(RuntimeError,'Ordered unique'):
                descendant(source,output,[0,0])
            descendant(source,output,[0,1,2])
            with self.assertRaisesRegex(RuntimeError,'Fresh'):
                descendant(source,output,[0,1,2])
            changed=copy.deepcopy(document);changed['nodes'][0]['translation']=[0,0,1]
            with self.assertRaisesRegex(RuntimeError,'identity-node'):
                mesh_arrays(changed,binary)


if __name__=='__main__':unittest.main()
