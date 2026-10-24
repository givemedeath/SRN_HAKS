"""Start Comfy with import-time proof of the complete executed module bodies.

Run this installed file instead of main.py. The audit hook verifies code before
execution, including cached bytecode, conditional assignments and default factories.
Ordinary main.py startup retains the conservative static verifier.
"""
import hashlib
import importlib.util
from pathlib import Path
import runpy
import sys
import types


def main():
    adapter = Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location('_srn_startup_snapshot', adapter/'source_snapshot.py',
                                                submodule_search_locations=[str(adapter)])
    snapshot = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = snapshot
    snapshot_code=compile((adapter/'source_snapshot.py').read_bytes(),str(adapter/'source_snapshot.py'),
                          'exec',dont_inherit=True,optimize=sys.flags.optimize)
    exec(snapshot_code,snapshot.__dict__)
    inventory = snapshot.load_inventory(adapter/'source-roots.json', adapter.parent.parent)
    roots = [Path(value).resolve() for value in inventory['roots']]
    pinned = {Path(row['path']): row['sha256'] for row in inventory['files']}
    executed = {}
    compiled = {}
    preexisting=set()
    for module in tuple(sys.modules.values()):
        if not isinstance(module,types.ModuleType):continue
        filename=vars(module).get('__file__')
        if isinstance(filename,str):
            path=Path(filename).resolve()
            if path.suffix.lower()=='.py' and snapshot._inside(path,roots):preexisting.add(path)
    preexisting.difference_update({Path(__file__).resolve(),adapter/'source_snapshot.py'})

    def audit(event, arguments):
        if event != 'exec' or not arguments or not isinstance(arguments[0], types.CodeType): return
        code = arguments[0]
        if code.co_filename.startswith('<'): return
        path = Path(code.co_filename).resolve()
        if path.suffix.lower() != '.py' or not snapshot._inside(path, roots): return
        source = path.read_bytes()
        digest = hashlib.sha256(source).hexdigest()
        if pinned.get(path) != digest:
            raise ValueError('Executed source differs from the frozen startup inventory: '+str(path))
        if path not in compiled:
            module = compile(source, str(path), 'exec', dont_inherit=True, optimize=sys.flags.optimize)
            compiled[path] = (snapshot._code_hash(module), set(snapshot._code_tree_hashes(module)))
        signature = snapshot._code_hash(code)
        if signature not in compiled[path][1]:
            raise ValueError('Executed Python code differs from its frozen source: '+str(path))
        if signature == compiled[path][0]: executed[path] = (digest, signature)

    def verified_sources(requested_roots, *, session=None):
        if [Path(value).resolve() for value in requested_roots] != roots:
            raise ValueError('Startup proof source roots differ')
        for path, (digest, _) in tuple(executed.items()):
            current=session.hash(path,retain_source=True) if session is not None else hashlib.sha256(path.read_bytes()).hexdigest()
            if current != digest:
                raise ValueError('Executed source changed after startup: '+str(path))
        # Preloaded modules may have retained older objects. They always keep the
        # static state checks, even if a later reload executes a reviewed body.
        return {path: signature for path, (_, signature) in executed.items() if path not in preexisting}

    # This is an in-process callable, never a caller-supplied JSON attestation.
    globals()['verified_sources'] = verified_sources
    sys.modules['_srn_verified_startup'] = sys.modules[__name__]
    sys.addaudithook(audit)
    # Include this running module's exact body, not merely its surviving functions.
    audit('exec', (sys._getframe().f_back.f_code,))
    audit('exec', (snapshot_code,))
    core = Path(inventory['core'])
    sys.path[0] = str(core)
    sys.argv = [str(core/'main.py'), *sys.argv[1:]]
    runpy.run_path(str(core/'main.py'), run_name='__main__')


if __name__ == '__main__': main()
