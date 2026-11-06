import json
import re
import struct
import unittest

import combat_release_manifest as crm


def gff(fields):
    """Build a minimal single-struct GFF V3.2 with DWORD/BYTE/ResRef fields."""
    labels, field_data, entries = [], b'', []
    for i, (label, ftype, value) in enumerate(fields):
        labels.append(label.encode('ascii').ljust(16, b'\0'))
        if ftype == 11:
            entries.append(struct.pack('<3I', ftype, i, len(field_data)))
            field_data += bytes([len(value)]) + value.encode('ascii')
        else:
            entries.append(struct.pack('<3I', ftype, i, value))
    indices = struct.pack(f'<{len(fields)}I', *range(len(fields)))
    struct_entry = struct.pack('<3I', 0xFFFFFFFF, 0, len(fields))
    header_size = 56
    s_off = header_size
    f_off = s_off + 12
    l_off = f_off + 12 * len(fields)
    d_off = l_off + 16 * len(fields)
    fi_off = d_off + len(field_data)
    li_off = fi_off + len(indices)
    header = b'UTI V3.2' + struct.pack('<12I', s_off, 1, f_off, len(fields), l_off, len(fields), d_off,
                                       len(field_data), fi_off, len(indices), li_off, 0)
    return header + struct_entry + b''.join(entries) + b''.join(labels) + field_data + indices


class ParserTests(unittest.TestCase):
    def test_whole_shield_resource_names_use_single_model_address(self):
        self.assertEqual(crm.expected_resources({'modelType':'0','itemClass':'AShLw','modelParts':{'ModelPart1':14}}),
                         ['ashlw_014.mdl','iashlw_014.tga'])
    def test_gff_reads_scalar_and_resref_fields(self):
        data = gff([('BaseItem', 4, 61), ('ModelPart1', 0, 51), ('TemplateResRef', 11, 'sr_cl36_1')])
        self.assertEqual(crm.parse_gff(data), {'BaseItem': 61, 'ModelPart1': 51, 'TemplateResRef': 'sr_cl36_1'})

    def test_2da_parses_quoted_values_and_short_rows(self):
        cols, rows = crm.parse_2da('2DA V2.0\n\n label ModelType Name\n0 "a b" 2 106\n1 sling\n')
        self.assertEqual(cols, ['label', 'ModelType', 'Name'])
        self.assertEqual(rows[0], {'label': 'a b', 'ModelType': '2', 'Name': '106'})
        self.assertEqual(rows[1]['Name'], '****')

    def test_model_strings_extracts_nul_terminated_names(self):
        self.assertEqual(crm.model_strings(b'\x01sr_cl36_051\x00ab\x00Wbwsl_B_051\x00'),
                         {'sr_cl36_051', 'wbwsl_b_051'})

    def test_strref_classification(self):
        self.assertEqual(crm.strref_status('****', set())['source'], 'none')
        self.assertEqual(crm.strref_status('1555', set())['source'], 'base-game dialog.tlk')
        custom = crm.strref_status(str(crm.TLK_CUSTOM_BASE + 5), {5})
        self.assertEqual((custom['source'], custom['entry'], custom['resolved']), ('srn.tlk', 5, True))

    def test_expected_resources_for_multipart_blueprint(self):
        bp = {'modelType': '2', 'itemClass': 'WBwSl',
              'modelParts': {'ModelPart1': 51, 'ModelPart2': 11, 'ModelPart3': 11}}
        self.assertEqual(crm.expected_resources(bp)[:2], ['wbwsl_b_051.mdl', 'iwbwsl_b_051.tga'])
        self.assertEqual(len(crm.expected_resources(bp)), 6)


class RepositoryManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = crm.build(check_git=False)

    def test_every_weapon_resource_matches_publication(self):
        self.assertTrue(all(r['publicationSha256Match'] for r in self.manifest['resources']))
        self.assertEqual(self.manifest['tables'][0]['matchesPublicationOverride'], True)

    def test_item_closures_are_complete_and_owned(self):
        for item in self.manifest['items']:
            self.assertEqual(item['closureMissing'], [], item['id'])
            self.assertTrue(item['closureMatchesPublicationOwnership'], item['id'])

    def test_approved_controls_use_the_selected_family_groups(self):
        expected={'cougar-fineblade-knife':('F1',22),'cougar-fineblade-longblade':('F1',22),
                  'cougar-fineblade-longsword':('F2',1),'colt-l36-pistol':('F7',61)}
        for item in self.manifest['items']:
            if item['id'] in expected:
                family,base=expected[item['id']]
                self.assertEqual(item['family'],family)
                self.assertTrue(all(bp['baseItem']==base for bp in item['blueprints']))

    def test_motion_overlay_and_hooks_remain_fixture_only(self):
        names={p.name for p in (crm.ROOT/'srn_weapon').iterdir()}
        self.assertTrue({'pmh0.mdl','pfh0.mdl','srf7_pmh0.mdl','srf7_pfh0.mdl','sr_f7_inc.nss','sr_f7_eq.ncs','sr_f7_un.ncs'}.isdisjoint(names))
        fixture=crm.ROOT/'test-modules/weapon-waves'
        self.assertEqual({p.name for p in (fixture/'haks').iterdir()},{'sw_reviewenv','sw_f7motion'})
        for item in self.manifest['items']:
            for bp in item['blueprints']:self.assertFalse((fixture/'module'/(bp['resRef']+'.uti')).exists())
        hooks=crm.parse_gff((fixture/'module/module.ifo').read_bytes())
        names={h['Mod_Hak'] for h in hooks['Mod_HakList']}
        self.assertEqual(names,{'sw_reviewenv','sw_f7motion','srn_weapon','srn_2da','srn_body','srn_body_tex'})

    def test_every_released_weapon_finish_has_both_npc_reviewers(self):
        module=crm.ROOT/'test-modules/weapon-waves/module'
        placed=crm.parse_gff((module/'sr_it_floor.git').read_bytes())['Creature List']
        actors={actor['Tag']:actor for actor in placed}
        self.assertEqual(len(actors),34)
        self.assertEqual(len(placed),len(actors))
        bindings=re.findall(r'Equip\("(sw[1234]_[mf][0-4])","([^"]+)"',
                            (module/'sw2_enter.nss').read_text())
        self.assertEqual(len(bindings),len(actors))
        self.assertEqual({tag for tag,_ in bindings},set(actors))
        expected={bp['resRef'] for item in self.manifest['items'] for bp in item['blueprints']}
        # The launcher is a gameplay entry sharing its AK-98 parent's model.
        expected.remove('sra84e4660gl')
        by_item={}
        for tag,resref in bindings:
            by_item.setdefault(resref,[]).append(actors[tag]['Gender'])
            self.assertEqual(actors[tag]['ScriptDialogue'],'sw_review')
            if tag.startswith(('sw3_','sw4_')):
                self.assertEqual(crm.parse_gff((module/(tag+'.utc')).read_bytes()),actors[tag])
                reference=crm.parse_gff((module/('sw2_'+tag[4]+'0.utc')).read_bytes())
                for field in ('Appearance_Type','Phenotype','Appearance_Head','BodyPart_Torso'):
                    self.assertEqual(actors[tag][field],reference[field])
        self.assertEqual(set(by_item),expected)
        self.assertTrue(all(sorted(genders)==[0,1] for genders in by_item.values()))

    def test_longblade_alias_changes_only_model_identity(self):
        publication=json.loads((crm.ROOT/crm.PUBLICATION).read_text(encoding='utf-8'))
        item=next(i for i in publication['items'] if i['id']=='cougar-fineblade-longblade')
        for alias in item['migration']['modelAliases']:
            a,b=(crm.ROOT/alias[k]['path'] for k in ('source','release'))
            self.assertEqual(b.read_bytes().replace(b.stem.encode(),a.stem.encode()),a.read_bytes())

    def test_sling_is_flagged_and_loads_table_pack(self):
        sling = [i for i in self.manifest['items'] if i['slingRelevant']]
        self.assertEqual({i['id'] for i in sling}, {'colt-l36-pistol','ingram-smartgun-x','sr4-ares-predator-iv-3ab64906ed'})
        self.assertIn('srn_2da', sling[0]['packs'])
        roles = {r['row']: r['role'] for r in self.manifest['tables'][0]['rows']}
        self.assertIn('sling ammunition', roles[27])

    def test_missing_published_texture_blocks_closure(self):
        original = crm.list_weapon_files
        crm.list_weapon_files = lambda: [p for p in original() if p.name.lower() != 'sr_cfk_07.tga']
        try:
            manifest = crm.build(check_git=False)
        finally:
            crm.list_weapon_files = original
        knife = next(i for i in manifest['items'] if i['id'] == 'cougar-fineblade-knife')
        self.assertIn('sr_cfk_07.tga', knife['closureMissing'])
        self.assertIn('closure-missing-cougar-fineblade-knife', [g['id'] for g in manifest['gaps']])

    def test_tracked_manifest_is_current_apart_from_git_comparison(self):
        tracked = json.loads((crm.ROOT / crm.JSON_OUT).read_text(encoding='utf-8'))
        self.manifest['pinnedComparison'] = tracked['pinnedComparison']
        self.assertEqual(tracked, json.loads(json.dumps(self.manifest)))


if __name__ == '__main__':
    unittest.main()
