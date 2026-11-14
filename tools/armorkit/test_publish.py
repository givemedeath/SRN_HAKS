"""A publication copies bakes into the pack, merges the tables without a gap or a changed row, and fails by gate."""
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from . import export, publish, registry, tables
from .test_registry import document, part
from .test_tables import stock

NUMBER = 6020
CHEST = part(number=NUMBER, set='facility', group='corpsec', tiers={'neck': 2, 'shoulder': 2, 'waist': 2})
PELVIS = part(slot='pelvis', number=NUMBER, set='facility', group='corpsec', genderedCut=False, tiers={'waist': 2, 'hip': 2})
SHIN = part(slot='shin', number=NUMBER, set='facility', group='corpsec', genderedCut=False, tiers={'knee': 2, 'ankle': 2})
PARTS = [CHEST, PELVIS, SHIN]
TOKENS = ('chest', 'pelvis', 'shinl', 'shinr')
MATERIAL = 'renderhint NormalTangents\ntexture1 {0}n\nparameter float Roughness 0.8\n'
BRIEF = {'schemaVersion': 1, 'kind': 'srn-armorkit-brief', 'model': 'facility-test', 'materials': [{'name': 'fabric'}, {'name': 'plates'}]}


def named(path):
    """A stand-in for `publish.model_textures`: a test model names the texture of its own name."""
    return [Path(path).stem]


def named_human(path):
    """A model that names the Human Fit model's texture in place of its own."""
    stem = Path(path).stem
    return [stem[:2] + 'h0' + stem[4:]]


def sound(pack, body_pack, body, model):
    return {'rest': 0.0, 'bent': 0.0, 'collar': 0.01, 'shown': 0.5, 'through': {'share': 0.0, 'most': 0.0}}, []


def drawn(parts, pack, body_pack):
    """A stand-in for `publish.icons`: an icon for each gender whose Human Fit model is in the pack."""
    made = {}
    for one in parts:
        for gender, body in publish.ICON_SOURCES.items():
            for token in registry.tokens(one):
                if one['slot'] in publish.ICON_SLOTS and registry.model_name(body, token, one['number']) + '.mdl' in pack:
                    made[publish.icon_name(gender, token, one['number']) + '.plt'] = b'icon ' + gender.encode()
    return made


def bake(folder, body, number=NUMBER, tokens=TOKENS, passed=True, model='facility-test'):
    """A bake's output folder as `bake.run` leaves it, with stand-in payloads."""
    folder = Path(folder)
    resources = folder / 'resources'
    resources.mkdir(parents=True)
    models = {token: registry.model_name(body, token, number) for token in tokens}
    for name in models.values():
        (resources / (name + '.mdl')).write_bytes(bytes(4) + name.encode())
        (resources / (name + '.plt')).write_bytes(b'tint ' + name.encode())
        (resources / (name + '.mtr')).write_bytes(MATERIAL.format(name).encode('ascii'))
        (resources / (name + 'n.tga')).write_bytes(b'relief ' + name.encode())
    record = {'model': model, 'body': body, 'tier': 2, 'number': number, 'models': models,
              'materials': [{'name': 'fabric', 'kind': 'cloth'}, {'name': 'plates', 'kind': 'metal'}],
              'gates': {'passed': passed, 'failures': [] if passed else ['chest: 9000 triangles'], 'triangles': {'outfit': 100}}, 'compiled': len(models)}
    (folder / 'bake.json').write_text(json.dumps(record), encoding='utf-8')
    return folder


SHARED = None  # bakes of every body, made once and only read: the outfit at NUMBER under `main`, a pair of gloves at 6030 under `hands`


def setUpModule():
    global SHARED
    holder = tempfile.TemporaryDirectory()
    unittest.addModuleCleanup(holder.cleanup)
    SHARED = Path(holder.name)
    for body in registry.BODIES:
        bake(SHARED / 'main' / body, body)
        bake(SHARED / 'hands' / body, body, number=6030, tokens=('handl', 'handr'))


def shared(bodies=registry.BODIES, outfit='main'):
    return [SHARED / outfit / body for body in bodies]


