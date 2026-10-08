"""Explicit source validation against a pinned infrastructure-adoption proof.

Historical helpers are inert bytes. This API neither rewrites receipts nor
extends CLI, rendering, staging, compilation or material-calibration callers.
Unadapted consumers retain their original literal source checks.
"""
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

import phenotype_infrastructure_adoption as adoption
import target_contract as contract

CONSUMERS = MappingProxyType({
    'target_part_pipeline.verify_source_receipt': 'target_part_pipeline.py',
    'pose_preview_target_parts.select_receipts': 'pose_preview_target_parts.py',
    'replay_stage_skin_intensity.source_receipt': 'replay_stage_skin_intensity.py',
})
_SEAL = object()


@dataclass(frozen=True, init=False)
class ExecutionAdoption:
    """Factory-created, immutable, exact receipt/consumer scope."""
    _seal: object
    _verified: object
    _consumer: str
    _module: str
    _target: object
    _space: str
    _receipts: object
    _closures: object
    _lineage: object
    _proof_pin: object

    def verify(self):
        adoption.require(getattr(self, '_seal', None) is _SEAL, 'Unverified execution adoption context')
        self._verified.verify()

    def evidence(self):
        """Separate physical lineage; no fields are added to original receipts."""
        self.verify()
        return adoption.immutable({
            'schemaVersion': 1, 'kind': 'phenotype-execution-adoption-context',
            'operation': 'explicit-frozen-source-resolution-v1',
            'proof': adoption.plain(self._proof_pin), 'consumer': self._consumer,
            'consumerModule': {'path': self._module,
                'sha256': self._verified.proof['currentHelpers'][self._module]},
            'targetContract': adoption.plain(self._target),
            'targetId': self._verified.proof['targetId'],
            'rigRevision': self._verified.proof['rigRevision'],
            'coordinateSpace': self._space, 'adoptionApplications': 1,
            'receiptPins': adoption.plain(self._receipts),
            'sourceResolutions': adoption.plain(self._lineage),
            'verificationInputs': adoption.plain(self._verified.inputs),
            'originalReceiptsRewritten': False, 'historicalHelpersExecuted': False,
            'sourceAssetsChanged': False, 'approvalStateChanged': False,
            'assetOperations': [],
        })


