"""Published-body verification: derived single-PLT closure per prefix; historical male v1 manifest unchanged."""
import hashlib
import json
from pathlib import Path
import subprocess
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


REPO = Path(__file__).resolve().parents[2]
EVIDENCE = 'docs/phenotypes/evidence/human-body-completion-v1'


def committed_bytes(rel):
    """Bytes of a tracked file as stored in git (index == commit), so eol=lf checkouts and CRLF work trees agree."""
    try:
        return subprocess.run(['git', '-C', str(REPO), 'show', ':' + rel], capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):  # source export without git: normalise like eol=lf
        data = (REPO / rel).read_bytes()
        return data if b'\0' in data else data.replace(b'\r\n', b'\n')


def committed_sha(rel):
    return hashlib.sha256(committed_bytes(rel)).hexdigest()


def pins(node):
    """Every {path, sha256} pin inside a JSON document that names an existing repository file."""
    if isinstance(node, dict):
        if isinstance(node.get('path'), str) and isinstance(node.get('sha256'), str) and (REPO / node['path']).is_file():
            yield node
        for value in node.values():
            yield from pins(value)
    elif isinstance(node, list):
        for value in node:
            yield from pins(value)


class CommittedEvidencePinTests(unittest.TestCase):
    """Pins over tracked text must hash the committed (LF) blob, never CRLF working-tree bytes (PR #42 review)."""
    MANIFESTS = ('docs/phenotypes/human-female-assets.json', 'docs/phenotypes/human-male-v2-assets.json')

    def test_publication_manifests_pin_committed_evidence_bytes(self):
        for rel in self.MANIFESTS:
            with self.subTest(manifest=rel):
                manifest = json.loads(committed_bytes(rel))
                self.assertEqual(committed_sha(manifest['sourceBodyReceipt']), manifest['sourceBodyReceiptSha256'])
                self.assertEqual(committed_sha(manifest['clientEvidence']), manifest['clientEvidenceSha256'])
                self.assertTrue(manifest['productionAccepted'] is True and 'final-user-approved' in manifest['status'])

    def test_evidence_index_ledger_and_heads_pin_committed_bytes(self):
        index = json.loads(committed_bytes(EVIDENCE + '/index.json'))
        for name, row in index['files'].items():
            data = committed_bytes(EVIDENCE + '/' + name)
            self.assertEqual((hashlib.sha256(data).hexdigest(), len(data)), (row['sha256'], row['bytes']), name)
        for rel in (EVIDENCE + '/index.json', EVIDENCE + '/human-male-v2-delivery.json', 'docs/heads/human-male-target.json'):
            for pin in pins(json.loads(committed_bytes(rel))):
                if pin['path'].startswith(('srn_body/', 'stock/')):
                    continue
                self.assertEqual(committed_sha(pin['path']), pin['sha256'], rel + ' -> ' + pin['path'])
        target = json.loads(committed_bytes('docs/heads/human-male-target.json'))
        self.assertEqual(target['bodyRevision'], committed_sha('docs/phenotypes/human-male-v2-assets.json'))

    def test_quoted_manifest_hashes_in_closure_docs_are_current(self):
        for manifest in self.MANIFESTS:
            current = committed_sha(manifest)
            for doc in ('docs/phenotype-human-female-source-adoption-checkpoint.md', 'docs/phenotype-human-male-delivery.md'):
                text = committed_bytes(doc).decode('utf-8')
                if manifest.rsplit('/', 1)[1] in text:
                    self.assertTrue(current in text or current[:12] + '...' in text, doc + ' quotes a stale ' + manifest)


if __name__ == '__main__':
    unittest.main()
