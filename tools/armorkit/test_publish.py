"""A publication copies bakes into the pack, merges the tables without a gap or a changed row, and fails by gate."""
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from . import export, logo, publish, registry, tables
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
                   'textures': named, 'measure_neck': sound, 'draw_icons': drawn, 'channels': lambda path: set(CHEST['channels']), **changes}
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
        whole = self.pack(registry.BODIES)
        found = self.failures(whole, textures=named_human)
        self.assertEqual({one['gate'] for one in found}, {'closure', 'unlisted'})  # their own textures are then no model's
        found = [one for one in found if one['gate'] == 'closure']
        self.assertEqual(len(found), 18 * len(TOKENS))  # every model but the Human Fit ones, which name their own
        self.assertIn('not its own', found[0]['reason'])
        pack = {name: path for name, path in whole.items()
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

    def test_a_model_or_material_file_that_cannot_be_read_fails_by_name(self):
        import struct
        pack = self.pack(registry.BODIES)

        def cut(path):
            raise struct.error('unpack_from requires a buffer of at least 12 bytes')
        found = self.failures(pack, textures=cut)
        self.assertEqual({one['gate'] for one in found}, {'closure', 'unlisted'})
        self.assertIn('the model could not be read', found[0]['reason'])
        pack[f'pmh0_chest{NUMBER}.mtr'] = self.root / 'other.mtr'  # its own file: the pack's are shared between the tests
        pack[f'pmh0_chest{NUMBER}.mtr'].write_bytes(b'texture1 caf\xc3\xa9\n')
        found = self.failures(pack)
        self.assertIn(('closure', f'its material file pmh0_chest{NUMBER}.mtr is not ASCII text'), [(one['gate'], one['reason']) for one in found])

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
    def test_a_part_lists_the_channels_its_tint_textures_use(self):
        with tempfile.TemporaryDirectory() as folder:  # a tint texture is read for the layers its texels are on
            tint = Path(folder) / 'tint.plt'
            blob = export.tint(np.full((2, 2), 170), np.array([[export.LAYERS['cloth1'], export.LAYERS['skin']], [export.LAYERS['cloth1']] * 2]))
            tint.write_bytes(blob[:-1] + bytes([9]))  # the last texel on a layer that is no channel of an outfit
            self.assertEqual(publish.tint_channels(tint), {'cloth1', 'skin', 'layer 9'})
            tint.write_bytes(blob[:-2])
            with self.assertRaisesRegex(ValueError, 'cut short'):
                publish.tint_channels(tint)
            tint.write_bytes(b'tint')
            with self.assertRaisesRegex(ValueError, 'no tint texture'):
                publish.tint_channels(tint)
        bakes = [bake(self.root / 'bakes' / 'pmh0', 'pmh0')]
        on = lambda *names: (lambda path: set(names))
        self.assertNotIn('channels', self.publish(bakes, dry_run=True)['failuresByGate'])
        report = self.publish(bakes, dry_run=True, channels=on('cloth1', 'leather2'))  # the parts list cloth1 and metal1
        reasons = sorted(one['reason'] for one in report['failures'] if one['gate'] == 'channels')
        self.assertEqual(len(reasons), 2 * len(PARTS))
        self.assertIn('has tint textures on leather2, which it does not list', reasons[0])
        self.assertIn('lists metal1, which none of its tint textures use', reasons[-1])
        unread = self.publish(bakes, dry_run=True, channels=publish.tint_channels)  # the stand-in payloads are no tint textures
        self.assertEqual(unread['failuresByGate']['channels'], len(PARTS))

    def test_a_registry_part_carries_the_colours_its_bakes_suggest(self):
        navy, grey = [38, 48, 72], [52, 56, 62]
        record = {'number': NUMBER, 'models': {token: token for token in TOKENS}, 'materials': [
            {'name': 'fabric', 'channels': ['cloth1', 'cloth2'], 'suggested': navy}, {'name': 'gear', 'channels': ['leather1', 'leather2']},
            {'name': 'plates', 'channels': ['metal1', 'metal2'], 'suggested': grey}, {'name': 'trim', 'channels': ['metal1', 'metal2'], 'suggested': navy}]}
        # both of a material's channels, none for a material that suggests nothing, none where two materials differ
        self.assertEqual(publish.suggested(record), {'cloth1': navy, 'cloth2': navy})
        self.assertEqual(publish.suggested(record, ['cloth2', 'metal1']), {'cloth2': navy})
        filled, changed = publish.coloured(document(*PARTS, part(slot='hand', number=6030, genderedCut=False, tiers={})), [record])
        self.assertEqual(changed, [('chest', NUMBER), ('pelvis', NUMBER), ('shin', NUMBER)])
        self.assertEqual([one.get('colours') for one in filled['parts']], [{'cloth1': navy}] * 3 + [None])  # the stand-in parts have no second cloth channel
        self.assertEqual(publish.coloured(filled, [record])[1], [])
        bare, taken = publish.coloured(filled, [{**record, 'materials': []}])  # bakes that suggest nothing: the colours go
        self.assertEqual((len(taken), [one.get('colours') for one in bare['parts']]), (3, [None] * 4))
        with self.assertRaisesRegex(ValueError, 'different colours: .*pmh0.*pfh0'):
            publish.coloured(document(*PARTS), [{**record, 'body': 'pmh0'}, {**record, 'body': 'pfh0', 'materials': [{**record['materials'][0], 'suggested': grey}]}])
        # a publication says so where the registry leaves them out, and passes once they are written
        bakes = [bake(self.root / 'bakes' / 'pmh0', 'pmh0')]
        told = json.loads((bakes[0] / 'bake.json').read_text(encoding='utf-8'))
        told['materials'] = [{'name': 'fabric', 'kind': 'cloth', 'channels': ['cloth1', 'cloth2'], 'suggested': navy}, {'name': 'plates', 'kind': 'metal'}]
        (bakes[0] / 'bake.json').write_text(json.dumps(told), encoding='utf-8')
        report = self.publish(bakes, dry_run=True)
        self.assertEqual(report['failuresByGate']['colours'], len(PARTS))
        self.assertIn('--colours-from', [one['reason'] for one in report['failures'] if one['gate'] == 'colours'][0])
        self.registry.write_text(json.dumps(publish.coloured(json.loads(self.registry.read_text(encoding='utf-8')), [told])[0]), encoding='utf-8')
        self.assertNotIn('colours', self.publish(bakes, dry_run=True)['failuresByGate'])

    def test_a_map_that_is_one_image_on_two_bodies_is_published_once(self):
        bakes = [bake(self.root / 'bakes' / body, body) for body in ('pmh0', 'pmg0')]
        for token in ('shinl', 'shinr'):  # the troll's shins carry the Human's normal maps, as a refit leaves them
            human, troll = (registry.model_name(body, token, NUMBER) for body in ('pmh0', 'pmg0'))
            (bakes[1] / 'resources' / (troll + 'n.tga')).write_bytes((bakes[0] / 'resources' / (human + 'n.tga')).read_bytes())
        trial = self.root / 'trial'
        report = self.publish(bakes, root=trial, trial=True)
        # a map two models wear is named for the part and its image, not for either body
        left, right = (f'{token}{NUMBER}n_' + publish.sha(bakes[0] / 'resources' / f'pmh0_{token}{NUMBER}n.tga')[:4] for token in ('shinl', 'shinr'))
        self.assertEqual(report['sharedMaps'], {f'pmg0_shinl{NUMBER}n': left, f'pmh0_shinl{NUMBER}n': left, f'pmg0_shinr{NUMBER}n': right, f'pmh0_shinr{NUMBER}n': right})
        self.assertEqual(set(report['failuresByGate']), {'bodies', 'icons'})  # two male bodies of twenty; no map is missing, the gates read the rewritten files
        pack = trial / 'srn_parts'
        self.assertFalse((pack / f'pmg0_shinl{NUMBER}n.tga').exists() or (pack / f'pmh0_shinl{NUMBER}n.tga').exists())
        self.assertTrue((pack / (left + '.tga')).is_file() and (pack / f'pmg0_chest{NUMBER}n.tga').is_file())
        for body in ('pmh0', 'pmg0'):
            self.assertEqual((pack / f'{body}_shinl{NUMBER}.mtr').read_text(encoding='ascii'), MATERIAL.format(f'{body}_shinl{NUMBER}').replace(f'{body}_shinl{NUMBER}n', left))
        self.assertEqual((pack / f'pmg0_chest{NUMBER}.mtr').read_text(encoding='ascii'), MATERIAL.format(f'pmg0_chest{NUMBER}'))
        self.assertEqual((bakes[1] / 'resources' / f'pmg0_shinl{NUMBER}.mtr').read_text(encoding='ascii'), MATERIAL.format(f'pmg0_shinl{NUMBER}'))  # the bake is as it was
        handoff = json.loads((trial / publish.HANDOFF).read_text(encoding='utf-8'))
        troll = {resource['name']: resource for resource in handoff['outfits'][1]['resources']}
        self.assertEqual(len(troll), len(TOKENS) * 4 - 2)
        human = {resource['name'] for resource in handoff['outfits'][0]['resources']}  # the Human Fit body's bake is recorded as holding the shared maps
        self.assertTrue({left + '.tga', right + '.tga'} <= human and len(human) == len(TOKENS) * 4)
        self.assertEqual(publish.shared_name(['pfd0_bicepr6020r', 'pmh0_bicepl6020r'], 'abcdef'), 'bicepl6020r_abcd')
        self.assertEqual(publish.shared_name(['pmh0_forearml6020n', 'pfh0_forearml6020n'], 'abcdef'), 'forearml6020n_ab')
        # two maps of one part whose hashes begin alike: the later by hash takes the next digits of its own
        files = {name: Path(name) for name in ('pmh0_legl1n.tga', 'pmg0_legl1n.tga', 'pfh0_legl1n.tga', 'pfg0_legl1n.tga')}
        alike = publish.shared_maps([], files, lambda path: ('abcd1111' if path.name[1] == 'm' else 'abcd2222') + '0' * 56)[0]
        self.assertEqual((alike['pmh0_legl1n'], alike['pmg0_legl1n'], alike['pfh0_legl1n']), ('legl1n_abcd', 'legl1n_abcd', 'legl1n_2222'))
        self.assertNotIn(f'pmg0_shinl{NUMBER}n.tga', troll)
        self.assertEqual(troll[f'pmg0_shinl{NUMBER}.mtr']['sha256'], publish.sha(pack / f'pmg0_shinl{NUMBER}.mtr'))
        self.assertEqual(troll[f'pmg0_shinl{NUMBER}.mtr']['bytes'], (pack / f'pmg0_shinl{NUMBER}.mtr').stat().st_size)
        self.assertEqual(publish.shared_maps([], {'a.tga': bakes[0] / 'bake.json', 'b.plt': bakes[0] / 'bake.json'}), ({}, {}, {}))  # a map alone, and no tint texture

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
        self.assertEqual(outfit['records'], [{'name': self.root.resolve().name + '/trial-ledger.json', 'sha256': publish.sha(self.ledger), 'bytes': 15}])
        self.assertEqual(len(outfit['resources']), len(TOKENS) * 4)
        # nothing of it is in the repository
        self.assertFalse((self.repo / 'srn_parts').exists() or (self.repo / publish.REGISTRY).exists())
        self.assertEqual(sorted(path.name for path in (self.repo / 'srn_2da').iterdir()), ['skyboxes.2da'])
        self.assertEqual(json.loads((trial / 'publish-report.json').read_text(encoding='utf-8'))['failuresByGate'], report['failuresByGate'])
        # a bake given twice fails by name and the trial is still written, its files recorded once
        twice = self.publish(shared(('pmh0', 'pmh0')), root=self.root / 'twice', trial=True)
        self.assertTrue(twice['written'])
        self.assertEqual(twice['failuresByGate']['bake'], len(TOKENS) * 4)
        outfits = json.loads((self.root / 'twice' / publish.HANDOFF).read_text(encoding='utf-8'))['outfits']
        self.assertEqual([len(outfit['resources']) for outfit in outfits], [len(TOKENS) * 4, 0])

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
        staged = self.repo / 'srn_parts' / 'pmh0_handl6030.mdl'
        staged.write_bytes(bytes(8))
        drift = self.publish(shared(registry.BODIES[1:], outfit='hands'), registry=more, dry_run=True)
        self.assertIn(('published', staged.name), [(one['gate'], one['model']) for one in drift['failures']])
        staged.unlink()
        icon_file = self.repo / 'srn_parts' / f'ipm_chest{NUMBER}.plt'
        kept_bytes = icon_file.read_bytes()
        icon_file.write_bytes(b'edited')
        drift = self.publish(shared(outfit='hands'), registry=more, dry_run=True)
        self.assertEqual([(one['gate'], one['model']) for one in drift['failures']], [('published', icon_file.name)])
        icon_file.write_bytes(kept_bytes)
        handoff_file = self.repo / publish.HANDOFF
        kept_bytes = handoff_file.read_bytes()
        handoff_file.unlink()
        with self.assertRaisesRegex(ValueError, 'is published without parts-handoff.json'):
            self.publish(shared(outfit='hands'), registry=more, dry_run=True)
        handoff_file.write_text('[]', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'is no parts handoff'):
            self.publish(shared(outfit='hands'), registry=more, dry_run=True)
        handoff_file.write_bytes(kept_bytes)
        read = []
        report = self.publish(shared(outfit='hands'), registry=more, measure_neck=lambda *given: (measured.append(given[3]), sound(*given))[1],
                              textures=lambda path: (read.append(Path(path).stem), named(path))[1])
        self.assertEqual(measured, [])  # the chests published earlier are not measured again
        self.assertEqual(len(read), 40)  # nor their models read: only the new gloves, a pair a body
        self.assertTrue(report['passed'] and report['written'])
        self.assertEqual(report['newParts'], ['hand 6030'])
        handoff = json.loads((self.repo / publish.HANDOFF).read_text(encoding='utf-8'))
        self.assertEqual(len(handoff['outfits']), 40)
        self.assertEqual([one['name'] for one in handoff['iconFiles']], [f'ipf_chest{NUMBER}.plt', f'ipf_pelvis{NUMBER}.plt', f'ipm_chest{NUMBER}.plt', f'ipm_pelvis{NUMBER}.plt'])
        self.assertEqual(len(tables.parse((self.repo / 'srn_2da' / 'parts_hand.2da').read_text(encoding='cp1252'))[1]), 6031)
        self.assertEqual(len(tables.parse((self.repo / 'srn_2da' / 'parts_chest.2da').read_text(encoding='cp1252'))[1]), NUMBER + 1)

    def test_a_bake_at_another_number_a_failed_bake_and_missing_records_fail_by_name(self):
        folders = shared(registry.BODIES[1:]) + [bake(self.root / 'bakes' / 'pmh0', 'pmh0', number=333, passed=False)]
        report = self.publish(folders, records=[], briefs=[], dry_run=True)
        by_gate = report['failuresByGate']
        self.assertEqual((by_gate['bodies'], by_gate['bake'], by_gate['records']), (len(TOKENS), len(TOKENS) + 1, 40))
        reasons = {one['model']: one['reason'] for one in report['failures'] if one['gate'] in ('bake', 'records')}
        self.assertIn('the registry has no new part chest 333 on pmh0', reasons['pmh0_chest333'])
        tiers = self.root / 'tiers.json'
        tiers.write_text(json.dumps(document(CHEST, PELVIS, {**SHIN, 'tiers': {**SHIN['tiers'], 'ankle': 3}})), encoding='utf-8')
        uneven = self.publish(shared(), registry=tiers, dry_run=True)
        self.assertEqual(uneven['failuresByGate'], {'bake': 40})
        self.assertIn('it was baked at tier 2 and the registry gives shin 6020 ankle tier 3', [one['reason'] for one in uneven['failures']])
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

    def test_a_tint_texture_that_is_one_image_on_several_bodies_is_kept_once_and_listed_as_copies(self):
        bakes = [bake(self.root / 'bakes' / body, body) for body in registry.BODIES]
        human = (bakes[registry.BODIES.index('pmh0')] / 'resources' / f'pmh0_shinl{NUMBER}.plt').read_bytes()
        for body in ('pmd0', 'pmg0'):  # a refit leaves the Human's tint texture on the other bodies
            (bakes[registry.BODIES.index(body)] / 'resources' / f'{body}_shinl{NUMBER}.plt').write_bytes(human)
        report = self.publish(bakes)
        self.assertTrue(report['passed'] and report['written'])
        listed = {f'pmd0_shinl{NUMBER}.plt': f'pmh0_shinl{NUMBER}.plt', f'pmg0_shinl{NUMBER}.plt': f'pmh0_shinl{NUMBER}.plt'}  # the Human Fit body's is the one kept
        self.assertEqual(report['copies'], sorted(listed))
        pack = self.repo / 'srn_parts'
        self.assertEqual(len(list(pack.iterdir())), 20 * len(TOKENS) * 4 + 4 - 2)
        self.assertTrue((pack / f'pmh0_shinl{NUMBER}.plt').is_file() and (pack / f'pmg0_shinr{NUMBER}.plt').is_file())
        self.assertFalse((pack / f'pmg0_shinl{NUMBER}.plt').exists() or (pack / f'pmd0_shinl{NUMBER}.plt').exists())
        self.assertEqual(json.loads((self.repo / publish.COPIES).read_text(encoding='utf-8')), {'schemaVersion': 1, 'kind': 'srn-hak-copies', 'pack': 'srn_parts', 'copies': listed})
        self.assertEqual(publish.copies(self.repo), listed)
        entry = next(pack for pack in json.loads((self.repo / 'hakbuilder.json').read_text(encoding='utf-8'))['HakList'] if pack['Name'] == 'srn_parts')
        self.assertEqual(entry['Copies'], './docs/armorkit/parts-copies.json')
        # the handoff records the copy under its own name, with the image's hash
        handoff = json.loads((self.repo / publish.HANDOFF).read_text(encoding='utf-8'))
        troll = {resource['name']: resource for outfit in handoff['outfits'] if outfit['body'] == 'pmg0' for resource in outfit['resources']}
        self.assertEqual(troll[f'pmg0_shinl{NUMBER}.plt'], {'name': f'pmg0_shinl{NUMBER}.plt', 'sha256': publish.sha(pack / f'pmh0_shinl{NUMBER}.plt'), 'bytes': len(human)})
        # a later publication reads a copy from the file kept, keeps the list, and holds both to the handoff
        more = self.root / 'more.json'
        more.write_text(json.dumps(document(*PARTS, part(slot='hand', number=6030, set='siteguard', group='corpsec', genderedCut=False, tiers={'wrist': 2}))), encoding='utf-8')
        self.assertEqual(self.publish(shared(outfit='hands'), registry=more, dry_run=True)['failures'], [])
        trial = self.publish(shared(outfit='hands'), registry=more, root=self.root / 'trial', trial=True)
        self.assertTrue(trial['passed'] and publish.copies(self.root / 'trial') == listed and not (self.root / 'trial' / 'srn_parts' / f'pmg0_shinl{NUMBER}.plt').exists())
        kept = pack / f'pmh0_shinl{NUMBER}.plt'
        kept.write_bytes(b'edited')
        drift = self.publish(shared(outfit='hands'), registry=more, dry_run=True)
        self.assertEqual(sorted((one['gate'], one['model']) for one in drift['failures']), [('published', name) for name in sorted([kept.name, *listed])])
        kept.write_bytes(human)
        (pack / f'pmg0_shinl{NUMBER}.plt').write_bytes(human)  # a copy put back into the folder would be packed twice
        drift = self.publish(shared(outfit='hands'), registry=more, dry_run=True)
        self.assertEqual([(one['gate'], one['model']) for one in drift['failures']], [('published', f'pmg0_shinl{NUMBER}.plt')])
        self.assertIn('copies list names it as a copy', drift['failures'][0]['reason'])
        (pack / f'pmg0_shinl{NUMBER}.plt').unlink()
        (self.repo / publish.COPIES).write_text('{"kind": "other"}', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'is no copies list of srn_parts'):
            self.publish(shared(outfit='hands'), registry=more, dry_run=True)
        # a list the repository's build would refuse is refused here too: a name that is no resource file name, another type, a copy of a copy
        for wrong in ({'../x.plt': kept.name}, {'PMD0_A.plt': kept.name}, {'pmd0_a.tga': kept.name}, {'pmd0_a.plt': 'pmd0_b.plt', 'pmd0_b.plt': kept.name}):
            (self.repo / publish.COPIES).write_text(json.dumps({'schemaVersion': 1, 'kind': 'srn-hak-copies', 'pack': 'srn_parts', 'copies': wrong}), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'both are resource file names of one type'):
                publish.copies(self.repo)
        # icons are kept under their own names, and a pack without copies has no list
        self.assertEqual(publish.tint_copies({'pfh0_a1.plt': 'x', 'pfd0_a1.plt': 'x', 'pfd2_a1.plt': 'x', 'pfd0_b1.plt': 'y', 'pfd0_a1n.tga': 'x'}),
                         {'pfd0_a1.plt': 'pfh0_a1.plt', 'pfd2_a1.plt': 'pfh0_a1.plt'})
        self.assertEqual(publish.copies(self.root / 'nowhere'), {})

    def test_the_build_entry_is_added_once_after_the_armor_pack(self):
        text = (self.repo / 'hakbuilder.json').read_text(encoding='utf-8')
        once = publish.registered(text)
        self.assertEqual(publish.registered(once), once)
        self.assertIn({'Name': 'srn_parts', 'Path': './srn_parts/', 'CompileModels': False}, json.loads(once)['HakList'])
        copied = publish.registered(once, True)  # the entry names the copies list once the pack has one, and keeps it
        self.assertIn({'Name': 'srn_parts', 'Path': './srn_parts/', 'CompileModels': False, 'Copies': './docs/armorkit/parts-copies.json'}, json.loads(copied)['HakList'])
        self.assertEqual((publish.registered(copied), publish.registered(copied, True)), (copied, copied))
        with self.assertRaisesRegex(ValueError, 'indent-2 form'):
            publish.registered(json.dumps(json.loads(text)))

    def test_the_command_prints_forty_failures_saves_them_all_and_reports_a_failed_build(self):
        import argparse
        import contextlib
        import io
        from unittest import mock
        many = {'passed': False, 'written': True, 'root': str(self.root / 'nowhere'), 'failures': [publish.failure('bodies', f'm{index}', 'none') for index in range(50)]}
        saved = self.root / 'report.json'
        given = argparse.Namespace(registry='r', bake=['b'], stock='s', record=[], brief=[], trial=str(self.root / 'nowhere'), dry_run=False, body_pack=None,
                                   build=True, report=str(saved))
        printed = io.StringIO()
        with mock.patch.object(publish, 'publish', return_value=dict(many)), mock.patch.object(publish, 'build', side_effect=ValueError('no tool')), \
                contextlib.redirect_stdout(printed):
            self.assertEqual(publish.command(given), 1)
        shown = json.loads(printed.getvalue())
        self.assertEqual((len(shown['failures']), shown['failures'][-1], shown['buildError']), (41, '... and 10 more', 'no tool'))
        self.assertEqual(len(json.loads(saved.read_text(encoding='utf-8'))['failures']), 50)
        passed = {**many, 'passed': True, 'failures': []}
        with mock.patch.object(publish, 'publish', return_value=dict(passed)), mock.patch.object(publish, 'build', return_value={}), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(publish.command(given), 0)
        with mock.patch.object(publish, 'publish', return_value=dict(passed)), mock.patch.object(publish, 'build', side_effect=ValueError('no tool')), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(publish.command(given), 1)  # written, and the build failed

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
        (two / 'index.json').write_text('[]', encoding='utf-8')  # a JSON file that is no brief is passed over
        self.assertIsNone(publish.brief_of('unknown', {}, two))
        with self.assertRaisesRegex(ValueError, "A root is a trial's scratch folder"):
            self.publish(shared(('pmh0',)), root=self.root / 'scratch')


BRASSARD = part(slot='shoulder', number=1000, families=['accessory'], set=..., group=..., genderedCut=False, tiers={},
                badge={'positions': ['left', 'right']})


def badged(path):
    """A stand-in for `publish.model_textures`: a model with a badge names its own texture and the logo strip."""
    return [Path(path).stem, logo.STRIP]


def brassard(folder, body, strip=b'strip'):
    """A drawn brassard's output folder as `brassard.run` leaves it, with stand-in payloads: no materials, no
    material file of its own, and the logo's three files."""
    folder = Path(folder)
    resources = folder / 'resources'
    resources.mkdir(parents=True)
    models = {token: registry.model_name(body, token, 1000) for token in ('shol', 'shor')}
    for name in models.values():
        (resources / (name + '.mdl')).write_bytes(bytes(4) + name.encode())
        (resources / (name + '.plt')).write_bytes(b'band')
    for name in logo.FILES:
        (resources / name).write_bytes(strip if name.endswith('.tga') else b'text\n')
    record = {'model': 'brassard-test', 'body': body, 'tier': 1, 'number': 1000, 'models': models, 'logo': logo.record(),
              'gates': {'passed': True, 'failures': [], 'triangles': {'shol': 10, 'shor': 10}}, 'compiled': 2}
    (folder / 'bake.json').write_text(json.dumps(record), encoding='utf-8')
    return folder


class DrawnPieceTests(Workspace):
    """A drawn piece with a badge: no brief, no material file, and the logo's files once for the pack."""

    def setUp(self):
        super().setUp()
        self.registry.write_text(json.dumps(document(BRASSARD)), encoding='utf-8')
        with (self.repo / 'PROVENANCE.md').open('a', encoding='utf-8') as stream:
            stream.write('brassard-test, drawn by the kit.\n')
        self.bakes = [brassard(self.root / 'drawn' / body, body) for body in registry.BODIES]
        self.options = {'records': [('brassard-test', self.ledger)], 'briefs': [], 'textures': badged}

    def test_a_drawn_piece_brings_no_material_file_and_the_logos_files(self):
        found = publish.survey(self.bakes[0])
        self.assertEqual((found['wrong'], found['drawn']), ([], True))
        self.assertEqual(sorted(found['files']), sorted(['pmh0_shol1000.mdl', 'pmh0_shol1000.plt', 'pmh0_shor1000.mdl', 'pmh0_shor1000.plt', *logo.FILES]))
        record = json.loads((self.bakes[0] / 'bake.json').read_text(encoding='utf-8'))
        record['logo']['cells'] = {'ares': 2}
        (self.bakes[0] / 'bake.json').write_text(json.dumps(record), encoding='utf-8')
        (self.bakes[0] / 'resources' / logo.FILES[1]).unlink()
        self.assertEqual([reason for _, reason in publish.survey(self.bakes[0])['wrong']],
                         ["it was drawn for another logo strip than the kit's: draw it again", f'the bake holds no {logo.FILES[1]}'])

    def test_it_is_published_with_the_logo_once_and_the_handoff_names_it(self):
        report = self.publish(self.bakes, **self.options)
        self.assertEqual((report['failures'], report['written']), ([], True))
        pack = {path.name for path in (self.repo / 'srn_parts').iterdir()}
        self.assertTrue(set(logo.FILES) <= pack)
        self.assertFalse({name for name in pack if name.endswith('.mtr')} - {logo.FILES[0]})
        handoff = json.loads((self.repo / publish.HANDOFF).read_text(encoding='utf-8'))
        self.assertEqual(handoff['logo'], logo.record())
        self.assertEqual(handoff['outfits'][0]['brief'], None)
        self.assertEqual(handoff['outfits'][0]['bake']['triangles'], {'shol': 10, 'shor': 10})
        holders = [outfit['body'] for outfit in handoff['outfits'] if set(logo.FILES) & {one['name'] for one in outfit['resources']}]
        self.assertEqual(holders, ['pmh0'])  # recorded with the first bake that brings them
        self.assertEqual(sum(len(outfit['resources']) for outfit in handoff['outfits']), 20 * 4 + 3)
        # the next publication stands on it: the published band has no material file, and the logo's files are the pack's
        self.registry.write_text(json.dumps(document(BRASSARD, *PARTS)), encoding='utf-8')
        again = self.publish(shared(), textures=named)
        self.assertEqual(again['failures'], [])
        self.assertEqual(json.loads((self.repo / publish.HANDOFF).read_text(encoding='utf-8'))['logo'], logo.record())

    def test_another_strip_a_badge_without_it_and_a_missing_history_fail(self):
        other = brassard(self.root / 'other' / 'pfg2', 'pfg2', strip=b'another strip')
        report = self.publish(self.bakes[:-1] + [other], dry_run=True, **self.options)
        self.assertEqual([(one['gate'], one['model'], one['reason']) for one in report['failures']],
                         [('bake', logo.FILES[2], f'pfg2 brassard-test holds another {logo.FILES[2]} than the one the other bakes hold')])
        report = self.publish(self.bakes, dry_run=True, **{**self.options, 'textures': named})
        self.assertEqual(report['failuresByGate'], {'closure': 40})
        self.assertIn('shoulder 1000 has a badge and the model has no mesh on the logo strip srn_logos', report['failures'][0]['reason'])
        report = self.publish(self.bakes, dry_run=True, **{**self.options, 'records': []})
        self.assertEqual(report['failuresByGate'], {'records': 20})

    def test_a_part_without_a_badge_may_not_name_the_strip(self):
        report = self.publish(shared(), dry_run=True, registry=self.plain(), textures=badged)
        self.assertEqual(report['failuresByGate'], {'closure': 20 * len(TOKENS) * 3})  # the strip is not its own, and it has no tint or material file
        self.assertIn('it names the texture srn_logos, not its own', report['failures'][0]['reason'])

    def test_a_new_strip_replaces_the_published_one_and_keeps_every_cell(self):
        from unittest import mock
        with self.assertRaisesRegex(ValueError, 'has no published logo to replace'):
            publish.relogo(repo=self.repo)
        self.assertEqual(self.publish(self.bakes, **self.options)['failures'], [])
        pack, handoff = self.repo / 'srn_parts', self.repo / publish.HANDOFF
        held = handoff.read_bytes()

        def strip(blob=b'a longer strip'):
            def write(folder):
                for name in logo.FILES:
                    (Path(folder) / name).write_bytes(blob if name.endswith('.tga') else b'text\n')
            return write
        with self.assertRaisesRegex(ValueError, 'there is nothing to replace'):
            publish.relogo(repo=self.repo, write=strip(b'strip'))
        more = logo.CELLS[:12] + ('zeta',) + logo.CELLS[13:]
        with mock.patch.object(logo, 'CELLS', more):
            report = publish.relogo(repo=self.repo, write=strip(), dry_run=True)
            self.assertEqual((report['passed'], report['files'], report['cells'], report['written']), (True, [logo.FILES[2]], {'added': ['zeta'], 'kept': 11}, False))
            self.assertEqual(handoff.read_bytes(), held)
            report = publish.relogo(repo=self.repo, write=strip())
            self.assertTrue(report['written'])
            self.assertEqual((pack / logo.FILES[2]).read_bytes(), b'a longer strip')
            now = json.loads(handoff.read_text(encoding='utf-8'))
            self.assertEqual(now['logo']['cells']['zeta'], 12)
            recorded = {one['name']: one for outfit in now['outfits'] for one in outfit['resources']}
            self.assertEqual((recorded[logo.FILES[2]]['sha256'], recorded[logo.FILES[2]]['bytes']), (publish.sha(pack / logo.FILES[2]), 14))
            # what is published is again what its handoff records: the next publication passes
            self.registry.write_text(json.dumps(document(BRASSARD, *PARTS)), encoding='utf-8')
            self.assertEqual(self.publish(shared(), textures=named)['failures'], [])
        # a cell that moved or went, and a strip changed by hand, fail and write nothing
        held, moved = handoff.read_bytes(), (None, 'renraku', 'ares') + logo.CELLS[3:]
        with mock.patch.object(logo, 'CELLS', moved):
            report = publish.relogo(repo=self.repo, write=strip(b'moved'))
        self.assertEqual([(one['gate'], one['model']) for one in report['failures']], [('cells', 'ares'), ('cells', 'renraku'), ('cells', 'zeta')])
        self.assertIn('published as cell 1 and now cell 2: a cell once given keeps its name and number', report['failures'][0]['reason'])
        self.assertIn('published as cell 12 and now gone', report['failures'][2]['reason'])
        (pack / logo.FILES[0]).write_bytes(b'by hand\n')
        with mock.patch.object(logo, 'CELLS', more[:13] + ('eta',) + more[14:]):
            report = publish.relogo(repo=self.repo, write=strip(b'third'))
        self.assertEqual((report['failuresByGate'], report['written']), ({'published': 1}, False))
        self.assertEqual((handoff.read_bytes(), (pack / logo.FILES[2]).read_bytes()), (held, b'a longer strip'))

    def plain(self):
        path = self.root / 'plain.json'
        path.write_text(json.dumps(document(*PARTS)), encoding='utf-8')
        return path


if __name__ == '__main__':
    unittest.main()
