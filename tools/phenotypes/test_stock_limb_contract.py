"""Explicit family/donor and actual package namespace regression guards."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

import stock_limb_contract as contract
from audit_thigh_package import validate_inventory, validate_unit_provenance


class StockLimbContractTests(unittest.TestCase):
    def test_arm_families_require_adjoining_preserved_pairs_and_exact_mirror(self):
        lower=contract.parse_preserved_parts('chest,pelvis,legl,legr,shinl,shinr,footl,footr')
        contract.validate_new_parts(['bicepl','bicepr'],lower)
        with self.assertRaises(RuntimeError):contract.validate_new_parts(['forel'],lower)
        upper=contract.parse_preserved_parts('chest,pelvis,bicepl,bicepr')
        contract.validate_new_parts(['forel','forer'],upper)
        with self.assertRaises(RuntimeError):contract.validate_new_parts(['handl'],upper)
        fore=contract.parse_preserved_parts('chest,pelvis,bicepl,bicepr,forel,forer')
        contract.validate_new_parts(['handl','handr'],fore)
        for left,right in [('bicepl','bicepr'),('forel','forer'),('handl','handr')]:
            donor={'part':left,'joint':contract.ATTACHMENTS[left]}
            contract.validate_mirror_association(donor,contract.ATTACHMENTS[left],contract.ATTACHMENTS[right])
            with self.assertRaises(RuntimeError):contract.validate_new_parts([right],fore)
            with self.assertRaises(RuntimeError):contract.validate_mirror_association(donor,contract.ATTACHMENTS[left],'rfoot_g')
        for parts in ['chest,pelvis,bicepl','chest,pelvis,forel,forer','chest,pelvis,handl,handr']:
            with self.assertRaises(RuntimeError):contract.parse_preserved_parts(parts)

    def test_explicit_preserved_sets_reject_unknown_duplicate_partial_pairs(self):
        expected={'pmh0_'+part+'001.mdl' for part in ('chest','pelvis','legl','legr')}
        self.assertEqual(contract.parse_preserved_parts('chest,pelvis,legl,legr'),expected)
        self.assertEqual(contract.parse_preserved_parts(),{'pmh0_chest001.mdl','pmh0_pelvis001.mdl'})
        for parts in ['chest,pelvis,legl','chest,pelvis,shinr','chest,pelvis,footl,footr',
                      'chest,pelvis,pmh0','chest,pelvis,legl,legr,legl','pelvis,legl,legr']:
            with self.subTest(parts=parts),self.assertRaises(RuntimeError):contract.parse_preserved_parts(parts)

    def test_no_overlap_family_mix_right_only_or_missing_accepted_thigh_pair(self):
        donor=contract.parse_preserved_parts('chest,pelvis,legl,legr')
        for parts in [['shinl'],['shinl','shinr']]:contract.validate_new_parts(parts,donor)
        for parts in [['legl'],['legl','legr'],['shinr'],['shinl','legr'],['shinl','shinl'],['footl'],['pmh0']]:
            with self.subTest(parts=parts),self.assertRaises(RuntimeError):contract.validate_new_parts(parts,donor)
        with self.assertRaisesRegex(RuntimeError,'explicit preserved accepted thigh'):
            contract.validate_new_parts(['shinl'],contract.parse_preserved_parts())
        complete=contract.parse_preserved_parts('chest,pelvis,legl,legr,shinl,shinr')
        with self.assertRaisesRegex(RuntimeError,'overlap'):contract.validate_new_parts(['shinl'],complete)
        for parts in [['footl'],['footl','footr']]:contract.validate_new_parts(parts,complete)
        with self.assertRaisesRegex(RuntimeError,'accepted thigh and shin'):
            contract.validate_new_parts(['footl'],donor)
        with self.assertRaises(RuntimeError):contract.validate_new_parts(['footr'],complete)

    def test_mirror_foot_family_is_bound_to_donor(self):
        donor={'part':'footl','joint':'lfoot_g'}
        contract.validate_mirror_association(donor,'lfoot_g','rfoot_g')
        for source,target in [('lfoot_g','rshin_g'),('lshin_g','rfoot_g'),('lfoot_g','lfoot_g')]:
            with self.assertRaises(RuntimeError):contract.validate_mirror_association(donor,source,target)

    def test_foot_package_requires_six_preserved_models_and_declared_feet(self):
        donor=contract.parse_preserved_parts('chest,pelvis,legl,legr,shinl,shinr')
        rows=[(Path(n).stem,2002,b'diagnostic') for n in donor]
        rows += [('pmh0_footl001',2002,b'left'),('pmx0',2002,b'stock')]
        validate_inventory(rows,['footl'],{'pmx0'},donor)
        for extra in ['pmh0','pmh0_footr001','pmh0_neck001']:
            with self.assertRaises(RuntimeError):validate_inventory(rows+[(extra,2002,b'bad')],['footl'],{'pmx0'},donor)

    def test_package_namespace_requires_preserved_four_plus_only_declared_shin(self):
        donor=contract.parse_preserved_parts('chest,pelvis,legl,legr')
        rows=[(Path(name).stem,2002,b'diagnostic') for name in donor]
        rows += [('pmh0_shinl001',2002,b'diagnostic'),('pmx0',2002,b'stock')]
        self.assertEqual(set(validate_inventory(rows,['shinl'],{'pmx0'},donor)),
                         {Path(name).stem for name in donor}|{'pmh0_shinl001'})
        for extra in [('pmh0_footl001',2002),('pmh0',2002),('a_ba',2002),('pmh0_shinr001',2002),
                      ('pmh0_shinl001',2009),('pmh0_oldshin001',2072)]:
            with self.subTest(extra=extra),self.assertRaises(RuntimeError):
                validate_inventory(rows+[(extra[0],extra[1],b'undeclared')],['shinl'],{'pmx0'},donor)
        with self.assertRaises(RuntimeError):validate_inventory(rows[:-2]+rows[-1:],['shinl'],{'pmx0'},donor)

    def test_recursive_receipt_union_does_not_hide_changed_ancestor(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary);client='c'*64
            def leaf(name):
                return {'clientSha256':client,'complete':True,'models':[{'name':name,'binarySha256':name}],
                        'materialResourceHashes':{name+'.plt':name}}
            def origin(name,native):
                path=folder/(str(len(list(folder.glob('*.json'))))+'-'+name+'.json');path.write_text(json.dumps(native))
                return {'path':str(path),'sha256':contract.sha(path),'models':[r['name'] for r in native['models']],
                        'materialResourceHashes':native['materialResourceHashes']}
            def combined(a,b):
                return {'clientSha256':client,'complete':True,'models':a['models']+b['models'],
                        'materialResourceHashes':a['materialResourceHashes']|b['materialResourceHashes'],
                        'composition':{'sourceReceipts':[origin(a['models'][0]['name'],a),origin(b['models'][0]['name'],b)]}}
            prior=combined(leaf('chest'),leaf('pelvis'))
            current=combined(prior,leaf('shin'))
            validate_unit_provenance(current)
            # Direct source receipt is unchanged, but nested ancestor bytes are now stale.
            Path(prior['composition']['sourceReceipts'][1]['path']).write_text('{}')
            with self.assertRaisesRegex(RuntimeError,'receipt changed'):validate_unit_provenance(current)

    def test_duplicate_models_or_missing_recursive_material_union_fail(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary);native={'clientSha256':'c'*64,'complete':True,'models':[],
                                          'materialResourceHashes':{},'composition':{'sourceReceipts':[]}}
            for name in ['chest','pelvis']:
                original={'clientSha256':'c'*64,'complete':True,'models':[{'name':name}],
                          'materialResourceHashes':{name+'.plt':'x'}}
                path=folder/(name+'.json');path.write_text(json.dumps(original))
                native['models']+=original['models'];native['materialResourceHashes'].update(original['materialResourceHashes'])
                native['composition']['sourceReceipts'].append({'path':str(path),'sha256':contract.sha(path),
                    'models':[name],'materialResourceHashes':original['materialResourceHashes']})
            validate_unit_provenance(native)
            bad=copy.deepcopy(native);bad['models'].append(bad['models'][0])
            with self.assertRaises(RuntimeError):validate_unit_provenance(bad)
            bad=copy.deepcopy(native);bad['materialResourceHashes']['undeclared.plt']='x'
            with self.assertRaises(RuntimeError):validate_unit_provenance(bad)


if __name__=='__main__': unittest.main()
