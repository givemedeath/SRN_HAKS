"""Published-body verification: derived single-PLT closure per prefix; historical male v1 manifest unchanged."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from verify_published_body import HUMAN_PARTS, SINGLE_PLT_SUFFIXES, verify


def publish(root, prefix='pfh0', gender='female', drop=None, extra=None, kind='published-validated-target-body', other_owner=True):
    bank = root/'srn_body'; bank.mkdir(parents=True, exist_ok=True)
    names = sorted(prefix+'_'+part+'001'+suffix for part in HUMAN_PARTS for suffix in SINGLE_PLT_SUFFIXES)
    rows = []
    for name in names:
        data = ('bytes-'+name).encode(); (bank/name).write_bytes(data)
        if name != drop:
            rows.append({'path': 'srn_body/'+name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
    if extra: (bank/extra).write_bytes(b'stale')
    if other_owner: (bank/'pmh0_chest001.mdl').write_bytes(b'other owner')  # another target's resources share the pack
    hashes = {Path(row['path']).name: row['sha256'] for row in rows}
    (root/'source.json').write_text(json.dumps({'hakSha256': 'h'*64, 'resourceHashes': hashes}))
    (root/'client.json').write_text('{}')
    manifest = {'schemaVersion': 2 if kind.endswith('target-body') else 1, 'kind': kind, 'pack': 'srn_body',
                'prefix': prefix, 'gender': gender, 'materialLayout': 'single-plt-per-part-v1',
                'resources': rows, 'resourceCount': len(rows), 'payloadBytes': sum(row['bytes'] for row in rows),
                'sourceBodyReceipt': 'source.json', 'sourceBodyReceiptSha256': hashlib.sha256((root/'source.json').read_bytes()).hexdigest(),
                'clientEvidence': 'client.json', 'clientEvidenceSha256': hashlib.sha256(b'{}').hexdigest(), 'sourceBodyHakSha256': 'h'*64}
    path = root/'manifest.json'; path.write_text(json.dumps(manifest)); return path


class VerifyPublishedBodyTests(unittest.TestCase):
    def test_target_manifest_derives_seventy_and_scopes_ownership_to_its_prefix(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); result = verify(root, publish(root))
            self.assertEqual(result['resources'], 70); self.assertEqual(result['materialLayout'], 'single-plt-per-part-v1')
            self.assertEqual(result['prefix'], 'pfh0')

    def test_missing_or_stale_resources_are_rejected(self):
        for kwargs, message in (({'drop': 'pfh0_pelvis001r.tga'}, 'stale'), ({'extra': 'pfh0_pelvis001f.tga'}, 'stale'),
                                ({'extra': 'pfh0_pelviss1.plt'}, 'stale')):
            with self.subTest(kwargs=kwargs), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                with self.assertRaisesRegex(Exception, message):
                    verify(root, publish(root, **kwargs))

    def test_prefix_gender_and_layout_are_explicit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(Exception, 'prefix/gender'):
                verify(root, publish(root, gender='male'))

    def test_historical_male_manifest_keeps_its_exact_count(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(Exception, 'Incomplete body payload'):
                verify(root, publish(root, prefix='pmh0', gender='male', kind='published-validated-human-male-body', other_owner=False))


if __name__ == '__main__':
    unittest.main()
