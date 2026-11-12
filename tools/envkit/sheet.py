"""A sheet's models through Meshy under the shared ledger, as the sheet's plan states them.

A plan (`tools/envkit/sets/<sheet>-meshy.json`) names the set, a short prefix for its ledger keys, each prop to make
with its triangle target, and the building's views and the ceiling it is remeshed to:

    {"set": "ares-depot", "prefix": "ares",
     "props": {"reception-desk": {"triangles": 12000}, "turret": {"triangles": 8000, "key": "ares-turret-a2"}},
     "building": {"views": ["building-hero", "building-front", "building-rear"], "triangles": 200000}}

A prop's key is `<prefix>-<asset>-a1` and the building's `<prefix>-building-a1`, its remesh that with `-remesh`,
unless the plan says otherwise (`key`, `remesh`): Meshy's CLI never sends a key twice, so a call that was refused
goes again under a new one, and the plan is where that is written down. `submit` sends whatever the ledger does not
hold yet, as far as Meshy's queue has room (`meshy.QUEUE`); `collect` waits for each, downloads the props, keeps the
building's full generation as a master, remeshes it and downloads that. Both are safe to run again, and a sheet of
more calls than the queue holds is run by turns: submit, collect, submit, collect. This was a one-off script for the Stuffer Shack and the Ares Depot
(2026-11-10, 2026-11-11) and is here so that the next sheet is run from the repository."""
import json
import re
from pathlib import Path

from . import meshy, reference, require

PREFIX = re.compile(r'[a-z0-9]{2,12}')
WAITING = ('submitted', 'pending', 'in_progress')
QUEUED = (*WAITING, 'uncertain')  # what may be holding a place in Meshy's queue


def load_plan(path):
    """The plan at `path`, checked against the set it names (the set file beside it), with every key worked out:
    {set, prefix, props: {asset: {triangles, key}}, building: {views, triangles, key, remesh} or None, unplanned}.
    `unplanned` names what the set holds that the plan makes nothing of: props that no other sheet's model serves,
    and the building's views where the plan has no building. Leaving one out is allowed, and `status` says so."""
    path = Path(path); plan = json.loads(path.read_text(encoding='utf-8'))
    require(isinstance(plan, dict) and {'set', 'prefix', 'props'} <= set(plan) <= {'set', 'prefix', 'props', 'building'}, 'A plan names its set, a prefix and its props')
    require(isinstance(plan['prefix'], str) and PREFIX.fullmatch(plan['prefix']) is not None, 'A plan\'s prefix is 2 to 12 lowercase letters and digits')
    require(isinstance(plan['set'], str) and reference.NAME.fullmatch(plan['set']) is not None, 'A plan names its set by its file name: ' + str(plan['set']))
    assets = reference.load_set(path.with_name(plan['set'] + '.json'))['assets']; prefix = plan['prefix']; props = {}
    require(isinstance(plan['props'], dict), 'A plan\'s props are {asset: {triangles}}')
    for name, stated in plan['props'].items():
        asset = assets.get(name)
        require(asset is not None and asset['kind'] == 'prop', f'{name} is not a prop of {plan["set"]}')
        require('same' not in asset, f'{name} is the same as {asset.get("same")}: that one serves, and nothing is made')
        require(isinstance(stated, dict) and {'triangles'} <= set(stated) <= {'triangles', 'key'} and type(stated['triangles']) is int
                and meshy.PROP_TRIANGLES[0] <= stated['triangles'] <= meshy.PROP_TRIANGLES[1],
                f'A prop states a triangle target of {meshy.PROP_TRIANGLES[0]} to {meshy.PROP_TRIANGLES[1]}: {name}')
        props[name] = {'triangles': stated['triangles'], 'key': stated.get('key', f'{prefix}-{name}-a1')}
    building = plan.get('building')
    if building is not None:
        require(isinstance(building, dict) and {'views', 'triangles'} <= set(building) <= {'views', 'triangles', 'key', 'remesh'}
                and isinstance(building['views'], list) and 1 <= len(building['views']) <= 4 and all(isinstance(name, str) for name in building['views'])
                and len(set(building['views'])) == len(building['views']), 'A building states one to four views, each once, and the triangles it is remeshed to')
        for name in building['views']:
            require(name in assets and assets[name]['kind'] == 'building', f'{name} is not a building view of {plan["set"]}')
        require(type(building['triangles']) is int and 1000 <= building['triangles'] <= meshy.BUILDING_TRIANGLES,
                f'A building is remeshed to at most {meshy.BUILDING_TRIANGLES} triangles')
        key = building.get('key', f'{prefix}-building-a1')
        building = {'views': list(building['views']), 'triangles': building['triangles'], 'key': key, 'remesh': building.get('remesh', key + '-remesh')}
    keys = [row['key'] for row in props.values()] + ([building['key'], building['remesh']] if building else [])
    require(all(isinstance(key, str) and meshy.KEY.fullmatch(key) is not None for key in keys), 'Ledger keys are lowercase letters, digits and hyphens')
    require(len(set(keys)) == len(keys), 'Each call of a plan has its own ledger key')
    unplanned = sorted(name for name, asset in assets.items() if (asset['kind'] == 'prop' and 'same' not in asset and name not in props)
                       or (asset['kind'] == 'building' and building is None))
    return {'set': plan['set'], 'prefix': prefix, 'props': props, 'building': building, 'unplanned': unplanned}


