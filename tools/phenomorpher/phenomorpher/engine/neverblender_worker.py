"""Runs inside headless Blender: binary MDL compile/decompile through the installed Neverblender add-on.

Started by neverblender_mdl.run as `blender --background --factory-startup --python <this> -- <job.json>`.
The add-on is imported from the declared folder after its file hashes are rechecked, so Blender
loads exactly the bytes the host pinned. Neverblender's bundled cleanmodels port does the work
(nvb_cleanmodels.compile_bundled / nvb_mdl.Mdl.decompile_bundled), but with the explicit lookup
folders of the job: no game-install discovery, no NWN_ROOT and no override folder.
Standard library and the add-on only; nothing here imports phenomorpher.
"""
import hashlib
import json
import os
import sys
import time


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load_addon(root, files):
    root = os.path.realpath(root)
    actual = {}
    for base, dirs, names in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d != '__pycache__')
        for name in names:
            if not name.endswith(('.pyc', '.pyo')):
                path = os.path.join(base, name)
                actual[os.path.relpath(path, root).replace(os.sep, '/')] = digest(open(path, 'rb').read())
    if actual != files:
        raise RuntimeError('Neverblender add-on files differ from the declared pins')
    sys.dont_write_bytecode = True
    sys.path.insert(0, os.path.dirname(root))
    package = os.path.basename(root)
    if package in sys.modules:
        raise RuntimeError('Neverblender was already imported before the pinned copy')
    module = __import__(package, fromlist=['cleanmodels'])
    cleanmodels = sys.modules[package + '.cleanmodels']
    for loaded in (module, cleanmodels):
        if not os.path.realpath(loaded.__file__).startswith(root + os.sep):
            raise RuntimeError('Neverblender imported from outside its declared folder: ' + loaded.__file__)
    return module, cleanmodels


def compile_job(cleanmodels, job):
    with open(job['input'], 'rb') as stream:
        source = stream.read()
    result = cleanmodels.parse(source)
    result.model.file_type = 'ascii'
    warnings = [str(e) for e in result.errors]
    data = cleanmodels.compile(result.model, job['dirs'], job['dirs'], warnings.append)
    return source, data, warnings


def decompile_job(cleanmodels, job):
    with open(job['input'], 'rb') as stream:
        source = stream.read()
    model = cleanmodels.decompile(source, job['dirs'])
    warnings = [(w.node + ': ' if w.node else '') + w.message for w in model.warnings]
    return source, cleanmodels.write(model).encode('latin-1'), warnings


def main():
    request = json.loads(open(sys.argv[sys.argv.index('--') + 1], encoding='utf-8').read())
    module, cleanmodels = load_addon(request['addon'], request['files'])
    rows = []
    for job in request['jobs']:
        started = time.perf_counter()
        try:
            source, data, warnings = (compile_job if job['op'] == 'compile' else decompile_job)(cleanmodels, job)
        except Exception as error:  # Reported per model; the host fails the run.
            rows.append({'input': job['input'], 'error': type(error).__name__ + ': ' + str(error)})
            continue
        if job['op'] == 'compile' and data[:4] != b'\0\0\0\0':
            rows.append({'input': job['input'], 'error': 'Compiler wrote no binary model'}); continue
        with open(job['output'], 'xb') as stream:
            stream.write(data)
        rows.append({'input': job['input'], 'output': job['output'], 'sourceSha256': digest(source),
                     'outputSha256': digest(data), 'bytes': len(data), 'warnings': warnings,
                     'seconds': round(time.perf_counter() - started, 4)})
    bl_info = getattr(module, 'bl_info', {})
    report = {'neverblenderVersion': list(bl_info.get('version', ())), 'cleanmodelsPortedFrom': cleanmodels.PORTED_FROM,
              'blenderVersion': __import__('bpy').app.version_string, 'results': rows}
    with open(request['report'], 'x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(report, indent=1) + '\n')


if __name__ == '__main__':
    main()