class Workspace(unittest.TestCase):
    """A stand-in repository, the stock tables, a registry, a brief and a history record, in a fresh folder."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repo, self.stock = self.root / 'repo', self.root / 'stock'
        for folder in (self.repo / 'srn_2da', self.repo / 'srn_body', self.repo / 'srn_armor', self.stock):
            folder.mkdir(parents=True)
        (self.repo / 'srn_2da' / 'skyboxes.2da').write_bytes(b'2DA V2.0\n')
        (self.repo / 'hakbuilder.json').write_text(json.dumps({'OutputPath': './output/', 'HakList': [
            {'Name': name, 'Path': f'./{name}/', 'CompileModels': False} for name in ('srn_2da', 'srn_armor', 'srn_head')]}, indent=2) + '\n', encoding='utf-8')
        (self.repo / 'PROVENANCE.md').write_text('## Facility Security (`srn_parts`)\n\nfacility-test, from the local engine.\n', encoding='utf-8')
        for table in registry.TABLES:
            (self.stock / (table + '.2da')).write_bytes(stock(table).encode('cp1252'))
        self.registry = self.root / 'registry.json'
        self.registry.write_text(json.dumps(document(*PARTS)), encoding='utf-8')
        self.brief = self.root / 'facility-test.json'
        self.brief.write_text(json.dumps(BRIEF), encoding='utf-8')
        self.ledger = self.root / 'trial-ledger.json'
        self.ledger.write_text('{"attempts": 1}', encoding='utf-8')

    def publish(self, bakes, **changes):
        options = {'records': [('facility-test', self.ledger)], 'briefs': [('facility-test', self.brief)], 'repo': self.repo,
                   'textures': named, 'measure_neck': sound, 'draw_icons': drawn, **changes}
        return publish.publish(options.pop('registry', self.registry), bakes, self.stock, **options)



class SurveyTests(Workspace):
    def test_a_bake_gives_each_model_with_its_tint_material_and_maps(self):
        found = publish.survey(bake(self.root / 'one', 'pmh0'))
        self.assertEqual(found['wrong'], [])
        self.assertEqual(sorted(found['files']), sorted(f'pmh0_{token}{NUMBER}{end}' for token in TOKENS for end in ('.mdl', '.plt', '.mtr', 'n.tga')))

    def test_what_is_wrong_with_a_bake_names_the_model(self):
        folder = bake(self.root / 'one', 'pfh0', passed=False)
        (folder / 'resources' / f'pfh0_chest{NUMBER}n.tga').unlink()
        (folder / 'resources' / f'pfh0_pelvis{NUMBER}.mdl').write_bytes(b'#MAXMODEL ASCII\n')
        wrong = dict(publish.survey(folder)['wrong'])
        self.assertIn('9000 triangles', wrong['pfh0 facility-test'])
        self.assertEqual(wrong[f'pfh0_chest{NUMBER}'], f'the bake holds no pfh0_chest{NUMBER}n.tga')
        self.assertEqual(wrong[f'pfh0_pelvis{NUMBER}'], 'the model is not compiled')

    def test_a_folder_that_is_no_bake_or_names_another_model_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'holds no bake'):
            publish.survey(self.root)
        folder = bake(self.root / 'one', 'pmh0')
        record = json.loads((folder / 'bake.json').read_text(encoding='utf-8'))
        record['models']['chest'] = 'pmh0_chest333'
        (folder / 'bake.json').write_text(json.dumps(record), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'is not the model of chest 6020 on pmh0'):
            publish.survey(folder)


class TableTests(Workspace):
    def test_only_tables_with_a_live_row_are_made_and_they_have_no_gap(self):
        made = publish.merged(PARTS, self.stock, self.repo / 'srn_2da')
        self.assertEqual(sorted(made), ['parts_chest', 'parts_pelvis', 'parts_shin'])
        for table, text in made.items():
            self.assertNotIn('\r', text)
            columns, rows = tables.parse(text)
            self.assertEqual(len(rows), NUMBER + 1)
            self.assertEqual(rows[:201], tables.parse(stock(table))[1])
            self.assertTrue(all(row == ['****', '****'] for row in rows[201:NUMBER]))
            self.assertEqual(rows[NUMBER], ['0', '0.00'])

    def test_a_padding_row_may_become_live_and_no_other_row_may_change(self):
        folder = self.repo / 'srn_2da'
        for table, text in publish.merged(PARTS, self.stock, folder).items():
            (folder / (table + '.2da')).write_bytes(text.encode('cp1252'))
        more = PARTS + [part(number=6030, set='siteguard', group='corpsec')]
        again = publish.merged(more, self.stock, folder)
        self.assertEqual(len(tables.parse(again['parts_chest'])[1]), 6031)
        self.assertEqual(sorted(again), ['parts_chest', 'parts_pelvis', 'parts_shin'])  # a table already there is kept up
        with self.assertRaisesRegex(ValueError, 'parts_chest: the table would lose rows'):
            publish.merged([PELVIS, SHIN, part(number=6010, set='patrol', group='corpsec')], self.stock, folder)
        text = (folder / 'parts_chest.2da').read_text(encoding='cp1252').replace(f'{NUMBER} 0             0.00', f'{NUMBER} 0             4.00')
        (folder / 'parts_chest.2da').write_bytes(text.encode('cp1252'))
        with self.assertRaisesRegex(ValueError, f'parts_chest: row {NUMBER} would change from 0 4.00 to 0 0.00'):
            publish.merged(more, self.stock, folder)

    def test_a_stock_folder_without_the_table_is_refused(self):
        (self.stock / 'parts_chest.2da').unlink()
        with self.assertRaisesRegex(ValueError, 'holds no parts_chest.2da'):
            publish.merged(PARTS, self.stock, self.repo / 'srn_2da')


class GateTests(Workspace):
    def pack(self, bodies):
        files = {}
        for folder in shared(bodies):
            files.update(publish.survey(folder)['files'])
        (self.root / 'gate').mkdir()
        for name, blob in drawn(PARTS, files, None).items():
            (self.root / 'gate' / name).write_bytes(blob)
            files[name] = self.root / 'gate' / name
        return files

    def failures(self, pack, textures=named, measure_neck=sound, clash=()):
        texts = publish.merged(PARTS, self.stock, self.repo / 'srn_2da')
        return publish.gates(PARTS, pack, texts, self.repo / 'srn_body', clash, textures, measure_neck)

    def test_every_body_listed_needs_its_models(self):
        found = self.failures(self.pack(('pmh0', 'pfh0')))
        self.assertEqual({one['gate'] for one in found}, {'bodies'})
        self.assertEqual(len(found), 18 * len(TOKENS))
        self.assertEqual(sorted({one['model'][:4] for one in found}), sorted(set(registry.BODIES) - {'pmh0', 'pfh0'}))
        self.assertIn({'gate': 'bodies', 'model': f'pmd0_chest{NUMBER}', 'reason': f'pmd0 has no model of chest {NUMBER}: bake or refit the outfit on that body'}, found)

    def test_all_twenty_bodies_pass(self):
        self.assertEqual(self.failures(self.pack(registry.BODIES)), [])

    def test_a_texture_a_model_names_must_be_in_the_pack_with_its_material_and_maps(self):
        pack = self.pack(registry.BODIES)
        del pack[f'pfo2_shinl{NUMBER}.plt'], pack[f'pmg0_chest{NUMBER}n.tga'], pack[f'pme2_pelvis{NUMBER}.mtr']
        found = self.failures(pack)
        self.assertEqual({(one['gate'], one['model'], one['reason']) for one in found if one['gate'] == 'closure'}, {
            ('closure', f'pfo2_shinl{NUMBER}', f'it names pfo2_shinl{NUMBER}, and the pack holds no pfo2_shinl{NUMBER}.plt'),
            ('closure', f'pmg0_chest{NUMBER}', f'its material file names pmg0_chest{NUMBER}n, and the pack holds no pmg0_chest{NUMBER}n.tga'),
            ('closure', f'pme2_pelvis{NUMBER}', f'it names pme2_pelvis{NUMBER}, and the pack holds no pme2_pelvis{NUMBER}.mtr')})
        # the map of the material file that went is no part's any more
        self.assertEqual([(one['gate'], one['model']) for one in found if one['gate'] != 'closure'], [('unlisted', f'pme2_pelvis{NUMBER}n.tga')])

    def test_a_model_that_names_another_models_texture_fails(self):
        found = self.failures(self.pack(registry.BODIES), textures=named_human)
        self.assertEqual({one['gate'] for one in found}, {'closure', 'unlisted'})  # their own textures are then no model's
        found = [one for one in found if one['gate'] == 'closure']
        self.assertEqual(len(found), 18 * len(TOKENS))  # every model but the Human Fit ones, which name their own
        self.assertIn('not its own', found[0]['reason'])
        pack = {name: path for name, path in self.pack(registry.BODIES).items()
                if name.endswith('.mdl') or name[:2] == 'ip' or name[2:4] == 'h0'}
        self.assertEqual({one['gate'] for one in self.failures(pack)}, {'closure'})  # and its own must be in the pack

    def test_a_name_another_pack_holds_a_stray_file_and_a_carriage_return_fail(self):
        pack = self.pack(registry.BODIES)
        (self.repo / 'srn_armor' / f'pmh0_chest{NUMBER}.mdl').write_bytes(b'theirs')
        stray = self.root / 'gate' / 'pmh0_chest333.mdl'
        stray.write_bytes(bytes(4))
        pack['pmh0_chest333.mdl'] = stray
        material = self.root / 'gate' / f'pfh0_chest{NUMBER}.mtr'
        material.write_bytes(Path(pack[material.name]).read_bytes().replace(b'\n', b'\r\n'))
        pack[material.name] = material
        found = self.failures(pack, clash=[self.repo / 'srn_body', self.repo / 'srn_armor'])
        self.assertEqual(sorted((one['gate'], one['model']) for one in found),
                         [('clash', f'pmh0_chest{NUMBER}.mdl'), ('format', f'pfh0_chest{NUMBER}.mtr'), ('unlisted', 'pmh0_chest333.mdl')])
        self.assertEqual([one['reason'] for one in found if one['gate'] == 'clash'], ['srn_armor holds a file of that name'])

    def test_a_chest_that_fails_its_neck_and_a_part_without_icons_fail(self):
        pack = self.pack(registry.BODIES)
        del pack[f'ipf_pelvis{NUMBER}.plt']
        short = lambda pack, body_pack, body, model: ({}, ['the lower end of the neck stands 2.0 cm out'] if body == 'pfg2' else [])
        found = self.failures(pack, measure_neck=short)
        self.assertEqual(found, [{'gate': 'neck', 'model': f'pfg2_chest{NUMBER}', 'reason': 'the lower end of the neck stands 2.0 cm out'},
                                 {'gate': 'icons', 'model': f'ipf_pelvis{NUMBER}', 'reason': f'pelvis {NUMBER} has no inventory icon ipf_pelvis{NUMBER}.plt'}])

    def test_a_part_without_its_table_row_fails(self):
        pack = self.pack(registry.BODIES)
        texts = publish.merged([CHEST, SHIN], self.stock, self.repo / 'srn_2da')
        found = publish.gates(PARTS, pack, texts, self.repo / 'srn_body', (), named, sound)
        self.assertEqual(found, [{'gate': 'tables', 'model': f'pelvis {NUMBER}', 'reason': f'parts_pelvis.2da has no live row {NUMBER}'}])


def tube(radius, low, high, sides=24):
    """A closed tube about the z axis, as (vertices, faces) wound to face out."""
    angle = np.linspace(0, 2 * np.pi, sides, endpoint=False)
    ring = np.stack([radius * np.cos(angle), radius * np.sin(angle)], axis=1)
    vertices = np.concatenate([np.column_stack([ring, np.full(sides, low)]), np.column_stack([ring, np.full(sides, high)]), [[0, 0, low], [0, 0, high]]])
    faces = []
    for k in range(sides):
        n = (k + 1) % sides
        faces += [(k, n, sides + n), (k, sides + n, sides + k), (2 * sides, n, k), (2 * sides + 1, sides + k, sides + n)]
    return vertices, np.array(faces)


def joined(*meshes):
    vertices, faces, start = [], [], 0
    for mesh in meshes:
        vertices.append(mesh[0])
        faces.append(mesh[1] + start)
        start += len(mesh[0])
    return np.concatenate(vertices), np.concatenate(faces)


class NeckTests(unittest.TestCase):
    NECK = tube(0.05, -0.07, 0.12)
    PLANE = (np.zeros(3), np.array((0.0, 0.0, 1.0)))

    def measure(self, chest, bend=18.5):
        return publish.neck(chest, self.NECK, *self.PLANE, bend, grain=0.008)  # twice the grain of a real measure, a quarter of the points

    def test_a_chest_that_holds_the_necks_end_and_leaves_its_top_free_passes(self):
        measure, reasons = self.measure(tube(0.2, -0.5, 0.02))
        self.assertEqual(reasons, [])
        self.assertEqual((measure['rest'], measure['bent'], measure['through']['share']), (0.0, 0.0, 0.0))
        self.assertAlmostEqual(measure['collar'], 0.02, delta=0.006)

    def test_a_collar_below_the_necks_end_shows_it(self):
        measure, reasons = self.measure(tube(0.2, -0.5, -0.1))
        self.assertAlmostEqual(measure['rest'], 0.04, delta=0.004)  # the end's top is 4 cm above the collar
        self.assertRegex(reasons[0], r'the lower end of the neck stands [34]\.\d cm out of the chest at rest, over the 0\.5 cm allowed')

    def test_an_end_just_under_the_collar_shows_when_the_neck_turns(self):
        chest = joined(tube(0.052, -0.5, -0.05), tube(0.2, -0.5, -0.1))  # a narrow collar the end stands in, on wide shoulders
        measure, reasons = self.measure(chest, bend=45.0)
        self.assertEqual(measure['rest'], 0.0)
        self.assertGreater(measure['bent'], 0.01)
        self.assertEqual(len(reasons), 1)
        self.assertRegex(reasons[0], r'out of the chest turned 45 degrees, over the 1\.0 cm allowed')
        self.assertEqual(self.measure(chest, bend=None)[1], [])

    def test_a_collar_over_the_necks_top_fails(self):
        self.assertEqual(self.measure(tube(0.2, -0.5, 0.2))[1], ['the chest closes over the top of the neck, where the head sits'])

    def test_skin_below_a_collar_band_is_through_it(self):
        measure, reasons = self.measure(joined(tube(0.2, -0.5, 0.0), tube(0.2, 0.04, 0.06)))  # the neck bare between the chest and a band
        self.assertGreater(measure['through']['share'], 0.1)
        self.assertEqual(len(reasons), 1)
        self.assertRegex(reasons[0], r'the neck shows through the chest below its collar: .*, up to (1[5-9]|20) mm out, 0\.\d to 3\.\d cm from the neck plane')


class IconTests(unittest.TestCase):
    def test_a_surface_is_drawn_from_the_front_in_its_texels_layers(self):
        # a square 20 cm a side at the waist, its left half one layer and its right half another
        vertices = np.array([(-0.1, 0.0, 1.0), (0.1, 0.0, 1.0), (0.1, 0.0, 1.2), (-0.1, 0.0, 1.2)])
        uvs = np.array([(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)])
        shades, layers = np.array([[100, 200], [100, 250]], np.uint8), np.array([[4, 2], [4, 2]], np.uint8)
        hidden = (vertices + (0.0, -0.05, 0.0), np.array([(0, 1, 2), (0, 2, 3)]), uvs, np.full((1, 1), 30, np.uint8), np.full((1, 1), 6, np.uint8))
        shade, layer = publish.icon([(vertices, np.array([(0, 1, 2), (0, 2, 3)]), uvs, shades, layers), hidden], 1.0)
        self.assertEqual(shade.shape, (128, 64))
        box = np.zeros((128, 64), bool)
        box[publish.ICON_WAIST:publish.ICON_WAIST + 20, 22:42] = True
        self.assertTrue((shade[~box] == publish.ICON_CLEAR).all())
        self.assertTrue((layer[publish.ICON_WAIST:publish.ICON_WAIST + 20, 22:32] == 4).all() and (layer[publish.ICON_WAIST:publish.ICON_WAIST + 20, 32:42] == 2).all())
        self.assertEqual(shade[publish.ICON_WAIST + 2, 25], 100)
        self.assertEqual(shade[publish.ICON_WAIST + 18, 40], publish.ICON_BRIGHT)  # 250 would come out black in the game
        clipped = publish.icon([(vertices, np.array([(0, 1, 2), (0, 2, 3)]), uvs, shades, layers)], 1.0, (publish.ICON_WAIST + 10, None))[0]
        self.assertTrue((clipped[:publish.ICON_WAIST + 10] == publish.ICON_CLEAR).all() and (clipped[publish.ICON_WAIST + 10:publish.ICON_WAIST + 20, 22:42] != publish.ICON_CLEAR).all())
        self.assertEqual(export.read_tint(export.tint(shade, layer))[0].shape, (128, 64))

    def test_only_the_slots_the_game_draws_have_icons(self):
        self.assertEqual(publish.icon_names(CHEST), [f'ipm_chest{NUMBER}', f'ipf_chest{NUMBER}'])
        self.assertEqual(publish.icon_names(SHIN), [])
        self.assertEqual(publish.icon_names(part(slot='shoulder', number=1000, families=['accessory'], set=..., group=..., genderedCut=False, tiers={}, sides=['l'])),
                         ['ipm_shol1000', 'ipf_shol1000'])
        self.assertEqual(publish.icon_name('m', 'belt', 7), 'ipm_belt007')


class PublishTests(Workspace):
    def test_a_trial_writes_the_pack_tables_and_records_whatever_the_gates_say(self):
        trial = self.root / 'trial'
        report = self.publish(shared(('pmh0', 'pfh0')), root=trial, trial=True)
        self.assertFalse(report['passed'])
        self.assertEqual(report['failuresByGate'], {'bodies': 18 * len(TOKENS)})
        self.assertEqual(len(report['bodiesWithoutModels']), 18)
        self.assertTrue(report['written'] and report['trial'])
        self.assertEqual(report['skipped'], [])
        pack = sorted(path.name for path in (trial / 'srn_parts').iterdir())
        self.assertEqual(len(pack), 2 * len(TOKENS) * 4 + 4)  # model, tint, material and map each, and four icons
        self.assertIn(f'ipf_chest{NUMBER}.plt', pack)
        self.assertEqual((trial / 'srn_parts' / f'pfh0_shinr{NUMBER}.plt').read_bytes(), b'tint pfh0_shinr6020')
        self.assertTrue((trial / 'srn_2da' / 'skyboxes.2da').is_file())  # seeded from the repository's tables
        self.assertNotIn(b'\r', (trial / 'srn_2da' / 'parts_chest.2da').read_bytes())
        self.assertEqual(registry.load(trial / publish.REGISTRY, publish=True), registry.validate(document(*PARTS)))
        handoff = json.loads((trial / publish.HANDOFF).read_text(encoding='utf-8'))
        self.assertEqual((handoff['kind'], handoff['pack'], handoff['tables']), (publish.HANDOFF_KIND, 'srn_parts', ['parts_chest', 'parts_pelvis', 'parts_shin']))
        self.assertEqual(handoff['icons'], [f'ipf_chest{NUMBER}', f'ipf_pelvis{NUMBER}', f'ipm_chest{NUMBER}', f'ipm_pelvis{NUMBER}'])
        outfit = handoff['outfits'][1]
        self.assertEqual((outfit['model'], outfit['body'], outfit['number']), ('facility-test', 'pfh0', NUMBER))
        self.assertEqual(outfit['brief'], {'name': 'facility-test.json', 'sha256': publish.sha(self.brief)})
        self.assertEqual(outfit['bake']['sha256'], publish.sha(SHARED / 'main' / 'pfh0' / 'bake.json'))
        self.assertEqual(outfit['records'], [{'name': 'trial-ledger.json', 'sha256': publish.sha(self.ledger), 'bytes': 15}])
        self.assertEqual(len(outfit['resources']), len(TOKENS) * 4)
        # nothing of it is in the repository
        self.assertFalse((self.repo / 'srn_parts').exists() or (self.repo / publish.REGISTRY).exists())
        self.assertEqual(sorted(path.name for path in (self.repo / 'srn_2da').iterdir()), ['skyboxes.2da'])
        self.assertEqual(json.loads((trial / 'publish-report.json').read_text(encoding='utf-8'))['failuresByGate'], report['failuresByGate'])

    def test_the_repository_is_written_only_when_every_gate_passes(self):
        report = self.publish(shared(('pmh0', 'pfh0')))
        self.assertFalse(report['passed'] or report['written'])
        self.assertFalse((self.repo / 'srn_parts').exists() or (self.repo / publish.REGISTRY).exists())
        self.assertNotIn('srn_parts', (self.repo / 'hakbuilder.json').read_text(encoding='utf-8'))
        dry = self.publish(shared(), dry_run=True)
        self.assertTrue(dry['passed'] and not dry['written'] and not (self.repo / 'srn_parts').exists())
        report = self.publish(shared())
        self.assertTrue(report['passed'] and report['written'])
        self.assertEqual(len(list((self.repo / 'srn_parts').iterdir())), 20 * len(TOKENS) * 4 + 4)
        names = [pack['Name'] for pack in json.loads((self.repo / 'hakbuilder.json').read_text(encoding='utf-8'))['HakList']]
        self.assertEqual(names, ['srn_2da', 'srn_armor', 'srn_parts', 'srn_head'])
        self.assertEqual(sorted(path.name for path in (self.repo / 'srn_2da').iterdir()), ['parts_chest.2da', 'parts_pelvis.2da', 'parts_shin.2da', 'skyboxes.2da'])

    def test_a_second_publication_adds_to_the_first_and_may_not_change_it(self):
        self.publish(shared())
        with self.assertRaisesRegex(ValueError, 'holds no part that is not published already'):
            self.publish(shared(('pmh0',)))
        changed = self.root / 'changed.json'
        changed.write_text(json.dumps(document({**CHEST, 'channels': ['cloth1']}, PELVIS, SHIN)), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'chest 6020 is published and may not change or leave the registry'):
            self.publish(shared(('pmh0',)), registry=changed)
        more = self.root / 'more.json'
        hands = part(slot='hand', number=6030, set='siteguard', group='corpsec', genderedCut=False, tiers={'wrist': 2})
        more.write_text(json.dumps(document(*PARTS, hands)), encoding='utf-8')
        measured = []
        changed_file = self.repo / 'srn_parts' / f'pmh0_chest{NUMBER}.plt'
        kept_bytes = changed_file.read_bytes()
        changed_file.write_bytes(b'edited')
        drift = self.publish(shared(outfit='hands'), registry=more, dry_run=True)
        self.assertEqual([(one['gate'], one['model']) for one in drift['failures']], [('published', changed_file.name)])
        changed_file.write_bytes(kept_bytes)
        report = self.publish(shared(outfit='hands'), registry=more, measure_neck=lambda *given: (measured.append(given[3]), sound(*given))[1])
        self.assertEqual(measured, [])  # the chests published earlier are not measured again
        self.assertTrue(report['passed'] and report['written'])
        self.assertEqual(report['newParts'], ['hand 6030'])
        handoff = json.loads((self.repo / publish.HANDOFF).read_text(encoding='utf-8'))
        self.assertEqual(len(handoff['outfits']), 40)
        self.assertEqual(len(tables.parse((self.repo / 'srn_2da' / 'parts_hand.2da').read_text(encoding='cp1252'))[1]), 6031)
        self.assertEqual(len(tables.parse((self.repo / 'srn_2da' / 'parts_chest.2da').read_text(encoding='cp1252'))[1]), NUMBER + 1)

    def test_a_bake_at_another_number_a_failed_bake_and_missing_records_fail_by_name(self):
        folders = shared(registry.BODIES[1:]) + [bake(self.root / 'bakes' / 'pmh0', 'pmh0', number=333, passed=False)]
        report = self.publish(folders, records=[], briefs=[], dry_run=True)
        by_gate = report['failuresByGate']
        self.assertEqual((by_gate['bodies'], by_gate['bake'], by_gate['records']), (len(TOKENS), len(TOKENS) + 1, 40))
        reasons = {one['model']: one['reason'] for one in report['failures'] if one['gate'] in ('bake', 'records')}
        self.assertIn('the registry has no new part chest 333 on pmh0', reasons['pmh0_chest333'])
        self.assertIn('--record facility-test=FILE', reasons['pfg2 facility-test'])
        self.assertTrue(any('no brief of facility-test' in one['reason'] for one in report['failures']))

    def test_provenance_is_a_gate_for_the_repository_and_set_aside_in_a_trial(self):
        (self.repo / 'PROVENANCE.md').write_text('nothing yet\n', encoding='utf-8')
        report = self.publish(shared(), dry_run=True)
        self.assertEqual(report['failuresByGate'], {'provenance': 2})
        self.assertEqual([one['model'] for one in report['failures']], ['srn_parts', 'facility-test'])
        trial = self.publish(shared(), root=self.root / 'trial', trial=True)
        self.assertTrue(trial['passed'])
        self.assertRegex(trial['skipped'][0], 'provenance: PROVENANCE.md names no srn_parts, facility-test')

    def test_a_trial_root_is_a_scratch_folder_and_never_the_repository(self):
        with self.assertRaisesRegex(ValueError, 'A trial is written to a scratch folder'):
            self.publish(shared(('pmh0',)), root=self.repo / 'docs', trial=True)
        other = self.root / 'other'
        other.mkdir()
        (other / 'file.txt').write_text('mine', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'is not empty and is no trial root'):
            self.publish(shared(('pmh0',)), root=other, trial=True)
        inside = self.repo / 'output' / 'trial'
        self.assertTrue(self.publish(shared(('pmh0',)), root=inside, trial=True)['written'])
        with self.assertRaisesRegex(ValueError, 'ask for one of them'):
            self.publish(shared(('pmh0',)), root=inside, trial=True, dry_run=True)
        with self.assertRaisesRegex(ValueError, 'holds a trial publication already'):
            self.publish(shared(('pmh0',)), root=inside, trial=True)
        made = self.root / 'unmade'
        with self.assertRaisesRegex(ValueError, 'registry'):  # a registry that is refused leaves no trial root
            self.publish(shared(('pmh0',)), root=made, trial=True, registry=self.brief)
        self.assertFalse(made.exists())
        with self.assertRaisesRegex(ValueError, 'is a file, not a folder'):
            self.publish(shared(('pmh0',)), root=self.ledger, trial=True)

    def test_the_build_entry_is_added_once_after_the_armor_pack(self):
        text = (self.repo / 'hakbuilder.json').read_text(encoding='utf-8')
        once = publish.registered(text)
        self.assertEqual(publish.registered(once), once)
        self.assertIn({'Name': 'srn_parts', 'Path': './srn_parts/', 'CompileModels': False}, json.loads(once)['HakList'])
        with self.assertRaisesRegex(ValueError, 'indent-2 form'):
            publish.registered(json.dumps(json.loads(text)))

    def test_records_and_briefs_are_given_by_model(self):
        self.assertEqual(publish.pairs(['a=C:/x/y.json', 'a=z'], '--record'), [('a', 'C:/x/y.json'), ('a', 'z')])
        with self.assertRaisesRegex(ValueError, '--record is MODEL=FILE: ledger.json'):
            publish.pairs(['ledger.json'], '--record')
        with self.assertRaisesRegex(ValueError, '--record names a model no bake is of: other'):
            self.publish(shared(('pmh0',)), records=[('facility-test', self.ledger), ('other', self.ledger)], dry_run=True)
        with self.assertRaisesRegex(ValueError, '--brief names a model no bake is of: other'):
            self.publish(shared(('pmh0',)), briefs=[('facility-test', self.brief), ('other', self.brief)], dry_run=True)

        def undrawn(parts, pack, body_pack):
            raise FileNotFoundError('no pmh0.mdl')
        report = self.publish(shared(('pmh0',)), draw_icons=undrawn, dry_run=True)
        self.assertIn('the icons could not be drawn: no pmh0.mdl', [one['reason'] for one in report['failures'] if one['gate'] == 'icons'])
        two = self.root / 'briefs'
        two.mkdir()
        for name in ('a.json', 'b.json'):
            (two / name).write_text(json.dumps(BRIEF), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, '2 briefs are of the model facility-test'):
            publish.brief_of('facility-test', {}, two)
        self.assertEqual(publish.brief_of('facility-test', {'facility-test': two / 'b.json'}, two), two / 'b.json')
        self.assertIsNone(publish.brief_of('unknown', {}, two))


if __name__ == '__main__':
    unittest.main()
