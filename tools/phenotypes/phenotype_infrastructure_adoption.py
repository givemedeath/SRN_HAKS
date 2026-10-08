"""Verify explicit infrastructure adoption declarations; never execute old helpers.

This companion does not change existing receipt validators or consume assets for
rendering/staging. Raw source digests remain authoritative. Enumerated old
Python helpers resolve to exact preservation copies. Schema2 additionally binds
external donor/reference claims to independently preserved worktree-relative copies. Git LF helper
representation is a separate proof and never normalizes model/material inputs.
"""
import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from types import MappingProxyType

import target_contract as contract

KIND = 'phenotype-infrastructure-adoption-proof'
OPERATION = 'historical-helper-source-location-rebinding-v1'
BINDING_KIND = 'phenotype-adopted-preparation-binding'
REQUEST_KIND = 'phenotype-adopted-preparation-request'
SAMPLERS = ('retarget.py', 'rig_controller_audit.py', 'rig_pose_audit.py',
            'target_contract.py', 'pose_preview_bridge.py', 'run_preparation.py')
CONSUMERS = ('resume-declaration', 'preparation-declaration')
CLOSURES = ('frozenInputs', 'sourceClosure')
PROOF_FIELDS = {'schemaVersion', 'kind', 'operation', 'adoptionApplications',
    'targetContract', 'targetId', 'rigRevision', 'coordinateSpace', 'originalBank',
    'historicalReceipts', 'helperMappings', 'preservationManifest', 'currentHelpers',
    'reconciliation', 'upstreamValidation', 'portableToolLock', 'runtimeToolchain', 'runtimeMigration',
    'unchangedAssets', 'originalReceiptsRewritten', 'historicalHelpersExecuted',
    'sourceAssetsChanged', 'approvalStateChanged'}


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def shape(value, fields, label):
    require(isinstance(value, dict) and set(value) == set(fields), 'Exact '+label+' fields required')


def canonical(value):
    require(isinstance(value, str) and Path(value).is_absolute(), 'Absolute declared source path required')
    return Path(value).resolve()


def digest(value):
    require(isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value), 'Exact raw SHA256 required')
    return value


def row(value):
    shape(value, ('path', 'sha256'), 'file pin')
    return canonical(value['path']), digest(value['sha256'])


def resolve_worktree_relative_pin(value, repo):
    """Resolve a canonical local metadata pin against an explicit checkout root."""
    repo = Path(repo).resolve()
    shape(value, ('path', 'sha256'), 'worktree-relative asset pin')
    relative = value['path']
    require(isinstance(relative, str) and relative and '\\' not in relative and ':' not in relative,
            'Canonical worktree-relative POSIX path required')
    pure = PurePosixPath(relative)
    require(not pure.is_absolute() and '..' not in pure.parts and pure.as_posix() == relative,
            'Canonical contained worktree-relative path required')
    physical = (repo / Path(*pure.parts)).resolve()
    require(physical.is_relative_to(repo), 'Worktree-relative copy escapes checkout')
    expected = digest(value['sha256'])
    require(physical.is_file() and sha(physical) == expected, 'Changed worktree-relative asset copy')
    return {'path': str(physical), 'sha256': expected}


def read_json(path):
    def unique(pairs):
        output = {}
        for key, value in pairs:
            require(key not in output, 'Duplicate JSON field: '+key)
            output[key] = value
        return output
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=unique)


