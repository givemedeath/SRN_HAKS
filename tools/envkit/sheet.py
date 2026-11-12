"""A sheet's models through Meshy under the shared ledger, as the sheet's plan states them.

A plan (`tools/envkit/sets/<sheet>-meshy.json`) names the set, a short prefix for its ledger keys, each prop to make
with its triangle target, and the building's views and the ceiling it is remeshed to:

    {"set": "ares-depot", "prefix": "ares",
     "props": {"reception-desk": {"triangles": 12000}, "turret": {"triangles": 8000, "key": "ares-turret-a2"}},
     "building": {"views": ["building-hero", "building-front", "building-rear"], "triangles": 200000}}

A prop's key is `<prefix>-<asset>-a1` and the building's `<prefix>-building-a1`, its remesh that with `-remesh`,
unless the plan says otherwise (`key`, `remesh`): Meshy's CLI never sends a key twice, so a call that was refused
goes again under a new one, and the plan is where that is written down. `submit` sends whatever the ledger does not
hold yet; `collect` waits for each, downloads the props, keeps the building's full generation as a master, remeshes it
and downloads that. Both are safe to run again. This was a one-off script for the Stuffer Shack and the Ares Depot
(2026-11-10, 2026-11-11) and is here so that the next sheet is run from the repository."""
import json
import re
from pathlib import Path

from . import meshy, reference, require

PREFIX = re.compile(r'[a-z0-9]{2,12}')
WAITING = ('submitted', 'pending', 'in_progress')


def load_plan(path):
    """The plan at `path`, checked against the set it names (the set file beside it), with every key worked out:
    {set, prefix, props: {asset: {triangles, key}}, building: {views, triangles, key, remesh} or None}."""
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
                and isinstance(building['views'], list) and 1 <= len(building['views']) <= 4, 'A building states one to four views and the triangles it is remeshed to')
        for name in building['views']:
            require(name in assets and assets[name]['kind'] == 'building', f'{name} is not a building view of {plan["set"]}')
        require(type(building['triangles']) is int and 1000 <= building['triangles'] <= meshy.BUILDING_TRIANGLES,
                f'A building is remeshed to at most {meshy.BUILDING_TRIANGLES} triangles')
        key = building.get('key', f'{prefix}-building-a1')
        building = {'views': list(building['views']), 'triangles': building['triangles'], 'key': key, 'remesh': building.get('remesh', key + '-remesh')}
    keys = [row['key'] for row in props.values()] + ([building['key'], building['remesh']] if building else [])
    require(all(isinstance(key, str) and meshy.KEY.fullmatch(key) is not None for key in keys), 'Ledger keys are lowercase letters, digits and hyphens')
    require(len(set(keys)) == len(keys), 'Each call of a plan has its own ledger key')
    return {'set': plan['set'], 'prefix': prefix, 'props': props, 'building': building}


def image(selected, name):
    """The one reference image chosen for an asset: `<name>-s<seed>-b0.png` in the folder of selected references."""
    found = sorted(Path(selected).glob(name + '-s*-b0.png'))
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
    image or of credits. Returns the keys sent."""
    work = Path(work); work.mkdir(parents=True, exist_ok=True); sent = []
    pictures = {name: image(selected, name) for name in plan['props']}
    views = [image(selected, name) for name in plan['building']['views']] if plan['building'] else []
    need = cost(ledger, plan); ledger.load()
    require(ledger.committed() + need <= ledger.data['cap'],
            f'The plan needs {need} more credits and the ledger has {ledger.data["cap"] - ledger.committed()} left under its cap of {ledger.data["cap"]}')
    for name, row in plan['props'].items():
        if state(ledger, row['key']) is None:
            task = meshy.submit(ledger, row['key'], name, 'prop', meshy.prop_arguments(pictures[name], row['triangles']), work, run=run)
            sent.append(row['key']); say(json.dumps({'key': row['key'], 'task': task}), flush=True)
    if plan['building'] and state(ledger, plan['building']['key']) is None:
        key = plan['building']['key']
        task = meshy.submit(ledger, key, 'building', 'building', meshy.building_arguments(views), work, run=run)
        sent.append(key); say(json.dumps({'key': key, 'task': task}), flush=True)
    return sent


def collect(ledger, plan, work, models, masters, *, run=meshy.run_cli, say=print):
    """Wait for whatever is still running and download what has finished: each prop into `models/<key>`, the
    building's full generation into `masters/<key>` and its remesh into `models/<remesh key>`. One call that failed
    does not stop the rest. Returns {failed: [keys], downloaded: [keys]}."""
    work, models, masters = Path(work), Path(models), Path(masters); failed, downloaded = [], []
    for folder in (work, models, masters):
        folder.mkdir(parents=True, exist_ok=True)
    report = lambda **fields: say(json.dumps(fields), flush=True)

    def finished(key):
        if state(ledger, key) in WAITING:
            report(key=key, **meshy.wait(ledger, key, work, run=run))
        return state(ledger, key) == 'succeeded'

    def fetched(key, bank, master=False):
        if not bank.exists():
            report(key=key, **{'master' if master else 'downloaded': meshy.download(ledger, key, work, bank, master=master, run=run)}); downloaded.append(key)

    for row in plan['props'].values():
        try:
            if finished(row['key']):
                fetched(row['key'], models / row['key'])
        except ValueError as error:
            failed.append(row['key']); report(key=row['key'], error=str(error))
    building = plan['building']
    if building:
        try:
            if finished(building['key']):
                fetched(building['key'], masters / building['key'], master=True)
                if state(ledger, building['remesh']) is None:
                    task = ledger.entry(building['key'])['taskId']
                    report(key=building['remesh'], task=meshy.submit(ledger, building['remesh'], 'building', 'remesh',
                                                                     meshy.remesh_arguments(task, building['triangles']), work, run=run))
                if finished(building['remesh']):
                    fetched(building['remesh'], models / building['remesh'])
        except ValueError as error:
            failed.append(building['key']); report(key=building['key'], error=str(error))
    return {'failed': failed, 'downloaded': downloaded}


def status(ledger, plan):
    """Each call of the plan with the ledger's word on it, and the credits the plan and the ledger stand at."""
    rows = {row['key']: state(ledger, row['key']) for row in plan['props'].values()}
    if plan['building']:
        rows.update({plan['building'][part]: state(ledger, plan['building'][part]) for part in ('key', 'remesh')})
    ledger.load()
    return {'calls': rows, 'unsent': cost(ledger, plan), 'cap': ledger.data['cap'], 'committed': ledger.committed()}
