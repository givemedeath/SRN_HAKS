"""Record completed practical validation; optionally attach an actual Git commit."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parents[2]


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def pin(relative):
    path = ROOT / relative
    return {'path': str(path), 'sha256': sha(path)}


def write(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')


parser = argparse.ArgumentParser()
parser.add_argument('--implementation-commit')
args = parser.parse_args()
ledger_path = ROOT / 'requirements.json'
ledger = json.loads(ledger_path.read_text(encoding='utf-8-sig'))
validation = json.loads((ROOT / 'client-validation-v1.json').read_text())
preflight = json.loads((ROOT / 'final-delivery-preflight-v1.json').read_text())
assert preflight['pass'] is True
assert len(validation['runs']) == 3
assert sha(ROOT / 'native-fourteen-v1/human_male_body.hak') == '01524cd39ad111021d30ba9a7c2241fdf8ef3afc7eb77f04346907d423d9f7c2'
common = ['offline-validation-v1.json', 'client-validation-v1.json', 'animation-sheet-review-v1.json', 'final-delivery-preflight-v1.json']
specific = {
    'full-body-animation-reference-sheet': ['offline-animation-reference-v1/reference-sheet.json', 'client-animation-reference-v2/reference-sheet.json'],
    'direct-load-launcher': ['Launch-HumanMale.ps1', 'client-fixture-selection.json'],
    'resource-costs': ['native-fourteen-costs-v1.json', 'client-log-scan-v1.json'],
    'isolated-test-module': ['client-fourteen-skin3-motion-v2/test-module/receipt.json'],
}
final_limits = {
    'full-body-pose-transitions': 'Sampled static offline controllers and actual continuous client observation are complementary; neither proves every intermediate joint state. Accepted deep-crouch/wrist overlaps remain.',
    'stock-equipment-offline': 'Representative offline equipment exposure and actual sword/shield/rigid-armor coverage are complete; not every equipment capture or variant was reviewed. Extreme stock held-axis palm penetration remains.',
    'body-only-native-hak': 'Construction-time clientReady=false is immutable history. Completed actual runtime validation is separate, scoped practical evidence.',
    'isolated-test-module': 'Actual three-run observation is complete. Historical builder/preflight false flags describe their creation time. Stationary gameplay targets and representative equipment do not cover every encounter.',
    'client-readiness-and-limitations': 'Ready for user review with bounded hand microdefects, visible extreme wrist overlap and accepted deep-crouch hip overlap. No exhaustive production certification.',
    'full-body-animation-reference-sheet': 'Both eight-category sheets and all included full-body sources were reviewed. A sheet samples motion and is not a continuous playback or all-angle guarantee.',
    'authorized-client-validation': 'Three actual owned runs and literal captures are complete. No all-equipment/palette/quality or crowded-scene GPU/frame-time claim.',
    'direct-load-launcher': 'The three immutable modes were actually client-tested; wrapper selection was exercised with NoLaunch. It refuses an existing client. Injected keyboard pan remains unverified.',
}
for name, item in ledger['requirements'].items():
    if name == 'committed-implementation':
        continue
    if 'preFinalReviewScope' not in item:
        item['preFinalReviewScope'] = {k: item.get(k) for k in ('status', 'completedEvidenceScope', 'remainingScope')}
    item['status'] = 'complete-practical-pass'
    item['remainingScope'] = 'None for the completed practical Human male pass; disclosed limits remain in client-validation-v1.json.'
    paths = common + specific.get(name, [])
    for relative in paths:
        proof = pin(relative)
        if proof['path'] not in item['evidence']:
            item['evidence'].append(proof['path'])
        item.setdefault('currentEvidenceHashes', {})[proof['path']] = proof['sha256']
    item['completedEvidenceScope'] = (item.get('completedEvidenceScope', '') + '\nCompleted cumulative offline and actual client validation: three owned runs, two palettes/light profiles, all eight animation categories, representative equipment, floor contact and sampled stability/performance.').strip() if 'Completed cumulative offline and actual client validation:' not in item.get('completedEvidenceScope', '') else item['completedEvidenceScope']
    if isinstance(item.get('limitations'), str):
        item['limitations'] = item['limitations'].replace('No collision-free item or continuous-client proof.', 'No collision-free item claim; representative continuous client observation is complete.')
    if name in final_limits:
        item.setdefault('preFinalReviewLimitations', item.get('limitations'))
        item['limitations'] = final_limits[name]

ledger['clientPolicy'] = 'Authorized practical client pass complete. All three owned clients stopped and archived. No new launch or polish required for this handoff.'
ledger['status'] = 'validation-complete-commit-pending'
ledger.pop('goalStatus', None)
ledger['goalStatusAuthority'] = 'Read actual tools.get_goal status; this ledger records deliverable evidence, not goal-tool state.'
milestone = ledger['currentMilestone']
milestone.update({
    'scope': 'Complete14 native body; offline/client practical validation and both sheets complete',
    'fixtureReceiptSha256': sha(ROOT / 'client-fourteen-skin3-motion-v2/test-module/receipt.json'),
    'fixtureModuleSha256': '6fbe425671c9317f2e3f6da08fd7de118963b3f4005bf033a79b4689978ee079',
    'offlineFullBodyVisualReviewCompleted': True,
    'animationReferenceSheetCompleted': True,
    'clientLaunched': True,
    'engineObserved': True,
    'runtimeAccepted': True,
    'productionWholeBodyAccepted': False,
    'allOwnedClientsStopped': True,
    'acceptanceScope': 'Ready for user review with disclosed practical limits; no exhaustive production certification.',
})

if args.implementation_commit:
    commit = subprocess.check_output(['git', 'rev-parse', '--verify', args.implementation_commit + '^{commit}'], cwd=WORKSPACE, text=True).strip()
    ledger['implementationCheckpoint'] = commit
    ledger['status'] = 'complete-practical-pass'
    ledger['requirements']['committed-implementation'].update({
        'status': 'complete-committed',
        'evidence': [commit, str(ROOT / 'final-implementation-files-v1.json')],
        'completedEvidenceScope': 'Selected implementation, configs, small evidence receipts, current process documents and literal-reference builder committed in the recorded Git object.',
        'remainingScope': 'None; final delivery bookkeeping follows this implementation commit.',
        'limitations': 'Large generated binary assets remain preserved in the worktree, pinned by committed receipts; unrelated changes were not staged.',
    })
write(ledger_path, ledger)

if args.implementation_commit:
    delivery = {
        'schemaVersion': 1,
        'status': 'complete-practical-pass-ready-for-user-review',
        'implementationCommit': commit,
        'bodyHak': pin('native-fourteen-v1/human_male_body.hak'),
        'bodyModels': 14,
        'resources': 72,
        'offlineValidation': pin('offline-validation-v1.json'),
        'clientValidation': pin('client-validation-v1.json'),
        'clientLogScan': pin('client-log-scan-v1.json'),
        'offlineSheet': pin('offline-animation-reference-v1/animation-reference-sheet.png'),
        'clientSheet': pin('client-animation-reference-v2/animation-reference-sheet.png'),
        'sheetReview': pin('animation-sheet-review-v1.json'),
        'preflight': pin('final-delivery-preflight-v1.json'),
        'launcher': pin('Launch-HumanMale.ps1'),
        'requirements': pin('requirements.json'),
        'clientModes': ['Motion', 'Gameplay', 'Kneel'],
        'defaultMode': 'Motion',
        'allOwnedClientsStopped': True,
        'acceptedLimitations': validation['acceptedLimitations'],
        'purgePerformedDuringGoal': False,
        'largeAssetsPreservedOutsideGit': True,
        'nextPhase': 'Troll male queued separately; not automatically started.',
    }
    write(ROOT / 'final-delivery-v1.json', delivery)
print(json.dumps({'ledger': ledger['status'], 'implementationCommit': args.implementation_commit, 'requirementCount': len(ledger['requirements'])}))
