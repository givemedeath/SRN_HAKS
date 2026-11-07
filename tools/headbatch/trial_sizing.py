"""Size a retained, reviewed compact-reference Troll export for a local trial."""
from pathlib import Path
import sys

from headkit.common import pin, read, require, verify, write
from headkit.native import prepare, compile_and_package, mdl_compiler, mdl_compiler_files


def inputs(native_path, policy, compiler, bindings):
    from headkit.common import stage_code_files
    native = read(native_path)
    export_pin = native['dependencies']['export']
    verify([export_pin])
    export = read(export_pin['path'])
    fit_pin = export['dependencies']['fit']
    palette_pin = export['dependencies']['palette']
    verify([fit_pin, palette_pin])
    fit = read(fit_pin['path'])['result']
    maps = read(palette_pin['path'])['result']
    old = export['result']
    require(native['state'] == export['state'] == 'complete' and
            'nativeSizing' not in old and fit['align'] in ('profile', 'nose'),
            'Trial sizing requires a completed, pre-allowance profile fit')
    require(old['matrix'] == fit['matrix'], 'Retained export used a different fit')
    refs = [native['result'][k] for k in ('mdl','plt')] + [fit['reference'], old['source'],
            old['expected'], old['plt'], maps['shades'], maps['ownership']]
    verify(refs)
    require(old['plt']['sha256'] == native['result']['plt']['sha256'], 'Retained PLT lineage differs')
    files = [Path(__file__), native_path, export_pin['path'], fit_pin['path'], palette_pin['path'],
             policy, bindings, *[p['path'] for p in refs], *[p['path'] for p in mdl_compiler_files(compiler)],
             *stage_code_files('export'), *stage_code_files('native'),
             *[p['path'] for p in read(bindings)['pythonPackages']['files']]]
    return old, fit, maps, sorted({str(Path(p).resolve()) for p in files})


def main():
    import numpy as np
    native, policy, compiler, bindings, output = map(Path, sys.argv[1:6])
    old, fit, maps, files = inputs(native, policy, compiler, bindings)
    if len(sys.argv) == 7:
        write(sys.argv[6], files, fresh=True)
        return
    result = prepare(old['source']['path'], maps['shades']['path'], maps['ownership']['path'],
                     {'matrix': old['matrix'], 'reviewed': True, 'sourceSha256': old['source']['sha256']},
                     old['model'], output/'prepared', sizing_inputs=(policy, fit['reference']['path']))
    require(result['plt']['sha256'] == old['plt']['sha256'], 'Troll trial changed reviewed PLT bytes')
    scale = result['nativeSizing']['scale']
    with np.load(result['expected']['path']) as new, np.load(old['expected']['path']) as original:
        require(np.array_equal(new['uv'], original['uv']) and np.array_equal(new['normals'], original['normals'])
                and np.allclose(new['positions'], original['positions']*scale, rtol=0, atol=1e-7),
                'Troll trial must differ only by uniform vertex scale')
    compiled = compile_and_package(output/'prepared', None, output/'native', mdl=mdl_compiler(compiler))
    write(output/'trial-sizing.json', {'retainedNative':pin(native),'sizing':result['nativeSizing'],
          'pltIdentical': True,'normalsAndUVIdentical':True,'native':compiled}, fresh=True)


if __name__ == '__main__':
    main()
