import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.tilekit import detail, family, placer
from tools.tilekit.test_detail import MODEL, PIECE, WOK

SPEC = {'tileset': 'x', 'families': [{'terrains': ['Slums*'], 'placer': 'propose', 'options': {'look': 'brick', 'plant': None}},
                                     {'terrains': ['Street'], 'match': 'all', 'placer': 'propose_street'}]}


class FamilyTest(unittest.TestCase):
    def test_the_family_of_a_tile(self):
        self.assertIs(family.family_of(SPEC, ['Street', 'slums2', 'Street', 'Street']), SPEC['families'][0])
        self.assertIs(family.family_of(SPEC, ['Street'] * 4), SPEC['families'][1])
        self.assertIsNone(family.family_of(SPEC, ['Street', 'Street', 'Street', 'Water']))

    def test_options_reach_the_placers(self):
        one = {'terrains': ['A'], 'placer': 'propose', 'options': {'grids': True, 'plant': 'roof'},
               'add': [{'placer': 'propose_corporate', 'options': {'plant': None}, 'pieces': ['camera']}]}
        spec = {'tileset': 'x', 'families': [one]}
        with mock.patch.object(placer, 'propose', return_value=[{'piece': 'vent'}]) as first, \
                mock.patch.object(placer, 'propose_corporate', return_value=[{'piece': 'camera'}, {'piece': 'canopy'}]) as second:
            self.assertEqual(family.proposed(spec, one, 'text', 't', ['A', 'A', 'B', 'B']), [{'piece': 'vent'}, {'piece': 'camera'}])
        self.assertEqual(first.call_args.kwargs['grids'], placer.GRIDS); self.assertIs(first.call_args.kwargs['plant'], placer.ROOF)
        self.assertIsNone(second.call_args.kwargs['plant'])
        self.assertEqual(first.call_args.kwargs['open'], placer.open_sides(['A', 'A', 'B', 'B'], lambda name: name == 'A'))

    def test_a_refused_piece_goes_and_a_box_takes_its_sparks(self):
        def place(them):
            for number, one in enumerate(them):
                if one['piece'] == 'junction_box':
                    raise detail.Refused(number, 'no')
            return {'pieces': len(them)}
        them = [{'piece': 'vent', 'at': 1}, {'piece': 'junction_box', 'at': 2}, {'piece': 'sparks', 'at': 3}]
        placements, told, gone = family.settled(place, them)
        self.assertEqual([one['piece'] for one in placements], ['vent']); self.assertEqual(told, {'pieces': 1}); self.assertEqual(len(gone), 1)

        def never(them):
            raise detail.Refused(0, 'no')
        with self.assertRaisesRegex(ValueError, '12 pieces refused'):
            family.settled(never, [{'piece': 'vent', 'at': 0}] * 30)

    def test_detail_names_the_placement_it_refuses(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / 'box.mdl').write_text(PIECE)
            with self.assertRaises(detail.Refused) as caught:
                detail.place(MODEL.format(z=8), 't_a01', [{'piece': 'box', 'at': [0, 0, 8], 'blocks': True}, {'piece': 'box', 'at': [40, 0, 4]}], folder, wok=WOK.format(z=8))
            (Path(folder) / 'box.mdl').write_bytes(bytes(4))
            with self.assertRaises(ValueError) as kits:  # the kit's own fault
                detail.place(MODEL.format(z=8), 't_a01', [{'piece': 'box', 'at': [0, 0, 8], 'blocks': True}], folder, wok=WOK.format(z=8))
            self.assertNotIsInstance(kits.exception, detail.Refused)
        self.assertEqual(caught.exception.number, 1); self.assertIn('#1 (box)', str(caught.exception))

    def test_a_spec_is_checked(self):
        for wrong in ({'placer': 'nothing'}, {'placer': 'propose', 'options': {'eye': 1}}, {'placer': 'propose', 'options': {'plant': 'jungle'}}):
            with self.assertRaises(ValueError):
                family._checked({'tileset': 'x', 'families': [{'terrains': ['A'], **wrong}]})

    def test_a_proposal_of_a_set(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = Path(folder); pack = repo / 'srn_t_x'; pack.mkdir(); (repo / 'srn_2da').mkdir(); kit = repo / 'kit'; kit.mkdir(); (kit / 'box.mdl').write_text(PIECE)
            rows = ''.join(f'[TILE{number}]\nModel={model}\nTopLeft=Slums1\nTopRight=Slums1\nBottomLeft=Slums1\nBottomRight=Slums1\n' for number, model in enumerate(('t_a01', 't_a02', 'ek_a')))
            (pack / 'x.set').write_text(rows)
            for model in ('t_a01', 't_a02', 'ek_a'):
                (pack / f'{model}.mdl').write_text(MODEL.format(z=8).replace('t_a01', model)); (pack / f'{model}.wok').write_text(WOK.format(z=8).replace('t_a01', model))
            (repo / 'held.json').write_text(json.dumps({'tiles': {'T_A02': []}})); (repo / 'spec.json').write_text(json.dumps({**SPEC, 'taken': ['held.json'], 'budget': {'faces': 0}}))
            placed = [{'piece': 'box', 'at': [0, 0, 8], 'blocks': True}, {'piece': 'box', 'at': [40, 0, 8]}]
            with mock.patch.object(placer, 'propose', return_value=placed):
                written, told = family.propose(repo, family.read(repo / 'spec.json'), kit)
                self.assertEqual(written, {'tileset': 'x', 'tiles': {'t_a01': placed[:1]}})
                self.assertEqual((told['tiles'], told['passed'], list(told['over']), list(told['dropped'])), (1, 1, ['t_a01'], ['t_a01']))
                (kit / 'box.mdl').unlink()
                with self.assertRaisesRegex(ValueError, 'No kit piece box'):
                    family.propose(repo, SPEC, kit)


if __name__ == '__main__':
    unittest.main()
