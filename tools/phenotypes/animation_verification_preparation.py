"""One exact all-family animation verification per run, with byte checks on reuse."""
import ast
from collections.abc import Mapping
import copy
from pathlib import Path

import target_contract as contract
from run_preparation import PreparationContext


def helper_closure():
    roots=(Path(__file__).parent,Path(__file__).parent.parent)
    pending=[Path(__file__).resolve(),Path(__file__).with_name('shared_female_animation_overlay.py')]
    seen=set()
    while pending:
        p=pending.pop()
        if p in seen:continue
        seen.add(p)
        for n in ast.walk(ast.parse(p.read_text(encoding='utf-8-sig'))):
            names=[a.name for a in n.names] if isinstance(n,ast.Import) else ([n.module] if isinstance(n,ast.ImportFrom) and n.module else [])
            for name in names:
                q=next((root/(name.split('.')[0]+'.py') for root in roots if (root/(name.split('.')[0]+'.py')).is_file()),None)
                if q:pending.append(q.resolve())
    return sorted(seen)


def thaw(value):
    if isinstance(value,Mapping):return {k:thaw(v) for k,v in value.items()}
    if isinstance(value,tuple):return [thaw(v) for v in value]
    return copy.deepcopy(value)


class AnimationVerificationPreparation:
    """Ephemeral preparation bound to one exact target and overlay, never a receipt waiver."""
    def __init__(self,receipt_pin,target_path):
        from shared_female_animation_overlay import require_target
        self.target_path=Path(target_path).resolve()
        target=contract.load(self.target_path);require_target(target,self.target_path)
        contract.require(isinstance(receipt_pin,dict) and set(receipt_pin)=={'path','sha256'},'Exact overlay pin required')
        self.receipt_pin=copy.deepcopy(receipt_pin)
        self.target_sha=contract.sha(self.target_path)
        contract.require(contract.sha(receipt_pin['path'])==receipt_pin['sha256'],'Stale prepared overlay pin')
        self.context=PreparationContext(target_revision=self.target_sha,rig_revision=target['rig']['revision'],
            animation_revision=receipt_pin['sha256'],settings={'operation':'all-family-native-animation-verification',
                'targetPath':str(self.target_path),'overlay':self.receipt_pin},
            dependencies=[self.target_path,Path(receipt_pin['path']),*helper_closure()])

    def verify(self,receipt_pin,target_path):
        from shared_female_animation_overlay import verify_shared_female_animation_overlay
        contract.require(receipt_pin==self.receipt_pin and Path(target_path).resolve()==self.target_path and
            contract.sha(self.target_path)==self.target_sha,'Cross-target, stale or foreign preparation')
        self.context.verify()
        def decode(_):
            # The unchanged full verifier runs before anything can enter the cache.
            report=verify_shared_female_animation_overlay(receipt_pin,self.target_path)
            for path,digest in report['frozenInputs'].items():
                _,actual=self.context.read(path)
                contract.require(actual==digest,'Verified overlay input drifted during preparation')
            self.context.verify()
            return report
        try:
            frozen=self.context.prepared(receipt_pin['path'],'all-family-native-overlay-verification',decode,
                settings={'targetSha256':self.target_sha,'receipt':self.receipt_pin})
            self.context.verify()
        except Exception:
            self.context.invalid=True
            raise
        report=thaw(frozen)
        report['frozenInputs'].update(self.context.inputs)
        return report

    def receipt(self):
        return self.context.receipt()
