"""Blueprints for envkit placeables, and the palette that offers them to a builder.

A row of the placeables table is only a shape. What a builder paints is a blueprint (`.utp`): the shape with a name, a
tag and how it behaves. Blueprints in a hak are not on the Toolset's Custom tab, which lists the module's own. They
show on the Standard tab when the hak's `placeablepalstd.itp` lists them, so that file is rebuilt here: the game's own
list with these blueprints added, laid out on the pack's category tree (`placeablepal.itp`).

The fields of a blueprint are the game's own for a plain placeable (read off `plc_rubble.utp`, 2026-11-11)."""
import copy

from . import placeables, require

PALETTE = 'placeablepalstd.itp'
SKELETON = 'placeablepal.itp'
EVENTS = ('OnClosed', 'OnDamaged', 'OnDeath', 'OnDisarm', 'OnHeartbeat', 'OnInvDisturbed', 'OnLock', 'OnMeleeAttacked', 'OnOpen', 'OnSpellCastAt',
          'OnTrapTriggered', 'OnUnlock', 'OnUsed', 'OnUserDefined')


def field(kind, value):
    return {'type': kind, 'value': value}


def blueprint(resref, row, name, category, *, static=True, comment=''):
    """A scenery blueprint as nwn_gff's JSON: row `row` of the placeables table, named `name`, in palette category
    `category`. It cannot be destroyed or used. `static` makes it scenery no script can reach; one whose lights a
    script should be able to put out (`convert.lights_script`) is made not static."""
    require(placeables.RESREF.fullmatch(resref), 'A blueprint is named by a lowercase resref: ' + resref)
    require(type(row) is int and row >= 0 and type(category) is int and 0 <= category <= 255 and name, 'A blueprint needs its row, its name and a palette category: ' + resref)
    values = {'Appearance': ('dword', row), 'LocName': ('cexolocstring', {'0': name}), 'Description': ('cexolocstring', {}), 'Tag': ('cexostring', resref),
              'TemplateResRef': ('resref', resref), 'PaletteID': ('byte', category), 'Comment': ('cexostring', comment), 'Static': ('byte', 1 if static else 0),
              'Plot': ('byte', 1), 'Useable': ('byte', 0), 'HP': ('short', 15), 'CurrentHP': ('short', 15), 'Hardness': ('byte', 5), 'Fort': ('byte', 16),
              'Ref': ('byte', 0), 'Will': ('byte', 0), 'Faction': ('dword', 1), 'Conversation': ('resref', ''), 'Portrait': ('resref', ''), 'KeyName': ('cexostring', ''),
              'OpenLockDC': ('byte', 18), 'DisarmDC': ('byte', 15), 'TrapDetectable': ('byte', 1), 'TrapDisarmable': ('byte', 1), 'TrapOneShot': ('byte', 1),
              **{key: ('byte', 0) for key in ('AnimationState', 'AutoRemoveKey', 'BodyBag', 'CloseLockDC', 'HasInventory', 'Interruptable', 'KeyRequired', 'Lockable',
                                              'Locked', 'TrapDetectDC', 'TrapFlag', 'TrapType', 'Type')},
              **{key: ('resref', '') for key in EVENTS}}
    return {'__data_type': 'UTP ', **{key: field(*value) for key, value in sorted(values.items())}}


def palette(skeleton, stock, entries):
    """The standard palette (nwn_gff's JSON) on the pack's category tree: every blueprint the game's own palette
    lists, under the category it had, and `entries` ([{resref, name, category}]) under theirs. A category with no
    blueprint, and a branch with none below it, is left out, as the game's own palette leaves them out."""
    listed = {}

    def gather(nodes):
        for node in nodes:
            inner = node.get('LIST', {}).get('value', [])
            if 'ID' in node:
                listed.setdefault(node['ID']['value'], []).extend(copy.deepcopy(one) for one in inner if 'RESREF' in one)
            gather([one for one in inner if 'RESREF' not in one])
    gather(stock['MAIN']['value'])
    count = lambda nodes: sum(1 if 'RESREF' in node else count(node.get('LIST', {}).get('value', [])) for node in nodes)
    require(sum(map(len, listed.values())) == count(stock['MAIN']['value']), 'The game\'s palette lists blueprints outside any category: none may be left out')
    known = set()

    def identify(nodes):
        for node in nodes:
            if 'ID' in node:
                known.add(node['ID']['value'])
            identify(node.get('LIST', {}).get('value', []))
    identify(skeleton['MAIN']['value'])
    require(set(listed) <= known, 'The game lists blueprints under categories the pack\'s tree lacks: ' + ', '.join(map(str, sorted(set(listed) - known))))
    for entry in sorted(entries, key=lambda one: one['name']):
        require(entry['category'] in known, f'{entry["resref"]} names palette category {entry["category"]}, which the pack\'s tree lacks')
        require(all(one['RESREF']['value'] != entry['resref'] for rows in listed.values() for one in rows), 'The palette already lists ' + entry['resref'])
        listed.setdefault(entry['category'], []).append({'__struct_id': 0, 'NAME': field('cexostring', entry['name']), 'RESREF': field('resref', entry['resref'])})

    def build(nodes):
        made = []
        for node in nodes:
            below = build(node.get('LIST', {}).get('value', [])) + (listed.get(node['ID']['value'], []) if 'ID' in node else [])
            if below:
                made.append({'__struct_id': 0, **{key: copy.deepcopy(node[key]) for key in ('ID', 'STRREF', 'NAME') if key in node}, 'LIST': field('list', below)})
        return made
    return {'__data_type': 'ITP ', 'MAIN': field('list', build(skeleton['MAIN']['value']))}


def listing(document):
    """{resref: category} of every blueprint a palette lists."""
    found = {}

    def walk(nodes, category):
        for node in nodes:
            if 'RESREF' in node:
                found[node['RESREF']['value']] = category
            else:
                walk(node.get('LIST', {}).get('value', []), node['ID']['value'] if 'ID' in node else category)
    walk(document['MAIN']['value'], None)
    return found
