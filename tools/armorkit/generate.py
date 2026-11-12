"""Source jobs for a generated outfit on the local engine: calibrate a reference image, generate its geometry,
export a mesh from that, generate its appearance.

Each job is posted straight to the running ComfyUI, on headkit's frozen graphs with their hash-checked model
loaders. It is a trial route: it skips the shared submission ledger and the guard's source and runtime checks
that headkit's own submissions pass, so what it makes is evidence for a trial and not a published source.

Two rules are kept here, where no script can leave them out. An image is taken further only if it comes from a
sealed brief (`brief.admit`): a calibrate, geometry or appearance job on any other image is refused before
anything is posted, and calibrate registers the copies it makes of the image. And a model gets at most
`MAXIMUM` geometry attempts, counted in `trial-ledger.json` in the work folder before the job is posted; an
attempt whose outcome is not known blocks the next one until it is reconciled by hand. Export and appearance
jobs are not counted. The ledger is locked for the whole of an attempt, so two started together cannot both be counted
as the same one. It is saved to a file of its own and put in place whole, so a write cut short loses no history. A model is named exactly as its folder is, so another spelling of it has no history of its own.

A work folder holds one folder per model, and a model's jobs are numbered folders under `geometry-trial` in it.
"""
import json
import time
import uuid
from contextlib import ExitStack, nullcontext
from pathlib import Path

from tools.headkit import comfy, common
from tools.headkit.comfy_nodes.model_resolution import bind_loader_models, model_choices, path_identity
from tools.headkit.gpu_lock import locked
from tools.headkit.shared_comfy import holding, slot
from tools.headkit.reference_background import analyze_reference

from . import brief, reference
from .registry import require

CHECKPOINTS = Path(__file__).resolve().parents[1] / 'headkit' / 'checkpoints.json'
PROFILE = 'pixal-single-v1'
LEDGER, JOBS = 'trial-ledger.json', 'geometry-trial'
MAXIMUM = 5  # geometry attempts per model, earlier ones included
DEADLINE, POLL = 2700, 5.0  # seconds a job may take, and between two looks at it
OUTSTANDING = ('intent', 'submitted')  # an attempt recorded and not known to have ended


def bound(graph, models):
    """(graph, pins): the graph with its model loaders bound to the files in the folder `models`, each held to
    the hash headkit has on record for it."""
    recorded = json.loads(CHECKPOINTS.read_text(encoding='utf-8'))
    pins = [{'category': category, 'name': name, 'pathIdentity': path_identity(Path(models) / category / name), 'sha256': recorded[name]}
            for category, name in model_choices(graph)]
    return bind_loader_models(graph, pins), pins


def export_settings(graph, settings):
    from tools.headkit.generation import apply_export_settings
    return apply_export_settings(graph, settings)


def engine(url):
    """The engine's client. Submission waits in shared_comfy.slot for the GPU lease and an idle queue; other jobs are left alone."""
    return comfy.Client(url)


def run(client, url, graph, token, folder, deadline=DEADLINE, poll=POLL):
    """Post one job and wait for it: (prompt id, history entry, names of the files fetched into `folder`,
    seconds). A job is posted once and never again."""
    with nullcontext() if holding() else slot(client):
        response = client.request('/prompt', {'prompt': graph, 'client_id': token})
    require(isinstance(response, dict) and response.get('prompt_id') and not response.get('node_errors'),
            'The engine refused the job: ' + json.dumps(response)[:2000])
    prompt_id = response['prompt_id']
    (folder / 'prompt-id.txt').write_text(prompt_id, encoding='utf-8')
    started = time.monotonic()
    while True:
        entry = client.request('/history/' + prompt_id).get(prompt_id)
        if entry and (entry.get('outputs') or entry.get('status', {}).get('completed') is not None):
            break
        require(time.monotonic() - started < deadline, f'Job {prompt_id} is unfinished after {deadline} s; it may still be running')
        time.sleep(poll)
    (folder / 'history.json').write_text(json.dumps(entry, indent=1), encoding='utf-8')
    files = []

    def visit(value):
        if isinstance(value, dict):
            if set(value) >= {'filename', 'subfolder', 'type'}:
                require(Path(value['filename']).name == value['filename'], 'An output is named as a path')
                (folder / value['filename']).write_bytes(reference.fetch(url, value, timeout=600))
                files.append(value['filename'])
            else:
                for item in value.values():
                    visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)
    visit(entry.get('outputs', {}))
    return prompt_id, entry, files, round(time.monotonic() - started, 1)


