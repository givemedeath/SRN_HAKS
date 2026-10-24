"""Item contracts around the same guarded Pixal engine used by headkit."""
from pathlib import Path
from tools.headkit.common import asset, bindings, pin, require, write, read, verify, digest
from tools.headkit.generation import prepare_request
from .contracts import all_pins, code_pins, family, manifest, source_version,stage_roles
from tools.headkit.reference_background import analyze_reference
from .conditioning import require_conditioning_review


def calibration_background_decision(manifest_path,data=None):
    data=manifest(manifest_path) if data is None else data
    return analyze_reference(asset(manifest_path,data['inputs'].get('geometry',data['inputs']['reference']))['path'])


def generation_manifest(path, *, roles=None):
    data = manifest(path,input_roles=roles,validate_native=False)
    # Detailed-only remains the default; a reviewed clay fallback is explicit.
    data['inputs'] = dict(data['inputs'])
    reference = data['inputs']['reference']
    data['inputs'].setdefault('geometry', reference)
    data['inputs'].setdefault('detail', reference)
    data['inputs'].setdefault('mask', reference)
    return data


def request_stage(manifest_path, bindings_path, stage, output, *, runtime, comfy_runtime):
    roles=stage_roles(stage) if stage!='export' else {'exportSource'}
    data = manifest(manifest_path,input_roles=roles,validate_native=False)
    local = bindings(bindings_path)
    shared_ledger(local)
    require(local.get('itemTrialId'), 'Bind the authorized item trial before dispatch')
    if stage in ('geometry', 'appearance'):
        require('geometry' in data['inputs'] and 'detail' in data['inputs'],
                'Import the reviewed normalized calibration image for both geometry and appearance')
        require_conditioning_review(manifest_path,data)
    profile = family(asset(manifest_path, data['familyProfile'])['path'],validate_native=False)
    return prepare_request(manifest_path, bindings_path, stage, output, runtime=runtime,
                           comfy_runtime=comfy_runtime, manifest_reader=lambda p:generation_manifest(p,roles=roles),
                           extra_pins=all_pins(manifest_path,roles=roles,native=False)+code_pins(), namespace='itemkit',
                           version=source_version(), export_settings=profile['sourceExport'] if stage == 'export' else None,
                           generation_subject={'id': data['id'], 'referenceSha256': asset(manifest_path, data['inputs']['reference'])['sha256']},
                           geometry_seed_offset=data.get('geometrySeedOffset', 0),
                           model_verification='server-owned-v1',
                           background=calibration_background_decision(manifest_path,data) if stage=='calibrate' else None)


def initialize_trial(path, trial_id, evidence):
    require(isinstance(trial_id,str) and bool(trial_id.strip()) and bool(evidence.strip()), 'Trial identity and user authorization required')
    write(path, {'schemaVersion': 1, 'priorGenerationAttempts': 0, 'reconciliation': evidence,
                 'itemTrial': {'id': trial_id, 'maximumGeometryAttempts': 5}, 'jobs': []}, fresh=True)


def set_trial_limit(path, trial_id, maximum, evidence, output):
    """Upgrade the existing trial under its submission lock, retaining all history."""
    from tools.headkit.comfy import locked
    require(type(maximum) is int and maximum == 5, 'Only the authorized five-attempt limit is supported')
    evidence_pin = pin(evidence); authorization = read(evidence)
    require(authorization.get('maximumGeometryAttempts') == maximum
            and authorization.get('scope') == 'all-items'
            and isinstance(authorization.get('authorization'), str)
            and bool(authorization['authorization'].strip()), 'Explicit all-item limit authorization required')
    output = Path(output)
    require(not output.exists(), 'Use a fresh limit-change receipt directory')
    with locked(path):
        state = read(path); policy = state.get('itemTrial', {})
        require(policy.get('id') == trial_id and policy.get('maximumGeometryAttempts') == 2,
                'Only an existing two-attempt trial can be upgraded; never reset or repeat a migration')
        require(not any(j['state'] in ('intent', 'submitted', 'timed-out') for j in state['jobs']),
                'Reconcile the outstanding job before changing the limit')
        before = pin(path); jobs_hash = digest(state['jobs'])
        verify([evidence_pin])
        output.mkdir(parents=True, exist_ok=False)
        write(output/'before.json', state, fresh=True)
        policy.setdefault('limitChanges', []).append({'previousMaximum': 2, 'maximumGeometryAttempts': maximum,
                                                     'authorization': evidence_pin})
        policy['maximumGeometryAttempts'] = maximum
        write(output/'after.json', state, fresh=True)
        verify([before, evidence_pin], fresh=True)
        write(path, state)
        actual = read(path)
        require(digest(actual) == digest(state) and digest(actual['jobs']) == jobs_hash,
                'Limit update changed ledger history')
        result = {'ledger': pin(path), 'before': pin(output/'before.json'),
                  'after': pin(output/'after.json'), 'authorization': evidence_pin,
                  'jobsUnchangedSha256': jobs_hash, 'maximumGeometryAttemptsPerModel': maximum}
        write(output/'receipt.json', result, fresh=True)
        return result


def shared_ledger(local, supplied=None):
    require(isinstance(local.get('submissionLedger'), str), 'Missing shared submission ledger binding')
    path = Path(local['submissionLedger']).resolve()
    require(path.is_file(), 'Initialize the authorized trial ledger once before item jobs; never reset its attempts')
    if supplied is not None:
        require(path == Path(supplied).resolve(), 'Item jobs must use the bound shared ledger')
    return path
