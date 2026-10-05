"""Generate state from explicit current ledger bindings; never infer selections."""
import argparse
from pathlib import Path
from shared_toolchain import sha
from shared_tools import read_json,write_json

FIELDS=('partsBank','targetRevision','toolMigration','latestDirection','rejectedAlternatives','blockers','nextAction',
        'referenceApproval','workingSelection','nativeValidation','clientValidation','productionAcceptance')

def lookup(value,pointer):
    for key in pointer.strip('/').split('/'):
        key=key.replace('~1','/').replace('~0','~')
        value=value[int(key)] if isinstance(value,list) else value[key]
    return value

def summary(bindings_path):
    bindings=read_json(bindings_path);pin=bindings['ledger'];path=Path(pin['path']).resolve()
    if sha(path)!=pin['sha256']:raise ValueError('Stale ledger binding; reconcile current authority')
    ledger=read_json(path);selectors=bindings['selectors']
    if set(selectors)!=set(FIELDS):raise ValueError('Missing or unknown current ledger binding')
    values={}
    for field,pointers in selectors.items():
        if isinstance(pointers,str):pointers=[pointers]
        if not pointers:raise ValueError('Missing current binding: '+field)
        found=[lookup(ledger,pointer) for pointer in pointers]
        if any(value!=found[0] for value in found[1:]):raise ValueError('Conflicting ledger bindings: '+field)
        values[field]=found[0]
    direction=values['latestDirection']
    if not isinstance(direction,dict) or direction.get('superseded') or not direction.get('sequence'):
        raise ValueError('Explicit current, unsuperseded direction required')
    # Authoritative state must explicitly say which direction supersedes earlier instructions.
    if direction['sequence']!=ledger.get('currentDirectionSequence'):
        raise ValueError('Latest direction contradicts current ledger sequence')
    for pin in bindings.get('dependencies',[]):
        if sha(pin['path'])!=pin['sha256']:raise ValueError('Current dependency binding changed')
    return {'schemaVersion':1,'kind':'phenotype-resume-summary','bindings':{'path':str(Path(bindings_path).resolve()),'sha256':sha(bindings_path)},
        'ledger':{'path':str(path),'sha256':sha(path)},'current':values,'dependencyPins':bindings.get('dependencies',[]),
        'authority':'Ledger and later user instructions; this summary grants no approvals and changes no goal status'}

def verify_summary(path):
    report=read_json(path)
    if sha(report['bindings']['path'])!=report['bindings']['sha256'] or summary(report['bindings']['path'])!=report:
        raise ValueError('Stale resume summary; reconcile ledger before continuing')
    return report

def verify_integration(parent,protected_neighbors):
    for pin in [parent,*protected_neighbors]:
        if sha(pin['path'])!=pin['sha256']:raise ValueError('Stale parent/protected neighbor; integration rejected')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bindings',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();write_json(a.output,summary(a.bindings),fresh=True)
