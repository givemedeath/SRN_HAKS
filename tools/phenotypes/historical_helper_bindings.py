"""Verify creation-helper provenance after infrastructure adoption.

Historical snapshots are data for hash checks. This module never imports or
executes them, rewrites a receipt, or grants asset acceptance.
"""
import hashlib
import json
import os
from pathlib import Path
import re


ENV_PATH = 'SRN_HISTORICAL_HELPER_BINDINGS'
ENV_SHA256 = 'SRN_HISTORICAL_HELPER_BINDINGS_SHA256'


def _sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _pin(value, label):
    _require(isinstance(value, dict) and set(value) == {'path', 'sha256'},
             label + ' requires an explicit path/hash pin')
    _require(isinstance(value['path'], str) and bool(value['path'])
             and isinstance(value['sha256'], str)
             and re.fullmatch(r'[a-f0-9]{64}', value['sha256']) is not None,
             label + ' has an invalid path/hash pin')
    return Path(value['path']).resolve(), value['sha256']


def validate_manifest(pin, repo):
    """Return verified manifest and its actual consumed provenance file paths."""
    repo = Path(repo).resolve()
    path, expected = _pin(pin, 'Historical helper manifest')
    _require(path.is_relative_to(repo), 'Historical helper manifest escaped consuming worktree')
    _require(_sha(path) == expected, 'Historical helper manifest changed')
    manifest = json.loads(path.read_text(encoding='utf-8'))
    _require(isinstance(manifest, dict) and manifest.get('schemaVersion') == 1
             and manifest.get('kind') == 'historical-creation-helper-bindings',
             'Historical creation-helper manifest required')
    _require(isinstance(manifest.get('activeWorktree'), str)
             and Path(manifest['activeWorktree']).resolve() == repo,
             'Historical helper manifest belongs to another worktree')
    contract, contract_hash = _pin(manifest.get('targetContract'), 'Target contract')
    _require(contract.is_relative_to(repo), 'Historical target contract escaped consuming worktree')
    _require(_sha(contract) == contract_hash, 'Historical target contract changed')
    entries = manifest.get('entries')
    _require(isinstance(entries, list) and bool(entries), 'Historical helper entries required')
    helper_root = (repo / 'tools' / 'phenotypes').resolve()
    _require(helper_root.is_relative_to(repo), 'Phenotype helper directory escaped consuming worktree')
    consumed = [path, contract]
    seen = set()
    for entry in entries:
        _require(isinstance(entry, dict) and set(entry) == {'source', 'snapshot'},
                 'Historical helper entry requires source and snapshot pins')
        source, source_hash = _pin(entry['source'], 'Historical source helper')
        snapshot, snapshot_hash = _pin(entry['snapshot'], 'Historical helper snapshot')
        _require(source.parent == helper_root and source.suffix == '.py' and source.is_file(),
                 'Historical source must be a consuming-worktree phenotype Python helper')
        _require(snapshot.is_relative_to(repo) and snapshot.suffix == '.py' and snapshot.is_file(),
                 'Historical helper snapshot escaped consuming worktree or is not Python helper data')
        _require(source_hash == snapshot_hash, 'Historical helper source/snapshot hashes differ')
        _require(_sha(snapshot) == snapshot_hash, 'Historical helper snapshot changed')
        identity = (source, source_hash)
        _require(identity not in seen, 'Duplicate historical helper mapping')
        seen.add(identity)
        consumed.append(snapshot)
    # Current source helpers are frozen separately by the launcher/caller. Their
    # present bytes can differ from this immutable creation-helper provenance.
    return manifest, list(dict.fromkeys(consumed))


def resolve(path, expected):
    """Resolve only an exact helper hash; historical fallback is provenance data."""
    source = Path(path).resolve()
    _require(isinstance(expected, str) and re.fullmatch(r'[a-f0-9]{64}', expected) is not None,
             'Expected helper SHA256 required')
    if source.is_file() and _sha(source) == expected:
        return source
    manifest_path = os.environ.get(ENV_PATH)
    manifest_hash = os.environ.get(ENV_SHA256)
    _require(bool(manifest_path) and bool(manifest_hash),
             'Changed creation helper requires explicit historical helper bindings')
    repo = Path(__file__).resolve().parents[2]
    manifest, _ = validate_manifest({'path': manifest_path, 'sha256': manifest_hash}, repo)
    for entry in manifest['entries']:
        if Path(entry['source']['path']).resolve() == source and entry['source']['sha256'] == expected:
            return Path(entry['snapshot']['path']).resolve()
    raise ValueError('No exact historical creation-helper mapping: ' + str(source))
