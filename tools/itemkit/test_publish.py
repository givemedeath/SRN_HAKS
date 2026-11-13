"""Weapon publication: package survey, collision and table rules, reviewer pairs, on small synthetic archives."""
import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.itemkit import publish as P


def gff(kind, fields):
    """A single-struct GFF V3.2 with BYTE (0) and DWORD (4) fields."""
    labels = b''.join(name.encode('ascii').ljust(16, b'\0') for name, _, _ in fields)
    entries = b''.join(struct.pack('<3I', t, i, v) for i, (_, t, v) in enumerate(fields))
    indices = struct.pack(f'<{len(fields)}I', *range(len(fields)))
    s, f = 56, 68; l = f + 12*len(fields); d = l + 16*len(fields)
    header = kind + b'V3.2' + struct.pack('<12I', s, 1, f, len(fields), l, len(fields), d, 0, d, len(indices), d + len(indices), 0)
    return header + struct.pack('<3I', 0xFFFFFFFF, 0, len(fields)) + entries + labels + indices


def erf(kind, entries, reverse=False):
    """An ERF V1.0 archive of {(resref, type): bytes}; `reverse` stores the resource table in the opposite key order."""
    count = len(entries); keys = 160; resources = keys + 24*count; data = resources + 8*count
    header = kind + b'V1.0' + struct.pack('<8I', 0, 0, count, 0, keys, resources, 0, 0) + struct.pack('<I', 0xFFFFFFFF) + b'\0'*116
    key, table, body = b'', [b''] * count, b''
    for i, ((resref, rtype), payload) in enumerate(entries.items()):
        resource = count - 1 - i if reverse else i
        key += resref.encode('ascii').ljust(16, b'\0') + struct.pack('<IHH', resource, rtype, 0)
        table[resource] = struct.pack('<II', data + len(body), len(payload)); body += payload
    return header + key + b''.join(table) + body


TABLE = (b'2DA V2.0\n\n     label        MaxRange   ItemClass\n'
         b'1    longsword    121        WSwLs\n22   dagger       100        WSwDg\n')


def make_run(root, blueprint='srabc', base=22, part=111, parts=None, tamper=False):
    run = root/'run-fit-v1'; native = run/'native/attempt-1/native'; native.mkdir(parents=True)
    models = {p: f'wswdg_{p}_{part:03}' for p in 'bmt'}
    hak = erf(b'HAK ', {**{(m, 2002): f'model {m}'.encode() for m in models.values()}, (f'i{models["b"]}', 3): b'icon', (f'{blueprint}_11', 3): b'diffuse'})
    (native/f'{blueprint}h.hak').write_bytes(hak)
    record = {'hak': {'path': f'X:/elsewhere/{blueprint}h.hak', 'sha256': hashlib.sha256(hak).hexdigest()}, 'baseItem': base,
              'identity': {'blueprint': blueprint, 'displayName': 'Test Knife'}, 'allocation': {'models': models}}
    (native/'native.json').write_text(json.dumps(record), encoding='utf-8')
    if tamper: (native/f'{blueprint}h.hak').write_bytes(hak + b'x')
    parts = parts or (part, part, part)
    uti = gff(b'UTI ', [('BaseItem', 4, base), *[(f'ModelPart{i}', 0, v) for i, v in zip((1, 2, 3), parts)]])
    modules = run/'fixture/attempt-2/fixture/userdir/modules'; modules.mkdir(parents=True)
    (modules/f'{blueprint}m.mod').write_bytes(erf(b'MOD ', {(blueprint, 2025): uti, ('other', 2025): b'not this one'}))
    return run


def make_repo(root, existing=()):
    (root/'srn_weapon').mkdir(); (root/'srn_2da').mkdir(); (root/'docs/items').mkdir(parents=True)
    for name in existing: (root/'srn_weapon'/name).write_bytes(b'published')
    (root/'srn_2da/baseitems.2da').write_bytes(TABLE)
    P.dump(root/P.PUBLICATION, {'items': [], 'resources': [], 'groupingPlan': {'families': [{'id': 'F1', 'baseItemId': 22}]}}, False)
    return root


