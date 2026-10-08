"""Verified shared tool resolution and dependency receipts (stdlib only).

Resolution is read-only. Registration is explicit and never constitutes approval
to remove a checkout, accept an asset, or run a client.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import time
import uuid

HERE = Path(__file__).resolve().parent


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write_json(path, data, *, fresh=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(data, indent=2, ensure_ascii=False) + '\n').encode('utf-8')
    if fresh:
        with path.open('xb') as out:
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
        return
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temp.open('xb') as out:
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def git(repo, *args):
    env = os.environ.copy()
    for key in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_COMMON_DIR', 'GIT_INDEX_FILE'):
        env.pop(key, None)
    result = subprocess.run(['git', '-C', str(repo), *args], capture_output=True,
                            encoding='utf-8', env=env)
    if result.returncode:
        raise ValueError('Git metadata unavailable; supply an explicit tools root')
    return result.stdout.strip()


def worktrees(repo):
    # Git 2.34 on supported Windows installs predates porcelain -z.
    records = git(repo, '-c', 'core.quotepath=false', 'worktree', 'list', '--porcelain').split('\n\n')
    result = []
    for record in records:
        fields = record.splitlines()
        paths = [field[9:] for field in fields if field.startswith('worktree ')]
        if paths:
            path=json.loads(paths[0]) if paths[0].startswith('"') else paths[0]
            result.append({'path': str(Path(path).resolve()), 'bare': 'bare' in fields})
    return result


def inside(path, root):
    return Path(path).resolve().is_relative_to(Path(root).resolve())


def reject_linked(path, repo):
    path = Path(path).resolve()
    try:
        for entry in worktrees(repo)[1:]:
            if inside(path, entry['path']):
                raise ValueError('Shared/installed tool is inside a linked worktree: ' + str(path))
    except ValueError as error:
        if 'metadata unavailable' not in str(error):
            raise
    # Detect linked checkouts of other repositories too, including through links.
    for ancestor in [path, *path.parents]:
        if (ancestor / '.git').is_file():
            git_dir = git(ancestor, 'rev-parse', '--path-format=absolute', '--git-dir')
            common = git(ancestor, 'rev-parse', '--path-format=absolute', '--git-common-dir')
            if Path(git_dir).resolve() != Path(common).resolve():
                raise ValueError('Shared/installed tool is inside a linked worktree: ' + str(path))
            break
        if (ancestor / '.git').is_dir():
            break


def tools_root(repo=None, explicit=None):
    repo = Path(repo or HERE.parent).resolve()
    chosen = explicit if explicit is not None else os.environ.get('SRN_TOOLS_ROOT')
    if chosen:
        root, origin = Path(chosen).expanduser().resolve(), ('argument' if explicit is not None else 'environment')
    else:
        entries = worktrees(repo)
        if not entries or entries[0]['bare']:
            raise ValueError('Bare repository requires an explicit tools root')
        root, origin = Path(entries[0]['path']) / '.tools', 'primary-checkout'
    root = root.resolve()
    reject_linked(root, repo)
    return root, origin


def platform_key():
    if platform.machine().lower() not in ('amd64', 'x86_64'):
        raise ValueError('Pinned tools require x64')
    return ('windows' if os.name == 'nt' else 'linux') + '-x64'


def inventory(repo=None):
    path = Path(repo or HERE.parent) / 'tools/shared-tools.lock.json'
    raw=path.read_bytes();data=json.loads(raw.decode('utf-8-sig'))
    if data.get('schemaVersion') != 1:
        raise ValueError('Unsupported shared tool inventory')
    return path, data, hashlib.sha256(raw).hexdigest()


def resolve_tool(name, repo=None, root=None, override=None):
    repo = Path(repo or HERE.parent).resolve()
    bank, root_origin = tools_root(repo, root)
    lock, data, lock_hash = inventory(repo)
    if name not in data['tools']:
        raise ValueError('Unknown tool: ' + name)
    tool = data['tools'][name]
    entry = tool['platforms'].get(platform_key())
    if not entry:
        raise ValueError('Tool unsupported on this platform: ' + name)
    base = repo / 'tools' if tool['origin'] == 'vendored' else bank
    path = Path(override).resolve() if override is not None else (base / entry['relativePath']).resolve()
    if not inside(path, base):
        raise ValueError('Tool path escapes its declared installation: ' + str(path))
    if tool['origin'] == 'vendored':
        if not inside(path, repo / 'tools/vendor'):
            raise ValueError('Vendored tool must belong to the consuming checkout')
    else:
        reject_linked(path, repo)
    if not path.is_file():
        raise ValueError('Missing tool: ' + str(path) + '. ' + tool.get('installation', 'Run tools/Bootstrap-Tools.ps1.'))
    actual = sha(path)
    if actual != entry['sha256']:
        raise ValueError('Tool binary changed: ' + str(path))
    if sha(lock)!=lock_hash:raise ValueError('Tool inventory changed during resolution')
    return {'name': name, 'path': str(path), 'version': tool['version'], 'sha256': actual,
            'origin': tool['origin'], 'toolsRoot': str(bank), 'rootOrigin': root_origin,
            'inventorySha256': lock_hash}


def resolve_addon(name='neverblender', repo=None, root=None, override=None):
    repo = Path(repo or HERE.parent).resolve()
    bank, origin = tools_root(repo, root)
    lock, data, lock_hash = inventory(repo)
    entry = data['addons'][name]
    path = Path(override).resolve() if override is not None else (bank / entry['relativePath']).resolve()
    reject_linked(path, repo)
    if not inside(path, bank) or not path.is_dir():
        raise ValueError('Missing/escaped addon bank. ' + entry['installation'])
    actual = {p.relative_to(path).as_posix() for p in path.rglob('*') if p.is_file()
              and '__pycache__' not in p.parts and p.suffix not in ('.pyc', '.pyo')}
    if actual != set(entry['files']):
        raise ValueError('Shared addon source inventory changed')
    for rel, expected in entry['files'].items():
        file = (path / rel).resolve()
        if not inside(file, path) or sha(file) != expected:
            raise ValueError('Shared addon bytes changed: ' + rel)
    if sha(lock)!=lock_hash:raise ValueError('Tool inventory changed during resolution')
    return {'root': str(path), 'files': entry['files'], 'version': entry['version'],
            'toolsRoot': str(bank), 'rootOrigin': origin, 'inventorySha256': lock_hash}


def resolve_runtime(name, path, repo=None, expected=None):
    path = Path(path).resolve()
    if name == 'python' and 'windowsapps' in (part.lower() for part in path.parts):
        raise ValueError('Windows Store Python shim is unsupported; use bundled workspace Python')
    reject_linked(path, repo or HERE.parent)
    actual = sha(path)
    if expected is not None and expected != actual:
        raise ValueError('Installed runtime changed: ' + str(path))
    return {'name': name, 'path': str(path), 'sha256': actual, 'origin': 'installed'}


@contextmanager
def locked(path, timeout=30):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = path.open('a+b')
    end = time.monotonic() + timeout
    acquired = False
    try:
        while not acquired:
            stream.seek(0)
            try:
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    # FileStream.Lock uses a POSIX byte-range lock. flock is a
                    # separate lock family on Linux and would allow PS writers
                    # to enter the same registration critical section.
                    fcntl.lockf(stream, fcntl.LOCK_EX | fcntl.LOCK_NB, 1, 0, os.SEEK_SET)
                acquired = True
            except OSError:
                if time.monotonic() >= end:
                    raise TimeoutError('Dependency lock is held: ' + str(path))
                time.sleep(.05)
        if not path.stat().st_size:
            stream.write(b'0'); stream.flush()
        yield
    finally:
        if acquired:
            stream.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.lockf(stream, fcntl.LOCK_UN, 1, 0, os.SEEK_SET)
        stream.close()


def reference(path, role='input', expected=None):
    if role not in ('tool', 'input', 'provenance'):
        raise ValueError('Unknown dependency role')
    path = Path(path).resolve()
    actual = sha(path) if path.is_file() else None
    if expected is not None and actual != expected:
        raise ValueError('Dependency changed: ' + str(path))
    return {'path': str(path), 'role': role, 'sha256': actual}


def register_run(repo, root=None, tools=(), inputs=(), provenance=(), *, complete=False, _verified_inputs=None):
    repo = Path(repo).resolve()
    bank, origin = tools_root(repo, root)
    consumer_id = hashlib.sha256(os.path.normcase(str(repo)).encode('utf-8')).hexdigest()
    folder = bank / 'consumers' / consumer_id
    refs = [reference(row['path'], 'tool', row['sha256']) for row in tools]
    def input_reference(row):
        path=Path(row['path'] if isinstance(row,dict) else row).resolve()
        role=row.get('role','input') if isinstance(row,dict) else 'input'
        expected=row.get('sha256') if isinstance(row,dict) else None
        # Only the synchronous launcher supplies its freshly verified snapshot.
        # Other callers retain independent byte verification. The launcher
        # verifies the complete snapshot again after the child exits.
        if _verified_inputs is not None and str(path) in _verified_inputs:
            digest=_verified_inputs[str(path)]
            if role not in ('tool','input','provenance') or not path.is_file():raise ValueError('Invalid verified input')
            if not isinstance(digest,str) or len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):raise ValueError('Invalid verified input digest')
            if expected is not None and expected!=digest:raise ValueError('Dependency changed: '+str(path))
            return {'path':str(path),'role':role,'sha256':digest}
        return reference(path,role,expected)
    refs += [input_reference(row) for row in inputs]
    refs += [reference(path, 'provenance') for path in provenance]
    if complete and any(row['role']!='provenance' and row['sha256'] is None for row in refs):
        raise ValueError('Complete declarations require individual existing file hashes; enumerate directory inputs')
    report = {'schemaVersion': 1, 'kind': 'shared-tool-consumer', 'worktree': str(repo),
              'createdUtc': datetime.now(timezone.utc).isoformat(), 'toolsRoot': str(bank),
              'rootOrigin': origin, 'completeDeclaration': complete, 'references': refs,
              'inventorySha256':sha(repo/'tools/shared-tools.lock.json')}
    local = repo / '.tmp/tool-dependencies' / (uuid.uuid4().hex + '.json')
    with locked(folder / 'registration.lock'):
        current = folder / 'current.json'
        if current.exists() and not complete:
            previous = read_json(current)
            all_refs = {(row['role'], row['path']): row for row in previous['references']}
            all_refs.update({(row['role'], row['path']): row for row in refs})
            report['references'] = list(all_refs.values())
        write_json(local, report, fresh=True)
        write_json(current, report)
    return local


def retirement_audit(repo, retiring, root=None):
    bank, _ = tools_root(repo, root)
    retiring = Path(retiring).resolve()
    known = {row['path'] for row in worktrees(repo)}
    records = {}
    for path in (bank / 'consumers').glob('*/current.json'):
        record = read_json(path)
        records[str(Path(record['worktree']).resolve())] = record
    coverage, dependencies, missing, drift = [], [], [], []
    for worktree in sorted(known | set(records)):
        if Path(worktree).resolve() == retiring:
            continue
        record = records.get(worktree)
        if worktree in known and (not record or record.get('completeDeclaration') is not True):
            coverage.append(worktree)
        if not record:
            continue
        for row in record['references']:
            if row['role'] == 'provenance':
                continue
            value = {'consumer': worktree, **row}
            path = Path(row['path'])
            if inside(path, retiring):
                dependencies.append(value)
            if not path.exists():
                missing.append(value)
            elif row.get('sha256') and (not path.is_file() or sha(path) != row['sha256']):
                drift.append(value)
    return {'kind': 'worktree-retirement-audit', 'retiringWorktree': str(retiring),
            'dependencies': dependencies, 'missingDependencies': missing, 'changedDependencies': drift,
            'incompleteConsumers': coverage, 'dependencyClear': not (dependencies or missing or drift or coverage),
            'safeToRetire': False, 'ownerArchiveAndRemovalApprovalRequired': True,
            'note': 'Dependency clearance is not evidence that ignored assets are backed up or removal is authorized.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=HERE.parent)
    parser.add_argument('--tools-root', type=Path)
    sub = parser.add_subparsers(dest='action', required=True)
    resolve = sub.add_parser('resolve'); resolve.add_argument('name')
    audit = sub.add_parser('retirement'); audit.add_argument('worktree', type=Path)
    declare = sub.add_parser('declare'); declare.add_argument('--manifest', type=Path, required=True)
    args = parser.parse_args()
    if args.action == 'resolve':
        result = resolve_tool(args.name, args.repo, args.tools_root)
    elif args.action == 'retirement':
        result = retirement_audit(args.repo, args.worktree, args.tools_root)
    else:
        manifest = read_json(args.manifest)
        result = {'receipt': str(register_run(args.repo, args.tools_root,
                  inputs=manifest['references'], complete=True))}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
