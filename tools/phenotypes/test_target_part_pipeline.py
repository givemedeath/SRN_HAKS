"""Target frame, serialized attribute and single runtime conversion regressions."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

import target_contract as contract
from target_part_pipeline import execute, fit_matrix
from place_purposebuilt_pelvis import raw_corners, read_glb, rotation_xyz, write_glb
from test_mirror_stock_limb_part import fixture


def target_fixture():
    frames = {joint: np.eye(4) for joint in contract.PART_JOINTS.values()}
    frames['lbicep_g'][:3, :3] = rotation_xyz([13, 7, -23])
    frames['rbicep_g'][:3, :3] = rotation_xyz([-11, 5, 27])
    frames['lbicep_g'][:3, 3] = [-.27, .03, 1.45]
    frames['rbicep_g'][:3, 3] = [.271, .03, 1.45]
    factor = 10/7
    runtime = copy.deepcopy(frames)
    for row in runtime.values(): row[:3, 3] *= factor
    return {'schemaVersion': 2, 'kind': 'phenotype-target', 'id': 'test-troll',
            'identity': {'gender': 'male', 'phenotype': 0, 'prefix': 'pmg0', 'raceId': 2, 'appearanceRow': 2},
            'workingHeightMeters': 1.9339157, 'heightMeters': 1.9339157*factor,
            'models': {part: 'pmg0_'+part+'001' for part in contract.PART_JOINTS},
            'rig': {'revision': 'unaccepted-pilot', 'runtimeScale': factor, 'pilotAccepted': False,
                    'positionPolicy': 'bind-relative', 'preserveRotations': True, 'preserveTimingEvents': True,
                    'frames': {'working': {k:v.tolist() for k,v in frames.items()},
                               'runtime': {k:v.tolist() for k,v in runtime.items()}},
                    'privateAliases': {'pmh0':'pmg0', 'a_ba':'sr_tmg0_01'}}, 'frozenInputs': {}}


class TargetPartPipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.target = self.root/'target.json'; self.target.write_text(json.dumps(target_fixture()))
        doc, blob = fixture(); self.source = self.root/'raw.glb'; write_glb(self.source, doc, blob)
        self.job = self.root/'job.json'
        self.job.write_text(json.dumps({'state':'success','promptId':'test-prompt',
             'outputs':[{'localPath':str(self.source), 'sha256':contract.sha(self.source)}]}))

    def tearDown(self): self.tmp.cleanup()

    def config(self, source, receipt, operation='fit', part='bicepl', space='working'):
        result = {'schemaVersion':2, 'operation':operation, 'part':part, 'coordinateSpace':space,
                'targetContract':str(self.target), 'targetContractSha256':contract.sha(self.target),
                'source':str(source), 'sourceSha256':contract.sha(source),
                'sourceReceipt':str(receipt), 'sourceReceiptSha256':contract.sha(receipt)}
        if operation == 'fit':
            result.update(uniformScale=.63, rotationDegreesXYZ=[19,-7,31],
                          sourceAnchorNwn=[.11,.08,.02], targetAnchorLocal=[.03,-.02,-.04])
        return result

    def run_config(self, config, name):
        path = self.root/(name+'.json'); path.write_text(json.dumps(config))
        result = execute(path, self.root/name)
        return result, json.loads(result.read_text())

    def test_fit_preserves_maps_uv_and_authored_normals(self):
        config = self.config(self.source, self.job)
        _, result = self.run_config(config, 'fit')
        doc, binary = read_glb(self.source); new, new_bin = read_glb(result['candidate'])
        p, n, uv, _ = raw_corners(doc, binary)
        ap, an, au, _ = raw_corners(new, new_bin)
        matrix = fit_matrix(config)
        self.assertTrue(np.allclose(ap, p@matrix[:3,:3].T+matrix[:3,3], atol=1e-7))
        self.assertTrue(np.allclose(an, n@rotation_xyz(config['rotationDegreesXYZ']).T, atol=1e-7))
        self.assertTrue(np.array_equal(uv, au)); self.assertEqual(doc['materials'], new['materials'])
        self.assertEqual(binary, new_bin[:len(binary)])
        self.assertEqual(result['statureApplications'], 0); self.assertFalse(result['rigPilotAccepted'])
        self.assertTrue(result['diagnosticOnly']); self.assertFalse(result['productionAccepted'])

    def test_mirror_conjugates_opposite_target_frames_and_flips_winding(self):
        fitted_path, fitted = self.run_config(self.config(self.source, self.job), 'fit')
        config = self.config(Path(fitted['candidate']), fitted_path, 'mirror', 'bicepr')
        config.update(sourcePart='bicepl', planeOriginWorld=[.0005,0,0], planeNormalWorld=[1,0,0])
        _, result = self.run_config(config, 'mirror')
        doc, blob = read_glb(fitted['candidate']); p, _, _, _ = raw_corners(doc, blob)
        new, baked = read_glb(result['candidate']); ap, _, _, _ = raw_corners(new, baked)
        source_frame = np.asarray(fitted['attachmentWorld']); target_frame = np.asarray(result['attachmentWorld'])
        plane = np.asarray(result['reflectionWorld'])
        expected = ((np.c_[p.reshape(-1,3), np.ones(p.size//3)]@source_frame.T)@plane.T)[:,:3].reshape(p.shape)[:,[0,2,1]]
        actual = (np.c_[ap.reshape(-1,3), np.ones(ap.size//3)]@target_frame.T)[:,:3].reshape(p.shape)
        self.assertTrue(np.allclose(actual, expected, atol=1e-7))
        self.assertEqual(result['proof']['triangleCornerOrder'], [0,2,1])
        self.assertNotEqual(result['sourceToAttachmentLocal'][:3], np.diag([-1,1,1,1]).tolist()[:3])

    def test_runtime_scale_once_and_preserves_normal_uv(self):
        fitted_path, fitted = self.run_config(self.config(self.source, self.job), 'fit')
        _, runtime = self.run_config(self.config(Path(fitted['candidate']), fitted_path, 'runtime', space='runtime'), 'runtime')
        fp, fn, fu, _ = raw_corners(*read_glb(fitted['candidate']))
        rp, rn, ru, _ = raw_corners(*read_glb(runtime['candidate']))
        self.assertTrue(np.allclose(rp, fp*10/7, atol=1e-7)); self.assertTrue(np.array_equal(fn, rn))
        self.assertTrue(np.array_equal(fu, ru)); self.assertEqual(runtime['statureApplications'], 1)
        path = self.root/'runtime/geometry.json'
        with self.assertRaisesRegex(ValueError, 'coordinate space'):
            self.run_config(self.config(Path(runtime['candidate']), path, 'runtime', space='runtime'), 'double')

    def test_reject_changed_target_receipt_and_source(self):
        path, fitted = self.run_config(self.config(self.source, self.job), 'fit')
        config = self.config(Path(fitted['candidate']), path, 'runtime', space='runtime')
        target = target_fixture(); target['rig']['revision'] = 'revised'
        self.target.write_text(json.dumps(target)); config['targetContractSha256'] = contract.sha(self.target)
        with self.assertRaisesRegex(ValueError, 'rig revision'):
            self.run_config(config, 'changed')
        config = self.config(self.source, self.job); config['sourceSha256'] = 'wrong'
        with self.assertRaisesRegex(ValueError, 'Frozen input'):
            self.run_config(config, 'bad-source')

    def test_reject_wrong_pair_uncollected_source_and_nonpositive_scale(self):
        path, fitted = self.run_config(self.config(self.source, self.job), 'fit')
        config = self.config(Path(fitted['candidate']), path, 'mirror', 'footr'); config['sourcePart']='bicepl'
        with self.assertRaisesRegex(ValueError, 'opposite limb'):
            self.run_config(config, 'bad-pair')
        self.job.write_text(json.dumps({'state':'success', 'promptId':'different', 'outputs':[]}))
        with self.assertRaisesRegex(ValueError, 'collected generation'):
            self.run_config(self.config(self.source, self.job), 'bad-job')
        for factor in [0, -1, float('nan')]:
            config = self.config(self.source, self.job); config['uniformScale'] = factor
            with self.subTest(scale=factor), self.assertRaisesRegex(ValueError, 'Positive finite'):
                fit_matrix(config)

    def test_reject_unrecorded_controls_and_protect_reviewed_neighbours(self):
        neighbour = self.root/'accepted-neighbour.bin'; neighbour.write_bytes(b'protected')
        config = self.config(self.source,self.job)
        config['protectedInputs'] = {str(neighbour):contract.sha(neighbour)}
        _, result = self.run_config(config,'protected-fit')
        self.assertEqual(neighbour.read_bytes(),b'protected')
        self.assertIn(str(neighbour),result['frozenInputs'])
        neighbour.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'Frozen input'):
            self.run_config(config,'changed-neighbour')
        config = self.config(self.source,self.job); config['perAxisScale'] = [1,2,1]
        with self.assertRaisesRegex(ValueError,'Unknown or inapplicable'):
            self.run_config(config,'extra-controls')


if __name__ == '__main__': unittest.main()