def immutable(value):
    if isinstance(value, dict):
        return MappingProxyType({key: immutable(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(immutable(item) for item in value)
    return value


def plain(value):
    if isinstance(value, (dict, MappingProxyType)):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(item) for item in value]
    return value


@dataclass(frozen=True)
class VerifiedAdoption:
    proof: object
    inputs: object
    receiptClosures: object
    helperResolutions: object
    samplerRepresentations: object
    assetResolutions: object = ()

    def verify(self):
        for path, expected in self.inputs.items():
            require(sha(path) == expected, 'Adoption input changed: '+path)


def verify_proof(proof_pin, *, repo=None):
    """Verify one explicitly pinned declaration. No fallback or archive imports."""
    repo = Path(repo or Path(__file__).resolve().parents[2]).resolve()
    bank = repo/'tools'/'phenotypes'
    inputs = {}

    def pin(value):
        path, expected = row(value)
        prior = inputs.get(str(path))
        require(prior is None or prior == expected, 'Conflicting adoption input digest: '+str(path))
        if prior is None:
            require(path.is_file() and sha(path) == expected, 'Changed adoption input: '+str(path))
            inputs[str(path)] = expected
        return path

    proof_path = pin(proof_pin)
    proof = read_json(proof_path)
    version = proof.get('schemaVersion')
    require(type(version) is int and version in (1, 2), 'Supported adoption proof schema required')
    shape(proof, PROOF_FIELDS | ({'assetSourceMappings'} if version == 2 else set()), 'adoption proof')
    require(proof['kind'] == KIND
            and proof['operation'] == OPERATION and type(proof['adoptionApplications']) is int
            and proof['adoptionApplications'] == 1, 'One explicit infrastructure adoption required')
    for key in ('originalReceiptsRewritten', 'historicalHelpersExecuted', 'sourceAssetsChanged', 'approvalStateChanged'):
        require(proof[key] is False, 'Adoption cannot change history, assets, execution or approvals: '+key)
    target_path = pin(proof['targetContract'])
    target = contract.load(target_path)
    require(proof['targetId'] == target['id'] and proof['rigRevision'] == target['rig']['revision']
            and proof['coordinateSpace'] in ('working', 'runtime'), 'Adoption target/rig/space differs')
    for path, expected in target.get('frozenInputs', {}).items():
        pin({'path': path, 'sha256': expected})

    if contract.rig_mode(target) == 'stock-exact':
        stock_path = pin(target['rig']['stockReferenceReceipt'])
        for path, expected in read_json(stock_path)['frozenInputs'].items():
            pin({'path': path, 'sha256': expected})

    manifest_path = pin(proof['preservationManifest'])
    manifest = read_json(manifest_path)
    require(manifest.get('kind') == 'pre-main-adoption-recoverable-byte-copy'
            and manifest.get('copiesIndependentlyHashVerified') is True
            and manifest.get('sourceWorktreeResetOrClean') is False,
            'Recoverable independently verified preservation manifest required')
    require(manifest_path.is_relative_to(repo) and isinstance(manifest.get('files'), list)
            and isinstance(manifest.get('helperHashes'), dict), 'Local explicit preservation rows required')
    preserved = {}
    for item in manifest['files']:
        shape(item, ('source', 'relative', 'copy', 'size', 'sha256', 'role'), 'preservation row')
        source = canonical(item['source'])
        require(source.is_relative_to(repo) and item['relative'] == source.relative_to(repo).as_posix(),
                'Preserved source escapes this checkout or has wrong relative identity')
        require(str(source) not in preserved, 'Duplicate preserved source')
        require(type(item['size']) is int and item['size'] >= 0, 'Literal preservation byte count required')
        digest(item['sha256'])
        require(item['role'] in ('modifiedTracked', 'untracked', 'ignoredAssetOrEvidence'), 'Unknown preservation role')
        preserved[str(source)] = item

    mappings = {}
    require(isinstance(proof['helperMappings'], list), 'Explicit helper mapping list required')
    resolutions = []
    for item in proof['helperMappings']:
        shape(item, ('originalClaimedSource', 'actualArchivedSourcePath', 'archivedCopy', 'size'), 'helper mapping')
        original, expected = row(item['originalClaimedSource'])
        require(original.parent == bank and original.suffix == '.py'
                and manifest['helperHashes'].get(str(original)) == expected,
                'Only exact recorded old helpers under this checkout may map')
        require(str(original) not in mappings, 'Duplicate historical helper mapping')
        archived_source = canonical(item['actualArchivedSourcePath'])
        require(archived_source.is_relative_to(repo) and archived_source.name == original.name
                and archived_source.suffix == '.py' and str(archived_source) in preserved,
                'Explicit same-basename local historical helper source required')
        saved = preserved[str(archived_source)]
        archive, archive_digest = row(item['archivedCopy'])
        require(item['actualArchivedSourcePath'] == saved['source'] and item['archivedCopy']['path'] == saved['copy']
                and archive_digest == saved['sha256'] == expected and type(item['size']) is int
                and item['size'] == saved['size'], 'Archive association differs from exact preservation row')
        require(archive.parent == manifest_path.parent/'files' and re.fullmatch(r'[0-9]{8}\.bin', archive.name),
                'Archive must be a flat preservation copy inside its declared root')
        pin(item['archivedCopy'])
        require(archive.stat().st_size == saved['size'], 'Archived helper byte count differs')
        mappings[str(original)] = (expected, str(archive))
        resolutions.append({'originalClaimedSource': item['originalClaimedSource'],
                            'actualArchivedSourcePath': saved['source'], 'archivedCopy': item['archivedCopy'],
                            'byteCount': saved['size'], 'executed': False})

    asset_resolutions = []
    if version == 2:
        require(isinstance(proof['assetSourceMappings'], list) and proof['assetSourceMappings'],
                'Explicit external source mapping list required')
        for item in proof['assetSourceMappings']:
            shape(item, ('originalClaimedSource', 'worktreeRelativeCopy'), 'external asset source mapping')
            claim = item['originalClaimedSource']
            shape(claim, ('path', 'sha256'), 'external original source claim')
            require(isinstance(claim['path'], str) and Path(claim['path']).is_absolute()
                    and '..' not in Path(claim['path']).parts, 'Absolute literal original source claim required')
            # Historical origin is a lexical identity, never a filesystem input.
            original, expected = Path(claim['path']), digest(claim['sha256'])
            require(not original.is_relative_to(repo) and original.suffix.lower() in ('.glb', '.png'),
                    'Only external donor GLB or reference PNG claims may map')
            require(str(original) not in mappings, 'Duplicate historical source mapping')
            relative_pin = item['worktreeRelativeCopy']
            physical_pin = resolve_worktree_relative_pin(relative_pin, repo)
            physical = Path(physical_pin['path'])
            require(physical.suffix.lower() == original.suffix.lower(), 'Mapped copy changes asset type')
            saved = preserved.get(str(physical))
            require(saved is not None and saved['sha256'] == expected == digest(relative_pin['sha256']),
                    'Local copy must match independently preserved original raw digest')
            physical_pin = {'path': str(physical), 'sha256': expected}
            pin(physical_pin)
            archive = pin({'path': saved['copy'], 'sha256': saved['sha256']})
            require(archive.parent == manifest_path.parent/'files'
                    and re.fullmatch(r'[0-9]{8}\.bin', archive.name)
                    and archive.stat().st_size == physical.stat().st_size == saved['size'],
                    'Exact flat preserved asset copy and byte count required')
            mappings[str(original)] = (expected, str(physical))
            asset_resolutions.append({'originalClaimedSource': item['originalClaimedSource'],
                'worktreeRelativeCopy': relative_pin, 'resolvedCopy': physical_pin,
                'preservedCopy': {'path': str(archive), 'sha256': expected},
                'originalRequired': False, 'sourceBytesChanged': False})

    original_bank_path = pin(proof['originalBank'])
    original_bank = read_json(original_bank_path)
    require(original_bank.get('kind') == 'unselected-fourteen-part-working-diagnostic-bank'
            and original_bank.get('target') == proof['targetContract']
            and set(original_bank.get('parts', {})) == contract.BODY_PARTS, 'Exact target fourteen-part bank required')
    require(manifest.get('authority', {}).get(str(original_bank_path)) == proof['originalBank']['sha256']
            and manifest.get('authority', {}).get(str(target_path)) == proof['targetContract']['sha256'],
            'Original bank/target must match preservation authority')
    require(isinstance(proof['unchangedAssets'], list), 'Explicit unchanged asset pins required')
    unchanged = {}
    for asset in proof['unchangedAssets']:
        path = pin(asset)
        require(str(path) not in unchanged, 'Duplicate unchanged asset pin')
        unchanged[str(path)] = asset['sha256']
    geometries = set()
    for part, item in original_bank['parts'].items():
        shape(item, ('geometry', 'candidate'), 'bank part')
        candidate = pin(item['candidate']); receipt = pin(item['geometry']); geometries.add(str(receipt))
        for file in (item['candidate'], item['geometry']):
            require(unchanged.get(str(canonical(file['path']))) == file['sha256'], 'Bank asset missing unchanged declaration')
        geometry = read_json(receipt)
        require(geometry.get('kind') == 'target-part-geometry' and geometry.get('schemaVersion') == 2,
                'Original bank part must retain its actual geometry receipt')
        contract.verify_binding(geometry, target_path, target, proof['coordinateSpace'])
        require(geometry['part'] == part and geometry['joint'] == contract.PART_JOINTS[part]
                and geometry['model'] == contract.model(target, part)
                and canonical(geometry['candidate']) == candidate and geometry['candidateSha256'] == item['candidate']['sha256']
                and geometry['attachmentWorld'] == target['rig']['frames'][proof['coordinateSpace']][geometry['joint']]
                and type(geometry['statureApplications']) is int
                and geometry['statureApplications'] == (0 if proof['coordinateSpace'] == 'working' else 1),
                'Historical candidate/attachment/space/conversion association differs')

    used = set(); closures = {}; receipts = set()
    require(isinstance(proof['historicalReceipts'], list) and proof['historicalReceipts'], 'Enumerated historical receipts required')
    for item in proof['historicalReceipts']:
        shape(item, ('receipt', 'kind', 'closures'), 'historical receipt declaration')
        path = pin(item['receipt']); name = str(path)
        require(name not in receipts, 'Duplicate historical receipt declaration'); receipts.add(name)
        value = read_json(path)
        require(value.get('kind') == item['kind'] and item['kind'] not in (KIND, BINDING_KIND, REQUEST_KIND),
                'Historical receipt kind differs or repeated adoption requested')
        if 'targetId' in value:
            contract.verify_binding(value, target_path, target, proof['coordinateSpace'])
        require(isinstance(item['closures'], list) and item['closures']
                and len(set(item['closures'])) == len(item['closures']) and set(item['closures']) <= set(CLOSURES),
                'Only declared historical frozen/source closure fields supported')
        for field in item['closures']:
            claims = value.get(field)
            require(isinstance(claims, dict) and claims, 'Original declared closure absent')
            resolved = {}
            for claimed_path, claimed_digest in claims.items():
                require(isinstance(claimed_path, str) and Path(claimed_path).is_absolute(),
                        'Absolute literal historical closure claim required')
                digest(claimed_digest); original_key = str(Path(claimed_path))
                if original_key in mappings:
                    expected, archive = mappings[original_key]
                    require(claimed_digest == expected, 'Original closure digest cannot be replaced')
                    resolved[archive] = expected; used.add(original_key)
                else:
                    physical = pin({'path': claimed_path, 'sha256': claimed_digest})
                    resolved[str(physical)] = claimed_digest
            closures[(name, field)] = resolved
    require(str(original_bank_path) in receipts and geometries <= receipts,
            'Original bank and every geometry receipt must be explicitly declared')
    require(used == set(mappings), 'Unused or undeclared historical source mapping')

    require(isinstance(proof['currentHelpers'], dict) and proof['currentHelpers'], 'Current execution helper pins required')
    for name, expected in proof['currentHelpers'].items():
        path = pin({'path': name, 'sha256': expected})
        require(path.parent == bank and path.suffix == '.py', 'Current helper must belong to this checkout')
    reconciliation_path = pin(proof['reconciliation']); reconciliation = read_json(reconciliation_path)
    require(reconciliation.get('kind') == 'phenotype-infrastructure-feature-reconciliation'
            and reconciliation.get('schemaVersion') == 1 and reconciliation.get('targetId') == proof['targetId']
            and reconciliation.get('upstreamCommit') == manifest.get('mergedBase')
            and set(reconciliation.get('helpers', {})) == set(proof['currentHelpers']), 'Exact target/current helper reconciliation required')
    for name, item in reconciliation['helpers'].items():
        shape(item, ('sha256', 'features'), 'reconciled helper')
        require(item['sha256'] == proof['currentHelpers'][name] and isinstance(item['features'], list)
                and item['features'] and all(isinstance(feature, str) and feature.strip() for feature in item['features']),
                'Current helper hash and concrete feature notes required')
    validation_path = pin(proof['upstreamValidation']); validation = read_json(validation_path)
    require(validation_path == repo/'docs'/'shared-tool-validation.json', 'Pinned upstream validation record required')
    benchmark = validation.get('boundBenchmarkHelperHashes', {})
    require(set(benchmark) == set(SAMPLERS), 'Exact six-helper committed benchmark closure required')
    representations = {}
    for name, expected in benchmark.items():
        path = bank/name
        require(str(path) in proof['currentHelpers'], 'Current sampler absent from adoption helper pins')
        raw = path.read_bytes(); committed = raw.replace(b'\r\n', b'\n')
        require(hashlib.sha256(raw).hexdigest() == proof['currentHelpers'][str(path)]
                and hashlib.sha256(committed).hexdigest() == digest(expected), 'Committed sampler bytes differ from upstream closure')
        representations[name] = {'actualRawSha256': proof['currentHelpers'][str(path)],
            'committedLfSha256': expected, 'rawEqualsCommittedBytes': raw == committed,
            'policy': 'git-text-crlf-to-lf-committed-representation-only', 'runtimeBenchmarkIdentityClaimed': False}

    lock_path = pin(proof['portableToolLock'])
    require(lock_path == repo/'tools'/'shared-tools.lock.json', 'Exact current portable tool lock required')
    runtime_path = pin(proof['runtimeToolchain']); migration_path = pin(proof['runtimeMigration'])
    runtime = read_json(runtime_path)
    require(runtime.get('schemaVersion') == 2 and runtime.get('kind') == 'phenotype-shared-toolchain',
            'Fresh schema2 local runtime binding required')
    migration = read_json(migration_path)
    require(migration.get('kind') == 'phenotype-shared-tool-migration' and migration.get('smokeChecksPassed') is True
            and migration.get('toolchain') == proof['runtimeToolchain'], 'Fresh successful migration must bind exact runtime bytes')
    from shared_toolchain import load
    resolved_runtime = load(runtime_path, migration_path)
    for tool in resolved_runtime['tools'].values():
        pin({'path': tool['path'], 'sha256': tool['sha256']})
    for name, value in migration.get('launchHelpers', {}).items():
        pin({'path': name, 'sha256': value['sha256']})
    if resolved_runtime.get('addons'):
        for name, expected in resolved_runtime['addons']['files'].items():
            pin({'path': str(Path(resolved_runtime['addons']['root'])/name), 'sha256': expected})
    result = VerifiedAdoption(immutable(proof), immutable(inputs), immutable(closures),
                             immutable(resolutions), immutable(representations), immutable(asset_resolutions))
    result.verify()
    return result


def declare_preparation(request_pin, output, *, repo=None):
    """Write a fresh declaration only. Ordinary asset consumers remain unchanged."""
    request_path, expected = row(request_pin)
    require(sha(request_path) == expected, 'Preparation request changed')
    request = read_json(request_path)
    shape(request, ('schemaVersion', 'kind', 'proof', 'targetContract', 'targetId', 'rigRevision',
                    'coordinateSpace', 'originalBank', 'consumer', 'preparationInputs'), 'preparation request')
    require(type(request['schemaVersion']) is int and request['schemaVersion'] == 1 and request['kind'] == REQUEST_KIND
            and request['consumer'] in CONSUMERS, 'Explicit declaration-only consumer required')
    adoption = verify_proof(request['proof'], repo=repo)
    for key in ('targetContract', 'targetId', 'rigRevision', 'coordinateSpace', 'originalBank'):
        require(request[key] == adoption.proof[key], 'Adopted preparation target/source/space differs: '+key)
    inputs = dict(adoption.inputs); inputs[str(request_path)] = expected
    require(isinstance(request['preparationInputs'], list), 'Explicit future preparation inputs required')
    for item in request['preparationInputs']:
        path, value = row(item)
        require(str(path) not in inputs or inputs[str(path)] == value, 'Future input cannot replace adopted source digest')
        require(path.is_file() and sha(path) == value, 'Future declared preparation input changed')
        inputs[str(path)] = value
    for path, value in inputs.items():
        require(sha(path) == value, 'Input changed during preparation declaration')
    receipt = {'schemaVersion': 1, 'kind': BINDING_KIND, 'adoptionApplications': 1,
        **{key: request[key] for key in ('proof', 'targetContract', 'targetId', 'rigRevision', 'coordinateSpace', 'originalBank', 'consumer')},
        'request': request_pin, 'resolvedInputs': inputs,
        'historicalHelperResolutions': plain(adoption.helperResolutions),
        **({'historicalAssetResolutions': plain(adoption.assetResolutions),
            'originalExternalFilesRequired': False} if adoption.assetResolutions else {}),
        'upstreamSamplerRepresentations': plain(adoption.samplerRepresentations),
        'operations': [], 'consumerExecutionSupported': False, 'historicalHelpersExecuted': False,
        'originalReceiptsRewritten': False, 'sourceAssetsChanged': False, 'approvalStateChanged': False,
        'runtimeBenchmarkIdentityClaimed': False}
    output = Path(output).resolve()
    with output.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(receipt, indent=2)+'\n')
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--request-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    declare_preparation({'path': str(args.request.resolve()), 'sha256': args.request_sha256}, args.output)
    print(json.dumps({'declaration': str(args.output.resolve()), 'sha256': sha(args.output), 'consumerExecuted': False}))
