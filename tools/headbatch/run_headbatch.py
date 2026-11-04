"""Run head batches through headkit: `run_headbatch.py --workspace DIR COMMAND`. See docs/heads/head-batch-orchestration.md."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import guards  # noqa: E402
from head_files import write_json  # noqa: E402
import head_setup  # noqa: E402
import launcher  # noqa: E402
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
    with launcher.cpu_slot(workspace, f'{os.getpid()} review {tool}'):
        return run()


def show_presets(workspace, args):
    held = False
    for head in args.heads:
        if args.apply:
            line, hold = presets.apply(workspace, head, args.uv_only, keep_floor=args.keep_floor)
        else:
            _, notes, reasons, _ = presets.plan(workspace, head, args.uv_only, keep_floor=args.keep_floor)
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
    p.add_argument('--approval', required=True, help='who picked the design and on what basis')
    p.add_argument('--reach', type=float, default=.04)
    p.add_argument('--slope', type=float, default=-.2, help='-0.3 when hair reaches the nape (RUNBOOK 76)')
    p.add_argument('--deviation', action='append', default=[], help='observed departure of the design from its prompt')
    commands.add_parser('manifest', help='rewrite a head manifest').add_argument('head')
    p = commands.add_parser('run', help='run stages for heads in one launch')
    p.add_argument('name')
    p.add_argument('stages')
    p.add_argument('heads', nargs='+')
    p.add_argument('--approve')
    p.add_argument('--notes')
    p.add_argument('--result', type=Path, help='also write the result here as JSON')
    p = commands.add_parser('gpu', help='calibrate, geometry and appearance for one head')
    p.add_argument('head')
    p.add_argument('--stages')
    p.add_argument('--seed-offset')
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
    p.add_argument('--keep-floor', action='store_true', help='report a lower UV floor instead of recording its review')
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
        outcome.update(launcher.run_stages(workspace, args.name, args.stages, args.heads, args.approve, args.notes))
    except guards.Refused as refusal:
        outcome['refused'] = str(refusal)
    except (launcher.LaunchFailed, subprocess.CalledProcessError) as error:
        outcome['error'] = str(error)
    if args.result:
        write_json(args.result, outcome)
    for row in outcome.get('heads', []):
        print(row['id'], row['error'], ' '.join(f"{item['stage']}:{item['status']}" for item in row['stages']))
    if 'refused' in outcome or 'error' in outcome:
        raise SystemExit(f"REFUSED: {outcome['refused']}" if 'refused' in outcome else f"FAILED: {outcome['error']}")
    print('launch', outcome['label'], round(outcome['elapsedSeconds'], 1), 's exit', outcome['exitCode'])
    return outcome['exitCode']


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        workspace = Workspace.load(args.workspace)
        if args.command == 'setup':
            print('ready', head_setup.set_up(workspace, args.head, args.design, args.reach, args.slope, args.deviation, args.approval))
        elif args.command == 'manifest':
            print('manifest', head_setup.write_manifest(workspace, args.head))
        elif args.command == 'run':
            return run_stages(workspace, args)
        elif args.command == 'gpu':
            extra = [*(['--stages', args.stages] if args.stages else []), *(['--seed-offset', args.seed_offset] if args.seed_offset else [])]
            data = launcher.run_gpu(workspace, args.head, extra)
            print('gpu launch', round(data['elapsedSeconds'], 1), 's exit', data['exitCode'])
            if data['exitCode'] == 0:
                print('manifest', head_setup.write_manifest(workspace, args.head))
            return data['exitCode']
        elif args.command == 'design':
            for row in launcher.run_design(workspace, args.race, args.requests):
                print(row['head'], 'seed', row['seed'], round(row['elapsedSeconds'], 1), 's exit', row['exitCode'])
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