def image(selected, name):
    """The one reference image chosen for an asset: `<name>-s<seed>-b0.png` in the folder of selected references."""
    named = re.compile(re.escape(name) + r'-s\d+-b0\.png')  # `fence-s*` alone would take fence-section's image too
    found = sorted(path for path in Path(selected).glob(name + '-s*-b0.png') if named.fullmatch(path.name))
    require(len(found) == 1, f'One selected reference is needed for {name}; found {len(found)} in {selected}')
    return found[0]


def state(ledger, key):
    """The ledger's word on a key as it stands on disk now, or None where it holds no such entry."""
    ledger.load()
    return next((row['state'] for row in ledger.data['entries'] if row['key'] == key), None)


def cost(ledger, plan):
    """Credits the plan's unsent calls will reserve: its props and building not yet in the ledger, and the remesh."""
    ledger.load(); held = {row['key'] for row in ledger.data['entries']}
    calls = [('prop', row['key']) for row in plan['props'].values()]
    if plan['building']:
        calls += [('building', plan['building']['key']), ('remesh', plan['building']['remesh'])]
    return sum(meshy.PRICES[operation] for operation, key in calls if key not in held)


def submit(ledger, plan, selected, work, *, run=meshy.run_cli, say=print):
    """Send every prop and the building that the ledger does not hold yet. Every reference is found before anything is
    sent, and the whole of what is unsent must fit under the cap, so a sheet is not left half submitted for want of an
    image or of credits. A call the ledger holds already is not sent again, and is refused if it was sent with another
    reference than the one selected now: the model it made is not of this reference, and a new key in the plan sends
    this one. No more is sent than Meshy's queue has room for, counting every call of the ledger that has
    not finished: the Ares Depot's eleventh call was refused and its key was lost to the CLI (2026-11-11). What is
    held back is said, and goes with the next `submit` after a `collect`. Returns the keys sent."""
    work = Path(work); work.mkdir(parents=True, exist_ok=True); sent = []
    pictures = {name: image(selected, name) for name in plan['props']}
    views = [image(selected, name) for name in plan['building']['views']] if plan['building'] else []
    need = cost(ledger, plan); ledger.load()
    require(ledger.committed() + need <= ledger.data['cap'],
            f'The plan needs {need} more credits and the ledger has {ledger.data["cap"] - ledger.committed()} left under its cap of {ledger.data["cap"]}')
    calls = [(row['key'], name, 'prop', [pictures[name]], lambda name=name, row=row: meshy.prop_arguments(pictures[name], row['triangles'])) for name, row in plan['props'].items()]
    if plan['building']:
        calls.append((plan['building']['key'], 'building', 'building', views, lambda: meshy.building_arguments(views)))
    for key, _, _, chosen, _ in calls:  # before anything is sent
        if state(ledger, key) is not None:
            was, now = meshy.sent_images(ledger.entry(key)), [path.name for path in chosen]
            require(was is None or was == now, f'{key} was sent with {", ".join(was or [])} and {", ".join(now)} is selected now: give it a new key in the plan')
    held = []
    for key, asset, operation, _, arguments in calls:
        if state(ledger, key) is not None:
            continue
        if sum(row['state'] in QUEUED for row in ledger.data['entries']) >= meshy.QUEUE:  # `state` has just read the ledger afresh
            held.append(key); continue
        task = meshy.submit(ledger, key, asset, operation, arguments(), work, run=run)
        sent.append(key); say(json.dumps({'key': key, 'task': task}), flush=True)
    if held:
        say(json.dumps({'held': held, 'why': f'Meshy holds {meshy.QUEUE} tasks at once: collect, then submit again'}), flush=True)
    return sent