def prepare_execution_adoption(proof_pin, *, target_path, target, space,
                               consumer, receipt_pins):
    """Bind a named current validator to explicitly requested geometry receipts.

    Consumer module paths are derived here from this checkout, never supplied
    by a request. The controlled callsite supplies its own __file__ again when
    resolving a closure. Existing proof verification remains unchanged.
    """
    adoption.require(consumer in CONSUMERS, 'Unsupported execution adoption consumer')
    adoption.require(space in ('working', 'runtime'), 'Explicit execution coordinate space required')
    adoption.require(isinstance(receipt_pins, (list, tuple)) and receipt_pins,
                     'Explicit nonempty requested receipt pins required')
    repo = Path(__file__).resolve().parents[2]
    module = str(repo/'tools'/'phenotypes'/CONSUMERS[consumer])
    verified = adoption.verify_proof(proof_pin, repo=repo)
    proof = verified.proof
    target_path = Path(target_path).resolve()
    target_pin = {'path': str(target_path), 'sha256': contract.sha(target_path)}
    adoption.require(target_pin == adoption.plain(proof['targetContract'])
                     and target == contract.load(target_path)
                     and target['id'] == proof['targetId']
                     and target['rig']['revision'] == proof['rigRevision']
                     and space == proof['coordinateSpace'],
                     'Execution adoption target/rig/space differs')
    for path in (str(Path(__file__).resolve()), module):
        adoption.require(path in proof['currentHelpers']
                         and contract.sha(path) == proof['currentHelpers'][path],
                         'Execution helper absent or stale in explicit currentHelpers: '+path)
    declared = {str(adoption.row(adoption.plain(row['receipt']))[0]): row
                for row in proof['historicalReceipts']}
    mappings = {}
    for row in verified.helperResolutions:
        claim = row['originalClaimedSource']
        mappings[str(Path(claim['path']))] = ('historical-helper', row['archivedCopy'], row)
    for row in verified.assetResolutions:
        claim = row['originalClaimedSource']
        mappings[str(Path(claim['path']))] = ('external-source-copy', row['resolvedCopy'], row)
    requested = {}; closures = {}; lineage = {}
    for requested_pin in receipt_pins:
        receipt_path, digest = adoption.row(requested_pin)
        name = str(receipt_path)
        adoption.require(name not in requested, 'Duplicate requested execution receipt')
        declaration = declared.get(name)
        adoption.require(declaration is not None
                         and digest == declaration['receipt']['sha256']
                         and declaration['kind'] == 'target-part-geometry'
                         and 'frozenInputs' in declaration['closures'],
                         'Requested geometry receipt/closure absent from exact proof')
        receipt = adoption.read_json(receipt_path)
        adoption.require(receipt.get('schemaVersion') == 2
                         and receipt.get('kind') == 'target-part-geometry',
                         'Only untreated target geometry receipts support execution adoption')
        contract.verify_binding(receipt, target_path, target, space)
        part = receipt.get('part')
        adoption.require(part in contract.BODY_PARTS
                         and receipt['joint'] == contract.PART_JOINTS[part]
                         and receipt['model'] == contract.model(target, part)
                         and receipt['attachmentWorld'] == target['rig']['frames'][space][receipt['joint']]
                         and type(receipt['statureApplications']) is int
                         and receipt['statureApplications'] == (0 if space == 'working' else 1),
                         'Execution receipt ownership/frame/conversion differs')
        claims = receipt['frozenInputs']; physical = {}; rows = []
        adoption.require(str(target_path) in claims and claims[str(target_path)] == target_pin['sha256'],
                         'Execution closure must pin the exact target')
        for key in ('source', 'sourceReceipt'):
            claim = str(Path(receipt[key]))
            adoption.require(claim in claims and claims[claim] == receipt[key+'Sha256'],
                             'Execution source provenance missing from original closure: '+key)
        for claimed_path, claimed_digest in claims.items():
            original = str(Path(claimed_path)); mapping = mappings.get(original)
            if mapping is None:
                pin = {'path': str(Path(claimed_path).resolve()), 'sha256': claimed_digest}
                kind = 'literal'; proof_row = None
            else:
                kind, mapped, proof_row = mapping; pin = adoption.plain(mapped)
                adoption.require(pin['sha256'] == claimed_digest,
                                 'Original execution closure digest cannot be replaced')
            prior = physical.get(pin['path'])
            adoption.require(prior is None or prior == claimed_digest, 'Conflicting execution physical pin')
            physical[pin['path']] = claimed_digest
            rows.append({'originalClaimedSource': {'path': claimed_path, 'sha256': claimed_digest},
                         'physicalSource': pin, 'resolution': kind,
                         'mappingEvidence': adoption.plain(proof_row), 'historicalHelperExecuted': False})
        adoption.require(physical == adoption.plain(verified.receiptClosures[(name, 'frozenInputs')]),
                         'Execution closure differs from independently verified proof')
        requested[name] = {'path': name, 'sha256': digest}
        closures[name] = {'original': receipt, 'resolved': physical}
        lineage[name] = rows
    result = object.__new__(ExecutionAdoption)
    for key, value in dict(_seal=_SEAL, _verified=verified, _consumer=consumer, _module=module,
                          _target=adoption.immutable(target_pin), _space=space,
                          _receipts=adoption.immutable(requested), _closures=adoption.immutable(closures),
                          _lineage=adoption.immutable(lineage), _proof_pin=adoption.immutable(dict(proof_pin))).items():
        object.__setattr__(result, key, value)
    result.verify()
    return result


def resolve_frozen_inputs(context, *, module_file, consumer, receipt_path,
                          receipt, target_path, target, space):
    """Controlled validator boundary; returns physical pins and separate lineage."""
    adoption.require(type(context) is ExecutionAdoption, 'Verified explicit execution adoption context required')
    context.verify()
    adoption.require(consumer in CONSUMERS and consumer == context._consumer
                     and str(Path(module_file).resolve()) == context._module,
                     'Execution adoption belongs to another controlled consumer/module')
    target_path = Path(target_path).resolve()
    adoption.require({'path': str(target_path), 'sha256': contract.sha(target_path)}
                     == adoption.plain(context._target)
                     and target == contract.load(target_path) and space == context._space,
                     'Execution consumer target/rig/space differs')
    name = str(Path(receipt_path).resolve())
    adoption.require(name in context._receipts, 'Receipt outside requested execution scope')
    adoption.require(contract.sha(name) == context._receipts[name]['sha256']
                     and receipt == adoption.plain(context._closures[name]['original']),
                     'Original execution receipt or closure changed')
    resolved = adoption.plain(context._closures[name]['resolved'])
    for path, digest in resolved.items():
        adoption.require(contract.sha(path) == digest, 'Execution physical source changed: '+path)
    return resolved, adoption.plain(context._lineage[name])