def creature(tag, x, y):
    return {'Tag': {'value': tag}, 'TemplateResRef': {'value': tag}, 'FirstName': {'value': {'0': 'x'}},
            'XPosition': {'value': x}, 'YPosition': {'value': y}}


class ArchiveTests(unittest.TestCase):
    def test_payloads_follow_each_keys_resource_id(self):
        entries = {('model', 2002): b'mdl bytes', ('image', 3): b'tga bytes'}
        for reverse in (False, True):
            self.assertEqual(P.read_erf(erf(b'HAK ', entries, reverse=reverse)), entries)


class SurveyTests(unittest.TestCase):
    def test_survey_takes_the_verified_package_and_its_own_blueprint(self):
        with tempfile.TemporaryDirectory() as folder:
            package = P.survey('knife', make_run(Path(folder)))
            self.assertEqual((package.blueprint, package.base_item, package.appearance), ('srabc', 22, 111))
            self.assertEqual(sorted(package.files), ['iwswdg_b_111.tga', 'srabc.uti', 'srabc_11.tga',
                                                     'wswdg_b_111.mdl', 'wswdg_m_111.mdl', 'wswdg_t_111.mdl'])
            self.assertEqual(package.files['wswdg_m_111.mdl'], (b'model wswdg_m_111', 'srabch.hak'))

    def test_survey_refuses_a_changed_package_or_a_mismatched_blueprint(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(P.PublishError, 'missing or changed'): P.survey('knife', make_run(Path(folder), tamper=True))
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(P.PublishError, 'model parts'): P.survey('knife', make_run(Path(folder), parts=(111, 111, 101)))


class TableTests(unittest.TestCase):
    def test_only_rows_below_the_appearance_change_and_only_their_maxrange_token(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = make_repo(Path(folder)); package = P.survey('knife', make_run(Path(folder)))
            needs = P.maxrange_needs(repo, [package]); self.assertEqual(needs, {22: (100, 111)})
            after = P.extend_maxrange(TABLE, needs)
            self.assertEqual(after, TABLE.replace(b'dagger       100 ', b'dagger       111 '))
            self.assertEqual(len(after), len(TABLE))

    def test_an_appearance_below_minrange_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = make_repo(Path(folder))
            (repo/P.BASEITEMS).write_bytes(TABLE.replace(b'ItemClass\n', b'ItemClass   MinRange\n').replace(b'WSwDg\n', b'WSwDg       120\n'))
            with self.assertRaisesRegex(P.PublishError, 'below row 22 MinRange 120'): P.plan(repo, [('knife', make_run(Path(folder)))])

    def test_a_wider_number_takes_the_padding_after_it(self):
        self.assertEqual(P.extend_maxrange(TABLE, {22: (100, 1111)}), TABLE.replace(b'dagger       100 ', b'dagger       1111'))
        tight = TABLE.replace(b'100        WSwDg', b'100 WSwDg')            # one separator space: nothing to take
        with self.assertRaisesRegex(P.PublishError, 'no padding'): P.extend_maxrange(tight, {22: (100, 1111)})


class PlanTests(unittest.TestCase):
    def test_a_name_already_in_srn_weapon_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = make_repo(Path(folder), existing=['srabc_11.tga'])
            with self.assertRaisesRegex(P.PublishError, 'srabc_11.tga'): P.plan(repo, [('knife', make_run(Path(folder)))])

    def test_dry_run_reports_the_plan_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            run = make_run(Path(folder)); (Path(folder)/'repo').mkdir(); repo = make_repo(Path(folder)/'repo')
            before = {p: p.read_bytes() for p in Path(folder).rglob('*') if p.is_file()}
            result = P.publish(repo, [('knife', run)], ['looks good'], 'Seen in game.', None, dry_run=True)
            self.assertEqual(result['maxRange'], {'22': {'before': 100, 'after': 111}})
            self.assertEqual({p: p.read_bytes() for p in Path(folder).rglob('*') if p.is_file()}, before)
            with self.assertRaisesRegex(P.PublishError, "user's words"): P.publish(repo, [('knife', run)], [], 'Seen.', None, dry_run=True)
            with self.assertRaisesRegex(P.PublishError, "user's words"): P.publish(repo, [('knife', run)], ['  '], 'Seen.', None, dry_run=True)
            with self.assertRaisesRegex(P.PublishError, 'not a YYYY-MM-DD'):
                P.publish(repo, [('knife', run)], ['ok'], 'Seen.', None, today='13/11/2026', dry_run=True)

    def test_a_failed_publication_puts_the_tree_back(self):
        with tempfile.TemporaryDirectory() as folder:
            run = make_run(Path(folder)); (Path(folder)/'repo').mkdir(); repo = make_repo(Path(folder)/'repo')
            (repo/P.MODULE).mkdir(parents=True); (repo/P.MODULE/'c.nss').write_bytes(b'kept')
            before = {p: p.read_bytes() for p in repo.rglob('*') if p.is_file()}

            def fail(repo, planned, tools, work):             # after the copy, table and record writes
                (repo/P.MODULE/'sw2_m0.utc').write_bytes(b'new'); (repo/P.MODULE/'c.nss').write_bytes(b'changed')
                raise RuntimeError('compile failed')
            with mock.patch.object(P, 'Tools', lambda repo, nwn: None), mock.patch.object(P, 'update_publication', lambda *a: None), \
                 mock.patch.object(P, 'reviewer_plan', lambda repo, packages: ([], [])), mock.patch.object(P, 'add_reviewers', fail):
                with self.assertRaisesRegex(RuntimeError, 'compile failed'): P.publish(repo, [('knife', run)], ['ok'], 'Seen.', 'nwn')
            self.assertEqual({p: p.read_bytes() for p in repo.rglob('*') if p.is_file()}, before)

    def test_no_room_for_reviewers_is_refused_before_any_write(self):
        with tempfile.TemporaryDirectory() as folder:
            run = make_run(Path(folder)); (Path(folder)/'repo').mkdir(); repo = make_repo(Path(folder)/'repo')
            (repo/P.MODULE).mkdir(parents=True); (repo/P.MODULE/'sr_it_floor.git').write_bytes(b'git'); (repo/P.MODULE/'sr_it_floor.are').write_bytes(b'are')
            area = {b'git': {'Creature List': [{'Tag': f'sw1_{s}0', 'XPosition': 25.0, 'YPosition': P.ROW_Y[s]} for s in 'mf']},
                    b'are': {'Width': 3}}                                   # a 30 m area already full at x 25
            before = {p: p.read_bytes() for p in repo.rglob('*') if p.is_file()}
            real = P.crm.parse_gff
            with mock.patch.object(P.crm, 'parse_gff', lambda data: area.get(data) or real(data)), mock.patch.object(P, 'Tools', lambda repo, nwn: None):
                with self.assertRaisesRegex(P.PublishError, 'No room'): P.publish(repo, [('knife', run)], ['ok'], 'Seen.', 'nwn', dry_run=True)
                with self.assertRaisesRegex(P.PublishError, 'No room'): P.publish(repo, [('knife', run)], ['ok'], 'Seen.', 'nwn')
            self.assertEqual({p: p.read_bytes() for p in repo.rglob('*') if p.is_file()}, before)

    def test_ranged_weapons_are_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = make_repo(Path(folder))
            (repo/P.BASEITEMS).write_bytes(TABLE.replace(b'ItemClass\n', b'ItemClass   RangedWeapon\n').replace(b'WSwDg\n', b'WSwDg       20\n'))
            with self.assertRaisesRegex(P.PublishError, 'Ranged weapons'): P.plan(repo, [('knife', make_run(Path(folder)))])

    def test_items_outside_the_right_hand_or_three_parts_are_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = make_repo(Path(folder))
            (repo/P.BASEITEMS).write_bytes(TABLE.replace(b'ItemClass\n', b'ItemClass   EquipableSlots\n').replace(b'WSwDg\n', b'WSwDg       0x00020\n'))
            with self.assertRaisesRegex(P.PublishError, 'right hand'): P.plan(repo, [('knife', make_run(Path(folder)))])
        with tempfile.TemporaryDirectory() as folder:
            run = make_run(Path(folder)); native = next(run.glob('native/attempt-*/native/native.json'))
            record = json.loads(native.read_text(encoding='utf-8')); record['allocation']['models'] = {'whole': 'ashlw_014'}
            native.write_text(json.dumps(record), encoding='utf-8')
            with self.assertRaisesRegex(P.PublishError, r"three-part \(b/m/t\) weapons; the package has \['whole'\]"): P.survey('shield', run)


class ReviewerTests(unittest.TestCase):
    def setUp(self):
        self.creatures = [creature(f'sw1_{s}{i}', 5.0 + 3.5*i, P.ROW_Y[s]) for s in 'mf' for i in range(2)]

    def test_selector_table_follows_the_groups(self):
        groups = P.groups_of(['sw1_m0', 'sw1_f0', 'sw1_m1', 'sw1_f1', 'sw2_m0', 'sw2_f0', 'sw2_target'])
        self.assertEqual(groups, [('sw1_', 2), ('sw2_', 1)])
        text = P.pairs_include(groups)
        self.assertIn('int SwPairCount(){return 3;}', text)
        self.assertIn('if(prefix=="sw2_")return 2;', text)
        self.assertIn('if(pair<3)return "sw2_";', text)
        with self.assertRaisesRegex(P.PublishError, 'complete pairs'): P.groups_of(['sw1_m0'])

    def test_new_pairs_fill_groups_of_five_along_the_southern_row(self):
        packages = [P.Package(f'i{n}', Path('.'), f'Item {n}', f'bp{n}', 1, 111, Path('h'), Path('m')) for n in range(7)]
        groups, pairs = P.plan_pairs(self.creatures, packages, 80.0)
        self.assertEqual(groups, [('sw1_', 2)])
        self.assertEqual([(p['prefix'], p['index']) for p in pairs], [('sw2_', i) for i in range(5)] + [('sw3_', 0), ('sw3_', 1)])
        self.assertEqual([p['x'] for p in pairs[:2]], [12.0, 15.5])
        with self.assertRaisesRegex(P.PublishError, 'No room'): P.plan_pairs(self.creatures, packages, 30.0)
        nine = [creature(f'sw{n}_{s}0', 1.0 + n, P.ROW_Y[s]) for n in range(1, 10) for s in 'mf']
        with self.assertRaisesRegex(P.PublishError, 'sw1_ to sw9_'): P.plan_pairs(nine, packages[:1], 80.0)

    def test_reviewer_copy_changes_only_identity_and_position(self):
        copy = P.reviewer(self.creatures[0], 'sw2_f0', 'Test Knife', 'f', 12.0)
        self.assertEqual((copy['Tag']['value'], copy['TemplateResRef']['value'], copy['FirstName']['value'], copy['YPosition']['value']),
                         ('sw2_f0', 'sw2_f0', {'0': 'Test Knife / female'}, 9.0))
        self.assertEqual(self.creatures[0]['Tag']['value'], 'sw1_m0')

    def test_enter_script_gives_equips_and_counts(self):
        text = ('void main(){\nCreateItemOnObject("old",pc);\nCreateItemOnObject("sr_cl36_1",pc);SetLocalInt(pc,"SW2_ITEMS",1);}\n'
                'Equip("sw1_m0","old",INVENTORY_SLOT_RIGHTHAND,0);\nSendMessageToPC(pc,"Seventeen weapon/finish NPC pairs and more");\n}')
        package = P.Package('i', Path('.'), 'Item', 'srnew', 1, 111, Path('h'), Path('m'))
        out = P.enter_script(text, [{'package': package, 'prefix': 'sw2_', 'index': 0, 'x': 1.0}], 21).split('\n')
        self.assertEqual(out[2], 'CreateItemOnObject("srnew",pc);')
        self.assertEqual(out[5:7], ['Equip("sw2_m0","srnew",INVENTORY_SLOT_RIGHTHAND,0);', 'Equip("sw2_f0","srnew",INVENTORY_SLOT_RIGHTHAND,0);'])
        self.assertEqual(out[7], 'SendMessageToPC(pc,"Twenty-one weapon/finish NPC pairs and more");')
        crlf = P.enter_script(text.replace('\n', '\r\n'), [{'package': package, 'prefix': 'sw2_', 'index': 0, 'x': 1.0}], 21)
        self.assertEqual(crlf, '\n'.join(out).replace('\n', '\r\n'))   # the stored scripts are CRLF; no bare LF is added


if __name__ == '__main__':
    unittest.main()