def named(work, model):
    """The model's folder, if `model` is its name exactly as the work folder lists it.

    The name is the model's identity in the attempts ledger. `outfit/`, `./outfit` and, on Windows, `Outfit`
    or `outfit.` all open the folder `outfit`, and each would start a history of its own there: a model with
    its five attempts made would get five more under another spelling. Any spelling but the listed one is
    refused."""
    work = Path(work).resolve()
    require(work.is_dir() and isinstance(model, str) and any(entry.name == model and entry.is_dir() for entry in work.iterdir()),
            f'{model!r} is not the name of a model folder in {work}')
    return work / model


def job(work, model, stage):
    """(work folder, the job's new folder, its token, the prefix the engine keeps its files under)."""
    work = Path(work).resolve()
    root = named(work, model) / JOBS
    root.mkdir(exist_ok=True)
    folder = root / f'{stage}-{len(list(root.glob(stage + "-*"))) + 1}'
    folder.mkdir()
    token = uuid.uuid4().hex
    return work, folder, token, 'headkit/armorkit-trial/' + token


def started(stage, model, token, image, document):
    return {'stage': stage, 'model': model, 'token': token, 'image': str(image), 'imageSha256': brief.digest(image),
            'route': 'direct, unguarded', 'brief': document['model']}


def finished(folder, record, done=None):
    if done is not None:
        prompt_id, entry, files, seconds = done
        record.update(promptId=prompt_id, files=files, seconds=seconds, status=entry.get('status', {}).get('status_str'))
    (folder / 'record.json').write_text(json.dumps(record, indent=1), encoding='utf-8')
    return {**record, 'folder': str(folder)}


def calibrate(work, model, image, models, url=reference.URL):
    """Prepare a reference image for the engine and read the camera it was drawn with. The copies it makes are
    what a geometry or appearance job is given, and are registered with the image's brief."""
    image = Path(image).resolve()
    document, sealed = brief.admit(image, Path(work) / model)
    client = engine(url)
    with slot(client):  # GPU lease and an idle queue before any job folder exists
        work, folder, token, prefix = job(work, model, 'calibrate')
        record = started('calibrate', model, token, image, document)
        decision = analyze_reference(image)
        staged = reference.upload(url, image, 'reference.png', prefix)
        graph, pins = bound(comfy.compile_graph('calibrate', PROFILE, {'geometry': staged, 'detail': staged, 'mask': staged}, prefix, background=decision), models)
        record.update(background={key: decision[key] for key in ('route', 'reason', 'size')}, models=pins)
        done = run(client, url, graph, token, folder)
        record['previews'] = {key: value.get('text') for key, value in done[1].get('outputs', {}).items() if 'text' in value}
        brief.register(sealed, *[folder / name for name in done[2] if name.lower().endswith('.png')])
        return finished(folder, record, done)


def attempts(work):
    """The geometry attempts on record in a work folder: the ledger, with a list of attempts per model."""
    path = Path(work) / LEDGER
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {'maximumGeometryAttempts': MAXIMUM, 'models': {}}