def collect(ledger, plan, work, models, masters, *, run=meshy.run_cli, say=print):
    """Wait for whatever is still running and download what has finished: each prop into `models/<key>`, the
    building's full generation into `masters/<key>` and its remesh into `models/<remesh key>`. One call that failed
    does not stop the rest. Returns {failed: [keys], downloaded: [keys], unsent: [keys]}: `failed` is every call that
    has not ended in a working model, whether it failed now or in an earlier run, under the key that failed (the
    remesh's own, for a remesh), and `unsent` what `submit` has still to send."""
    work, models, masters = Path(work), Path(models), Path(masters); failed, downloaded, unsent = [], [], []
    for folder in (work, models, masters):
        folder.mkdir(parents=True, exist_ok=True)
    report = lambda **fields: say(json.dumps(fields), flush=True)

    def finished(key, target=None):
        """Whether the call has succeeded, waited for if it is running. One not sent yet is told as unsent; any other
        end is an error, in this run as in the one it ended in. So is a call that was sent for another polycount than
        the plan now gives it (`target`): the ledger's model is then not the plan's, and a new key sends the plan's."""
        if state(ledger, key) is not None:
            asked = meshy.sent_target(ledger.entry(key))
            require(target is None or asked == target, f'{key} was sent for {asked} triangles and the plan now asks {target}: give it a new key in the plan')
        if state(ledger, key) in WAITING:
            report(key=key, **meshy.wait(ledger, key, work, run=run))
        now = state(ledger, key)
        if now is None:
            unsent.append(key); return False
        require(now == 'succeeded', f'{key} is {now}')
        return True

    def fetched(key, bank, master=False):
        if bank.exists():  # `download` leaves a model that came back over its ceiling where it landed, and says so in the ledger
            require(ledger.entry(key).get('accepted') is not False, f'{key} is over its triangle ceiling and is no working model: {bank}')
            return
        report(key=key, **{'master' if master else 'downloaded': meshy.download(ledger, key, work, bank, master=master, run=run)}); downloaded.append(key)

    for row in plan['props'].values():
        try:
            if finished(row['key'], row['triangles']):
                fetched(row['key'], models / row['key'])
        except ValueError as error:
            failed.append(row['key']); report(key=row['key'], error=str(error))
    building = plan['building']
    if building:
        key = building['key']
        try:
            if finished(key):
                fetched(key, masters / key, master=True)
                task = ledger.entry(key)['taskId']; key = building['remesh']  # what fails from here on is the remesh
                if state(ledger, key) is None:
                    report(key=key, task=meshy.submit(ledger, key, 'building', 'remesh', meshy.remesh_arguments(task, building['triangles']), work, run=run))
                if finished(key, meshy.remesh_target(building['triangles'])):
                    fetched(key, models / key)
        except ValueError as error:
            failed.append(key); report(key=key, error=str(error))
    return {'failed': failed, 'downloaded': downloaded, 'unsent': unsent}


def status(ledger, plan):
    """Each call of the plan with the ledger's word on it, and the credits the plan and the ledger stand at."""
    ledger.load(); held = {row['key']: row['state'] for row in ledger.data['entries']}  # read once: nothing here waits
    keys = [row['key'] for row in plan['props'].values()] + ([plan['building']['key'], plan['building']['remesh']] if plan['building'] else [])
    return {'calls': {key: held.get(key) for key in keys}, 'unplanned': plan['unplanned'], 'unsentCredits': cost(ledger, plan), 'cap': ledger.data['cap'],
            'committed': ledger.committed()}
