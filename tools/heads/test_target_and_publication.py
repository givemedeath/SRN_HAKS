"""Protected body pins, fail-closed publication and exact archive payloads."""
import copy
from pathlib import Path
import struct
import tempfile
import unittest
from head_workflow import Session,make_roster,pin,validate_target,write_fresh
from publish_head_pack import publish
from verify_head_hak import payload


class TargetAndPublicationTests(unittest.TestCase):
    def test_target_rejects_changed_body_neck_palette_and_revision(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); protected=root/'body.mdl';protected.write_bytes(b'body')
            manifest=root/'manifest.json';write_fresh(manifest,{'resources':[{'path':'body.mdl','sha256':pin(protected)['sha256']}]})
            stock=[]
            for name in ('rig','neck','skin','hair','animation'):
                path=root/name;path.write_bytes(name.encode());stock.append(pin(path))
            target={'schemaVersion':1,'kind':'srn-head-target','approved':True,'race':'human','sex':'male',
                'prefix':'pmh0','phenotype':0,'bodyRevision':pin(manifest)['sha256'],'bodyManifest':pin(manifest),
                'bodyResourceRoot':str(root),'rig':stock[0],'neckGeometry':stock[1],'palettes':stock[2:4],
                'animations':stock[4:],'headBindMatrix':[[1,0,0,0],[0,1,0,0],[0,0,1,1.75],[0,0,0,1]],
                'cranialEnvelope':[[-.1,-.1,-.06],[.1,.15,.2]],'landmarkTolerance':.025}
            validate_target(target)
            bad=copy.deepcopy(target);bad['bodyRevision']='unrelated'
            with self.assertRaisesRegex(ValueError,'revision'):validate_target(bad)
            for path in [protected,*[Path(p['path']) for p in stock]]:
                original=path.read_bytes();path.write_bytes(b'changed')
                with self.subTest(path=path),self.assertRaises(ValueError):validate_target(target)
                path.write_bytes(original)

    def test_pending_client_cannot_copy_resources_or_register_pack(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);roster=root/'roster.json';write_fresh(roster,make_roster())
            session=Session.create(root/'session',roster);configuration=root/'hakbuilder.json'
            configuration.write_text('{"HakList":[]}')
            with self.assertRaisesRegex(ValueError,'review missing'):
                publish(session.root,['human-male-01'],root,root/'publication.json')
            self.assertEqual(configuration.read_text(),'{"HakList":[]}')
            self.assertFalse((root/'srn_head').exists());self.assertFalse((root/'publication.json').exists())

    def test_native_hak_payload_rejects_duplicate_and_outside_pointers(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'fixture.hak';data=bytearray(160+48+16+6)
            data[:8]=b'HAK V1.0';struct.pack_into('<I',data,16,2);struct.pack_into('<II',data,24,160,208)
            for i,name in enumerate((b'head',b'headn')):
                struct.pack_into('<16sIH',data,160+24*i,name,i,2002 if i==0 else 3)
                struct.pack_into('<II',data,208+8*i,224+3*i,3)
            data[224:]=b'abcdef';path.write_bytes(data);self.assertEqual(len(payload(path)),2)
            struct.pack_into('<I',data,208,9999);path.write_bytes(data)
            with self.assertRaisesRegex(ValueError,'bounds'):payload(path)

    def test_revision_preserves_parent_credit_and_invalidates_only_selected_gates(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);roster=root/'roster.json';write_fresh(roster,make_roster())
            parent=Session.create(root/'parent',roster)
            parent.append('reserved',requestId='paid',estimatedCredits=20)
            parent.append('settled',requestId='paid',credits=20)
            for identity in ('human-male-01','human-male-02'):
                for stage in ('reference','donor','fitting','assembly','native'):
                    parent.append('review',designId=identity,stage=stage,report={'sha256':stage})
            before={p.name:p.read_bytes() for p in (parent.root/'events').glob('*.json')}
            child=parent.fork_revision(root/'child',['human-male-01'],'fitting',[pin(roster)])
            self.assertEqual(child.credit_used(),20)
            self.assertEqual(set(child.reviews('human-male-01')),{'reference','donor'})
            self.assertIn('native',child.reviews('human-male-02'))
            self.assertEqual(before,{p.name:p.read_bytes() for p in (parent.root/'events').glob('*.json')})
            fresh=parent.fork_revision(root/'fresh-reference',['human-male-01'],'reference',[pin(roster)])
            self.assertEqual(fresh.credit_used(),20);self.assertEqual(fresh.reviews('human-male-01'),{})
            self.assertIn('native',fresh.reviews('human-male-02'))
            with self.assertRaisesRegex(ValueError,'Fresh descendant'):parent.fork_revision(root/'child',['human-male-01'],'fitting',[pin(roster)])


if __name__=='__main__':unittest.main()
