"""Run head batches through headkit: `run_headbatch.py --workspace DIR COMMAND`. See docs/heads/head-batch-orchestration.md."""
import argparse
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import guards  # noqa: E402
from head_files import write_json  # noqa: E402
import head_setup  # noqa: E402
import launcher  # noqa: E402
import gpu_contract  # noqa: E402
import presets  # noqa: E402
import spool  # noqa: E402
import trials  # noqa: E402
from workspace import PYTHON, Workspace, WorkspaceError  # noqa: E402


REVIEW = Path(__file__).resolve().with_name('review')


def review(workspace, tool, arguments, slot):
    command = [PYTHON, '-B', str(REVIEW/f'{tool}.py'), *arguments]
    environment = workspace.python_environment(packages=True, tools=True)

    def run():
        return subprocess.run(command, env=environment, cwd=workspace.heads).returncode
    if not slot:
        return run()
    with launcher.cpu_slot(workspace):
        return run()


def show_presets(workspace, args):
    held = False
    for head in args.heads:
        if args.apply:
            line, hold = presets.apply(workspace, head, args.uv_only, floor_review=args.review_floor)
        else:
            _, notes, reasons, _ = presets.plan(workspace, head, args.uv_only, floor_review=args.review_floor)
            line, hold = presets.summary(head, notes, reasons), bool(reasons)
        print(line)
        held = held or hold
    return 1 if held else 0


def parser():
    top = argparse.ArgumentParser(description=__doc__)
    top.add_argument('--workspace', help='workspace.json or its folder (default: SRN_HEAD_WORKSPACE)')
    commands = top.add_subparsers(dest='command', required=True)
    p = commands.add_parser('setup', help='create a head folder from a picked design')
    p.add_argument('head')
    p.add_argument('design')
    p.add_argument('--reference-record', type=Path)
    p.add_argument('--revised-clay-check', type=Path, help='select a checked replacement clay on the existing slot and preserve the GPU ledger')
    p.add_argument('--quality-profile', choices=['face-v1'])
    p.add_argument('--no-neck-cut', action='store_true', help='preserve a jaw-terminated head for review against the bound body neck')
    p.add_argument('--approval', required=True, help='who picked the design and on what basis')
    p.add_argument('--reach', type=float, default=.04)
    p.add_argument('--slope', type=float, default=-.2, help='-0.3 when hair reaches the nape (RUNBOOK 76)')
    p.add_argument('--deviation', action='append', default=[], help='observed departure of the design from its prompt')
    p = commands.add_parser('reference-check', help='validate a hash-bound external reference and optional measured pair; no approval')
    p.add_argument('head')
    p.add_argument('record', type=Path)
    p.add_argument('--output', type=Path, required=True)
    commands.add_parser('manifest', help='rewrite a head manifest').add_argument('head')
    p = commands.add_parser('components', help="record the reviewed shell selection from review-evidence/shells.json")
    p.add_argument('head')
    p.add_argument('--notes', required=True, help='what the shell review found')
    p = commands.add_parser('ownership', help='record a reviewed ownership rule set')
    p.add_argument('head')
    p.add_argument('rules', type=Path, help='JSON with regions, rules and notes')
    p = commands.add_parser('run', help='run stages for heads in one launch')
    p.add_argument('name')
    p.add_argument('stages')
    p.add_argument('heads', nargs='+')
    p.add_argument('--approve')
    p.add_argument('--notes')
    p.add_argument('--approve-attempt', help='refuse unless this is still the current attempt of the approved stage')
    p.add_argument('--result', type=Path, help='also write the result here as JSON')
    p = commands.add_parser('gpu', help='calibrate, geometry and appearance for one head')
    p.add_argument('head')
    p.add_argument('--stages')
    p.add_argument('--seed-offset')
    gpu_contract.geometry_options(p)
    p = commands.add_parser('gpu-camera', help='show the two camera estimates for an exact calibration attempt')
    p.add_argument('head')
    p.add_argument('--attempt', required=True)
    p = commands.add_parser('gpu-review', help='record user review of an exact raw geometry submission')
    p.add_argument('head')
    p.add_argument('--attempt', required=True)
    p.add_argument('--approval', required=True)
    p = commands.add_parser('design', help='design proposals, one launch per HEAD:SEED[:BATCH]')
    p.add_argument('race')
    p.add_argument('requests', nargs='+')
    p = commands.add_parser('trial-spec', help='write specs/trial-RACE-vN.json')
    p.add_argument('race')
    p.add_argument('--version', default='1')
    p = commands.add_parser('trial', help='build trials/NAME-vN from its spec')
    p.add_argument('name')
    p.add_argument('--version', default='1')
    p = commands.add_parser('spool', help='auto-advance queued heads')
    p.add_argument('--once', action='store_true')
    p = commands.add_parser('presets', help='plan or apply the up-front repair policies')
    p.add_argument('heads', nargs='+')
    p.add_argument('--uv-only', action='store_true')
    p.add_argument('--review-floor', metavar='NOTES', help='what you checked before lowering the UV floor; without it a lower floor is only reported')
    p.add_argument('--apply', action='store_true')
    commands.add_parser('status', help='one line per head: newest stage and what it waits for')
    p = commands.add_parser('review', help='a review sheet or diagnostic from tools/headbatch/review, run in the heads folder')
    p.add_argument('--slot', action='store_true', help='wait for a CPU slot first')
    p.add_argument('tool', choices=sorted(path.stem for path in REVIEW.glob('*.py') if not path.stem.startswith('_')))
    p.add_argument('arguments', nargs=argparse.REMAINDER)
    p = commands.add_parser('env', help='run a script with headkit and the bound packages on the path')
    p.add_argument('script')
    p.add_argument('arguments', nargs=argparse.REMAINDER)
    return top


