"""Exercise race-aware fixture controls, target row preservation, and armor templates."""
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

import stock_dwarf_control as controls
import build_derived_dwarf_fixture as dwarf
import build_derived_elf_fixture as elf
import build_derived_orc_fixture as orc
import build_derived_troll_fixture as troll
from preflight_derived_dwarf_client import verify_stock_controls, run_preflight

TABLE = ('2DA V2.0\n\nLABEL STRING_REF RACE HEIGHT WEAPONSCALE\n'
         '0 Dwarf 1 D 1.5 1\n1 Elf 2 E 1.75 1\n2 Gnome 3 G 1.5 1\n'
         '5 Orc 4 O 2.25 1.3\n6 Human 5 H 2 1\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class StockControlTests(unittest.TestCase):
    def test_each_race_uses_its_stock_family_and_troll_uses_human_donor(self):
        for race, expected_prefix, expected_slug, row, race_id in [
            ('dwarf', 'pmd0', 'stock_dwarf_male_fit', 0, 0),
            ('elf', 'pme0', 'stock_elf_male_fit', 1, 1),
            ('orc', 'pmo0', 'stock_orc_male_fit', 5, 5),
            ('troll', 'pmh0', 'stock_human_male_fit', 6, 6)]:
            with self.subTest(race=race), tempfile.TemporaryDirectory() as folder:
                stage = Path(folder)
                (stage / 'fixture-resources').mkdir()
                target_table = TABLE.replace('1 Elf 2 E 1.75 1', '1 Elf 2 E 2.0996799 1.085714')
                appearance = stage / 'fixture-resources/appearance.2da'
                appearance.write_text(target_table)
                manifest = stage / 'manifest.json'
                manifest.write_text(json.dumps({'combinations': [{'slug': 'target', 'appearance': row}]}))
                requests = []
                def extract(name, userdir, game_root):
                    requests.append(name)
                    if name == 'appearance.2da':
                        return TABLE.encode()
                    if name.endswith('.plt'):
                        return b'palette'
                    stem = Path(name).stem
                    return f'newmodel {stem}\nsetsupermodel {stem} {expected_prefix}\nbeginmodelgeom {stem}\nnode dummy {stem}\n parent null\n bitmap {stem}\nendnode\nendmodelgeom {stem}\n'.encode()
                def compile_models(command, **kwargs):
                    self.assertIn('native_compile.py', command[1])
                    converted = Path(command[command.index('--converted') + 1])
                    self.assertEqual(len(list((converted / 'ascii').glob('*.mdl'))), len(controls.PARTS) + 1)
                    for model in (converted / 'ascii').glob('*.mdl'):
                        (converted / 'resources' / model.name).write_bytes(b'\0\0\0\0' + model.read_bytes())
                    (converted / 'native-compile.json').write_text('{"complete":true}')
                with patch.object(controls, 'extract_stock_resource', side_effect=extract), patch.object(controls.subprocess, 'run', side_effect=compile_models):
                    controls.stage_stock_control(stage, stage, stage / 'client', race)
                    stale = stage / expected_slug / 'converted/resources/stale.plt'
                    stale.write_text('obsolete')
                    controls.stage_stock_control(stage, stage, stage / 'client', race)
                    self.assertFalse(stale.exists())
                entries = json.loads(manifest.read_text())['combinations']
                self.assertEqual(len(entries), 2)
                record = entries[1]
                self.assertEqual(record['slug'], expected_slug)
                self.assertEqual(record['raceId'], race_id)
                self.assertEqual(record['sourcePrefix'], expected_prefix)
                self.assertEqual(record['sourceAppearance'], row)
                conversion = stage / expected_slug / 'converted/conversion.json'
                data = json.loads(conversion.read_text())
                self.assertEqual(data['controlTargetRace'], race)
                self.assertEqual(data['sourcePrefix'], expected_prefix)
                root_alias = stage / expected_slug / 'converted/ascii/pmz0.mdl'
                self.assertIn('newmodel pmz0', root_alias.read_text())
                self.assertNotIn(expected_prefix, root_alias.read_text())
                model_requests = [name for name in requests if name.endswith('.mdl')]
                self.assertTrue(all(name.startswith(expected_prefix) for name in model_requests))
                self.assertEqual(len(model_requests), 2 * (len(controls.PARTS) + 1))
                # Target sizing survives control creation and reruns; the private row
                # is copied from the unmodified stock family, never the scaled row.
                self.assertIn('1 Elf 2 E 2.0996799 1.085714', appearance.read_text())
                private = next(line.split() for line in appearance.read_text().splitlines() if line.startswith(str(record['appearance']) + ' '))
                stock_row = next(line.split() for line in TABLE.splitlines() if line.startswith(str(row) + ' '))
                self.assertEqual(private[4:], stock_row[4:])
                self.assertEqual(record['appearance'], 7)
                receipt_control = {'slug': expected_slug, 'modelPrefix': 'pmz0', 'conversionSha256': sha(conversion),
                    **{key: data[key] for key in ('sourceRace', 'sourcePrefix', 'sourceAppearance', 'controlTargetRace')}}
                packed = [path.name for path in (stage / expected_slug / 'converted/resources').iterdir()]
                verify_stock_controls({'fixtureControls': [receipt_control]}, packed, stage, race)
                # Run the actual archive-based preflight, not only its control helper.
                userdir = stage / 'userdir'
                for name in ['hak', 'modules', 'override']:
                    (userdir / name).mkdir(parents=True)
                candidate_prefix = {'dwarf': 'pmd0', 'elf': 'pme0', 'orc': 'pmo0', 'troll': 'pmg0'}[race]
                candidate_parts = ['bicepl', 'bicepr', 'chest', 'footl', 'footr', 'forel', 'forer', 'handl', 'handr', 'head', 'neck', 'legl', 'legr', 'pelvis', 'shinl', 'shinr']
                entries = [name for name in packed if name.endswith(('.mdl', '.plt'))] + ['appearance.2da']
                entries += [f'{candidate_prefix}_{part}001.{ext}' for part in candidate_parts for ext in ('mdl', 'plt', 'mtr')]
                type_ids = {'mdl': 2002, 'plt': 6, 'mtr': 2072, '2da': 2017}
                header = bytearray(160)
                header[:4] = b'HAK '
                struct.pack_into('<I', header, 16, len(entries))
                struct.pack_into('<II', header, 24, 160, 160 + 24 * len(entries))
                keys = b''.join(struct.pack('<16sIH2x', Path(name).stem.encode(), i, type_ids[Path(name).suffix[1:]]) for i, name in enumerate(entries))
                hak = userdir / 'hak/srn_pheno_test.hak'
                hak.write_bytes(header + keys)
                module = userdir / 'modules/srn_pheno_test.mod'
                module.write_bytes(b'module')
                client = stage / 'client'
                client.write_bytes(b'client')
                candidate = stage / f'{race}_male_fit/converted'
                candidate.mkdir(parents=True)
                (candidate / 'native-compile.json').write_text(json.dumps({'clientSha256': sha(client)}))
                (stage / 'test-module').mkdir()
                (stage / 'test-module/receipt.json').write_text(json.dumps({'specimens': [f'{race}_male_fit', expected_slug], 'fixtureControls': [receipt_control], 'hakSha256': sha(hak), 'moduleSha256': sha(module)}))
                result = run_preflight(stage, client, race=race, prefix=candidate_prefix)
                self.assertTrue(result['pass'])
                self.assertEqual(result['specimens'][1], expected_slug)
                self.assertEqual(result['fixtureControls'][0]['sourcePrefix'], expected_prefix)
                with self.assertRaisesRegex(ValueError, 'race/source mismatch'):
                    verify_stock_controls({'fixtureControls': [receipt_control]}, packed, stage, 'orc' if race != 'orc' else 'elf')
                conversion.write_text('{}')
                with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                    verify_stock_controls({'fixtureControls': [receipt_control]}, packed, stage, race)

    def test_historical_dwarf_control_cannot_validate_elf(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, 'Dwarf control cannot validate another race'):
                verify_stock_controls({'specimens': ['stock_dwarf_male_fit']}, [], Path(folder), 'elf')

    def test_missing_stock_row_rejected_without_changing_target(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'appearance.2da'
            path.write_text(TABLE)
            with self.assertRaisesRegex(ValueError, 'stock source appearance row'):
                controls.stage_control_appearance(path, TABLE.replace('1 Elf', '3 Elf'), controls.CONTROL_SOURCES['elf'])
            self.assertEqual(path.read_text(), TABLE)


class ArmorTemplateTests(unittest.TestCase):
    def test_clean_baselines_for_every_race_stage_the_durable_armor_template(self):
        for builder in [dwarf, elf, orc, troll]:
            with self.subTest(builder=builder.__name__), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                durable = root / 'tools/phenotypes/references/fixtures/full_armor_template.json'
                durable.parent.mkdir(parents=True)
                durable.write_text('{"ArmorPart_Torso":{"value":16}}')
                stage = root / 'stage'
                def gff(command, **kwargs):
                    Path(command[command.index('-o') + 1]).write_text('{}')
                with patch.object(dwarf, 'REPO', root), patch.object(builder, 'resolve_game_root', return_value=root), patch.object(builder, 'run_tool', return_value=b'fixture'), patch.object(builder, 'resolve_tool', return_value={'path': 'gff'}), patch.object(builder.subprocess, 'run', side_effect=gff):
                    builder.stage_baseline(stage, root / 'compiler', game_root=root)
                staged = stage / 'baseline/full-armor-template.json'
                self.assertEqual(staged.read_bytes(), durable.read_bytes())

    def test_game_fallback_builds_template_when_durable_copy_is_absent(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            baseline = root / 'baseline'
            baseline.mkdir()
            def gff(command, **kwargs):
                Path(command[command.index('-o') + 1]).write_text('{"armor":"game"}')
            with patch.object(dwarf, 'REPO', root), patch.object(dwarf, 'run_tool', return_value=b'uti'), patch.object(dwarf, 'resolve_tool', return_value={'path': 'gff'}), patch.object(dwarf.subprocess, 'run', side_effect=gff):
                dwarf.stage_armor_template(baseline, root, root / 'compiler', root)
            self.assertEqual(json.loads((baseline / 'full-armor-template.json').read_text()), {'armor': 'game'})


if __name__ == '__main__':
    unittest.main()