def geometry(work, model, image, fov, models, url=reference.URL):
    """Generate the outfit's geometry from an image: one counted attempt.

    The attempt is written to the ledger before the job is posted, and stays there whatever happens. If the
    job's outcome is not learned (the engine went away, the wait ran out), the attempt stays `submitted` with
    the error, and no further attempt is made on the model until someone has looked and set its state.

    The ledger is held (`tools.headkit.gpu_lock`) from before it is read until the attempt's outcome is
    written. Two attempts started together in one work folder would otherwise both read it, both pass the
    count, and each overwrite what the other wrote: a sixth job posted with five on record. The second is
    refused while the first is under way. The model is named exactly as its folder is (`named`), so another
    spelling of it cannot start a second history."""
    image = Path(image).resolve()
    document, _ = brief.admit(image, named(work, model))
    with ExitStack() as held:
        try:
            held.enter_context(locked(Path(work).resolve() / LEDGER))
        except FileExistsError:
            require(False, f'Another geometry attempt is under way in {work}: its ledger is held')
        ledger = attempts(work)
        rows = ledger['models'].setdefault(model, [])
        require(not any(row['state'] in OUTSTANDING for row in rows), f'An earlier attempt on {model} has no known outcome: reconcile it first')
        require(len(rows) < MAXIMUM, f'{model} has had its {MAXIMUM} geometry attempts')
        client = engine(url)
        held.enter_context(slot(client))  # wait for the GPU and the queue before the attempt is recorded
        work, folder, token, prefix = job(work, model, 'geometry')
        save = lambda: common.write(work / LEDGER, ledger)  # whole or not at all: a write cut short leaves the last one
        record = started('geometry', model, token, image, document)
        staged = reference.upload(url, image, 'geometry.png', prefix)
        graph, pins = bound(comfy.compile_graph('geometry', PROFILE, {'geometry': staged}, prefix, fov=fov), models)
        row = {'attempt': len(rows) + 1, 'token': token, 'state': 'intent', 'imageSha256': record['imageSha256'], 'fov': fov,
               'started': time.strftime('%Y-%m-%dT%H:%M:%S'), 'folder': str(folder.relative_to(work))}
        rows.append(row)
        save()
        record.update(fov=fov, attempt=row['attempt'], models=pins)
        (folder / 'graph.json').write_text(json.dumps(graph, indent=1), encoding='utf-8')
        row['state'] = 'submitted'
        save()
        try:
            done = run(client, url, graph, token, folder)
        except Exception as error:
            row['error'] = str(error)[:500]
            save()
            raise
        row.update(state='complete' if done[1].get('status', {}).get('status_str') == 'success' else 'failed', promptId=done[0], seconds=done[3])
        save()
        return finished(folder, record, done)


def appearance(work, model, image, fov, shape, models, url=reference.URL):
    """Generate the outfit's colours on a shape a geometry attempt saved (`shape`, its .npz). Not counted."""
    image, shape = Path(image).resolve(), Path(shape).resolve()
    document, _ = brief.admit(image, Path(work) / model)
    require(shape.is_file(), f'{shape} is not a saved shape')
    client = engine(url)
    with slot(client):  # GPU lease and an idle queue before any job folder exists
        work, folder, token, prefix = job(work, model, 'appearance')
        record = started('appearance', model, token, image, document)
        pin = {'path': str(shape), 'sha256': brief.digest(shape)}
        staged = reference.upload(url, image, 'detail.png', prefix)
        graph, pins = bound(comfy.compile_graph('appearance', PROFILE, {'detail': staged}, prefix, fov=fov, shape=pin), models)
        record.update(fov=fov, shape=pin, models=pins)
        (folder / 'graph.json').write_text(json.dumps(graph, indent=1), encoding='utf-8')
        return finished(folder, record, run(client, url, graph, token, folder))


def export(work, model, mesh, faces, fill=None, url=reference.URL):
    """Remesh a generated mesh at 768 and reduce it to `faces` faces; with `fill`, as a solid with its outside
    surface only. The mesh is one of the model's own, from a geometry attempt. Not counted."""
    work, mesh = Path(work).resolve(), Path(mesh).resolve()
    require(mesh.is_file() and mesh.is_relative_to(work / model), f'{mesh} is not a mesh of {model}')
    require(isinstance(faces, int) and faces > 0, 'The number of faces is a whole number')
    client = engine(url)
    with slot(client):  # GPU lease and an idle queue before any job folder exists
        work, folder, token, prefix = job(work, model, 'export')
        settings = {'remeshResolution': 768, 'targetFaceCount': faces}
        if fill is not None:
            settings.update(signMode='solid', fill=float(fill))
        pin = {'path': str(mesh), 'sha256': brief.digest(mesh)}
        graph = export_settings(comfy.compile_graph('export', PROFILE, {}, prefix, source=pin), settings)
        record = {'stage': 'export', 'model': model, 'token': token, 'route': 'direct, unguarded', 'settings': settings, 'source': pin}
        (folder / 'graph.json').write_text(json.dumps(graph, indent=1), encoding='utf-8')
        return finished(folder, record, run(client, url, graph, token, folder))