def run_stages(workspace, args):
    outcome = {'name': args.name}
    try:
        outcome.update(launcher.run_stages(workspace, args.name, args.stages, args.heads, args.approve, args.notes, args.approve_attempt))
    except guards.Refused as refusal:
        outcome['refused'] = str(refusal)
    except launcher.LaunchFailed as error:
        outcome['error'] = str(error)
    if args.result:
        write_json(args.result, outcome)
    for row in outcome.get('heads', []):
        print(row['id'], row['error'], ' '.join(f"{item['stage']}:{item['status']}" for item in row['stages']))
        for item in row['stages']:
            if 'reason' in item and item['status'].startswith('blocked'):
                print(' ', item['stage'], item['reason'])
    if 'refused' in outcome or 'error' in outcome:
        raise SystemExit(f"REFUSED: {outcome['refused']}" if 'refused' in outcome else f"FAILED: {outcome['error']}")
    print('launch', outcome['label'], round(outcome['elapsedSeconds'], 1), 's exit', outcome['exitCode'])
    if outcome['exitCode']:
        print('reason:', outcome['errors'])
    return outcome['exitCode']


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        workspace = Workspace.load(args.workspace)
        if args.command == 'setup' and args.revised_clay_check:
            print('revised clay', head_setup.revise_clay(workspace, args.head, args.design, args.reference_record,
                                                        args.revised_clay_check, args.approval))
        elif args.command == 'setup':
            print('ready', head_setup.set_up(workspace, args.head, args.design, args.reach, args.slope, args.deviation, args.approval, reference=args.reference_record, quality_profile=args.quality_profile, no_neck_cut=args.no_neck_cut))
        elif args.command == 'reference-check':
            # The bound packages are loaded only in the env child, like other CPU tools.
            return subprocess.run([PYTHON, '-B', '-c',
                'import sys; sys.path.insert(0,sys.argv.pop(1)); import reference_record; reference_record.check(sys.argv[1],sys.argv[2],sys.argv[3])',
                str(Path(__file__).parent), str(args.record), args.head, str(args.output)],
                env=workspace.python_environment(packages=True, tools=True)).returncode
        elif args.command == 'manifest':
            print('manifest', head_setup.write_manifest(workspace, args.head))
        elif args.command == 'components':
            print('components', *head_setup.set_components(workspace, args.head, args.notes))
        elif args.command == 'ownership':
            print('manifest', head_setup.set_ownership(workspace, args.head, args.rules))
        elif args.command == 'run':
            return run_stages(workspace, args)
        elif args.command == 'gpu':
            extra = [*(['--stages', args.stages] if args.stages else []), *(['--seed-offset', args.seed_offset] if args.seed_offset else [])]
            if args.detail_camera_attempt is not None:
                extra.extend(['--detail-camera-attempt', args.detail_camera_attempt])
            if args.camera_approval is not None:
                extra.extend(['--camera-approval', args.camera_approval])
            if args.shape_grid is not None:
                extra.extend(['--shape-grid', str(args.shape_grid)])
            if args.single_submission:
                extra.append('--single-submission')
            data = launcher.run_gpu(workspace, args.head, extra)
            print('gpu launch', round(data['elapsedSeconds'], 1), 's exit', data['exitCode'])
            if data['exitCode'] == 0:
                print('manifest', head_setup.write_manifest(workspace, args.head))
            else:
                print('reason:', data['errors'])  # a cap or an open occiput stops the job with only its message there
            return data['exitCode']
        elif args.command == 'gpu-camera':
            with guards.head_locks(workspace, [args.head]), launcher.cpu_slot(workspace):
                args_list = ['--camera', str(workspace.head(args.head)), args.attempt]
                return subprocess.run([PYTHON, '-B', str(REVIEW/'gpuclay.py'), *args_list],
                                      env=workspace.python_environment(packages=True, tools=True)).returncode
        elif args.command == 'gpu-review':
            with guards.head_locks(workspace,[args.head]):
                print(gpu_contract.review_geometry(workspace.head(args.head),args.attempt,args.approval))
        elif args.command == 'design':
            rows = launcher.run_design(workspace, args.race, args.requests)
            for row in rows:
                print(row['head'], 'seed', row['seed'], round(row['elapsedSeconds'], 1), 's exit', row['exitCode'], row.get('error', ''))
            return max(row['exitCode'] for row in rows)  # RUNBOOK 119
        elif args.command == 'trial-spec':
            out, count = trials.write_spec(workspace, args.race, args.version)
            print(out, count, 'heads')
        elif args.command == 'trial':
            print(trials.build(workspace, args.name, args.version))
        elif args.command == 'spool':
            spool.Spool(workspace).loop(args.once)
        elif args.command == 'presets':
            return show_presets(workspace, args)
        elif args.command == 'status':
            for line in launcher.status(workspace):
                print(line)
        elif args.command == 'review':
            return review(workspace, args.tool, args.arguments, args.slot)
        elif args.command == 'env':
            return subprocess.run([PYTHON, '-B', args.script, *args.arguments], env=workspace.python_environment(packages=True, tools=True)).returncode
    except (WorkspaceError, guards.Refused, launcher.LaunchFailed) as error:
        raise SystemExit(f'{type(error).__name__}: {error}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
