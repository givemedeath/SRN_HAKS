import json
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

    def test_sling_is_flagged_and_loads_table_pack(self):
        sling = [i for i in self.manifest['items'] if i['slingRelevant']]
        self.assertEqual([i['id'] for i in sling], ['colt-l36-pistol'])
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
