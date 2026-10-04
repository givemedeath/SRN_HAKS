"""Reject hidden body/rig baggage and baseline map changes even with fresh hashes."""
import unittest
import json
from pathlib import Path
import tempfile

from effective_body_contract import (
    BODY_PARTS, PRESERVED_PARTS, validate_body_ownership, validate_preserved_bytes,
    validate_effective_normal_dependencies, sha)


def inventory(parts):
    models={'pmh0_'+p+'001.mdl':p for p in parts}
    resources={'pmh0_'+p+'001'+s:'frozen-'+p+s for p in parts
               for s in ('.mdl','.mtr','.plt','n.tga','r.tga')}
    resources.update({'pmh0_pelvis001f.mtr':'cloth-material','pmh0_pelvis001f.tga':'cloth-map'})
    return models,resources


class EffectiveBodyContractTests(unittest.TestCase):
    def test_roughness_descendant_preserves_real_compiled_normal_binding(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);original=root/'original';current=root/'current'
            for folder in [original,current]:(folder/'resources').mkdir(parents=True)
            name='pmh0_chest001.mtr';normal='pmh0_chest001n.tga'
            text='renderhint NormalTangents\ntexture1 pmh0_chest001n\nparameter float Roughness 0.72\n'
            (original/'resources'/name).write_text(text)
            for folder in [original,current]:(folder/'resources'/normal).write_bytes(b'authored-normal')
            receipt=original/'native-compile.json';receipt.write_text(json.dumps({'models':[]}))
            native={'materialResourceHashes':{name:sha(original/'resources'/name),normal:sha(original/'resources'/normal)},
                    'composition':{'sourceReceipts':[{'path':str(receipt)}]}}
            (current/'resources'/name).write_text(text.replace('0.72','0')+'texture3 pmh0_chest001r\n')
            validate_effective_normal_dependencies(current,native)
            (current/'resources'/normal).write_bytes(b'wrong-normal-pixels')
            with self.assertRaisesRegex(RuntimeError,'compiled tangent dependency'):
                validate_effective_normal_dependencies(current,native)
            (current/'resources'/normal).write_bytes(b'authored-normal')
            (current/'resources'/name).write_text(text.replace('texture1 pmh0_chest001n','texture1 unrelated'))
            with self.assertRaisesRegex(RuntimeError,'compiled tangent bindings'):
                validate_effective_normal_dependencies(current,native)
            (current/'resources'/name).write_text(text.replace('0.72','0'))
            (original/'resources'/name).write_text('changed-original')
            with self.assertRaisesRegex(RuntimeError,'unavailable/changed'):
                validate_effective_normal_dependencies(current,native)

    def test_complete_and_partial_ownership_are_distinct(self):
        for parts in [PRESERVED_PARTS, PRESERVED_PARTS|{'footl','footr'}, BODY_PARTS]:
            models,resources=inventory(parts)
            validate_body_ownership(models,resources,parts==BODY_PARTS)
            with self.assertRaisesRegex(RuntimeError,'Complete-body'):
                validate_body_ownership(models,resources,parts!=BODY_PARTS)

    def test_even_hashed_extra_prefix_resources_are_rejected(self):
        models,resources=inventory(BODY_PARTS)
        for name in ['pmh0.mdl','a_ba.mdl','appearance.2da','pmx0_head001.mdl',
                     'pmh0_chest001old.mtr','pmh0_handl001f.tga','pmh0_neck001.mdl']:
            with self.subTest(name=name),self.assertRaisesRegex(RuntimeError,'undeclared'):
                validate_body_ownership(models,{**resources,name:'fresh-hash'},True)

    def test_missing_maps_partial_pairs_and_changed_style_are_rejected(self):
        models,resources=inventory(BODY_PARTS)
        missing=dict(resources);missing.pop('pmh0_handr001r.tga')
        with self.assertRaisesRegex(RuntimeError,'Missing'):
            validate_body_ownership(models,missing,True)
        partial,partial_resources=inventory(BODY_PARTS-{'handr'})
        with self.assertRaisesRegex(RuntimeError,'complete selected pairs'):
            validate_body_ownership(partial,partial_resources,False)
        wrong=dict(models);wrong['pmh0_handl002.mdl']=wrong.pop('pmh0_handl001.mdl')
        with self.assertRaisesRegex(RuntimeError,'namespace'):
            validate_body_ownership(wrong,resources,True)

    def test_preserved_current_materials_are_compared_not_old_compile_inputs(self):
        _,preserved=inventory(PRESERVED_PARTS)
        _,current=inventory(BODY_PARTS)
        selection={'accepted6ResourceHashes':preserved}
        validate_preserved_bytes(selection,current)
        for name in ['pmh0_pelvis001.plt','pmh0_chest001.mtr','pmh0_shinl001n.tga']:
            changed={**current,name:'old-compiler-material'}
            with self.subTest(name=name),self.assertRaisesRegex(RuntimeError,'bytes changed'):
                validate_preserved_bytes(selection,changed)
        incomplete=dict(preserved);incomplete.pop('pmh0_pelvis001f.tga')
        with self.assertRaisesRegex(RuntimeError,'bytes changed'):
            validate_preserved_bytes({'accepted6ResourceHashes':incomplete},current)


if __name__=='__main__':unittest.main()
