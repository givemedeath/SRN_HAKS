"""Portable decoder regressions; an actual asset replay is explicitly opt-in."""
import copy
import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest

import diagnostic_descendant_representation as m

def pin(p):
    return {'path':str(Path(p).resolve()),'sha256':hashlib.sha256(Path(p).read_bytes()).hexdigest()}

def document():
    return {'asset':{'version':'2.0'},'scene':0,'scenes':[{'nodes':[0]}],
            'nodes':[{'mesh':0}], 'meshes':[{'primitives':[{'attributes':
            {'POSITION':0,'NORMAL':1,'TEXCOORD_0':2},'indices':3}]}],
            'buffers':[{'byteLength':108}],
            'bufferViews':[{'buffer':0,'byteOffset':0,'byteLength':36},
                           {'buffer':0,'byteOffset':36,'byteLength':36},
                           {'buffer':0,'byteOffset':72,'byteLength':24},
                           {'buffer':0,'byteOffset':96,'byteLength':12}],
            'accessors':[{'bufferView':i,'componentType':5126 if i<3 else 5125,
                          'count':3,'type':'VEC3' if i<2 else 'VEC2' if i==2 else 'SCALAR'} for i in range(4)]}

def write_glb(path,doc):
    js=json.dumps(doc,separators=(',',':')).encode()
    js+=b' '*((-len(js))%4)
    data=bytes(108)
    body=struct.pack('<II',len(js),0x4e4f534a)+js+struct.pack('<II',len(data),0x004e4942)+data
    path.write_bytes(b'glTF'+struct.pack('<II',2,len(body)+12)+body)

class PortableDecoderTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
    def test_valid_detached_glb(self):
        p=self.root/'valid.glb';write_glb(p,document())
        doc,data=m.read_glb(p)
        self.assertEqual(m.accessor(doc,data,0).shape,(3,3))
    def test_extra_hidden_mesh(self):
        d=document();d['meshes'].append(copy.deepcopy(d['meshes'][0]))
        with self.assertRaises(m.RepresentationError):m.validate_document(d,bytes(108))
    def test_node_transform(self):
        d=document();d['nodes'][0]['translation']=[0,0,1]
        with self.assertRaises(m.RepresentationError):m.validate_document(d,bytes(108))
    def test_triangle_strip_rejected(self):
        d=document();d['meshes'][0]['primitives'][0]['mode']=5
        with self.assertRaises(m.RepresentationError):m.validate_document(d,bytes(108))
    def test_rig_payload_rejected(self):
        d=document();d['skins']=[]
        with self.assertRaises(m.RepresentationError):m.validate_document(d,bytes(108))
    def test_accessor_bounds(self):
        d=document();d['accessors'][0]['count']=4
        with self.assertRaises(m.RepresentationError):m.accessor(d,bytes(108),0)
    def test_external_buffer_rejected(self):
        d=document();d['bufferViews'][0]['buffer']=1
        with self.assertRaises(m.RepresentationError):m.accessor(d,bytes(108),0)
    def test_duplicate_json_key(self):
        p=self.root/'duplicate.json';p.write_text('{"schemaVersion":1,"schemaVersion":2}')
        with self.assertRaises(m.RepresentationError):m.strict_json(p)
    def test_invalid_hash(self):
        p=self.root/'input.bin';p.write_bytes(b'fixed')
        with self.assertRaises(m.RepresentationError):m.checked_pin({'path':str(p),'sha256':'z'*64})
    def test_invalid_path_type(self):
        with self.assertRaises(m.RepresentationError):m.checked_pin({'path':None,'sha256':'0'*64})
    def test_pin_detects_changed_input(self):
        p=self.root/'input.bin';p.write_bytes(b'fixed');row=pin(p);p.write_bytes(b'changed')
        with self.assertRaises(m.RepresentationError):m.checked_pin(row)
    def test_forged_seal(self):
        with self.assertRaises(m.RepresentationError):m.DiagnosticRepresentation(None,(),(),{},()).verify()
    def test_malformed_chunk_extent(self):
        p=self.root/'bad.glb';write_glb(p,document());b=bytearray(p.read_bytes());struct.pack_into('<I',b,12,len(b)*2);p.write_bytes(b)
        with self.assertRaises(m.RepresentationError):m.read_glb(p)
    def test_schema_version_is_exact_integer(self):
        for version in (True,1.0,'1'):
            c={k:{} for k in ('target','stockReference','baseline','final')}
            c.update(kind='diagnostic-descendant-representation',schemaVersion=version,part='chest',space='working',operations=[],consumers=[],physicalInputs=[])
            p=self.root/'schema.json';p.write_text(json.dumps(c))
            with self.subTest(version=version), self.assertRaisesRegex(m.RepresentationError,'Unknown contract'):
                m.prepare_diagnostic_representation(pin(p),target_path=p,target={},part='chest')

@unittest.skipUnless(os.environ.get('SRN_DIAGNOSTIC_CHEST_CONTRACT'),'Actual chest contract not explicitly bound')
class ActualChestTests(unittest.TestCase):
    def test_actual_chest_replay(self):
        original=Path(os.environ['SRN_DIAGNOSTIC_CHEST_CONTRACT'])
        c=json.loads(original.read_text(encoding='utf-8'))
        old={x['path'] for x in c['consumers']}
        consumer=pin(Path(m.__file__).resolve())
        c['consumers']=[consumer]
        c['physicalInputs']=[p for p in c['physicalInputs'] if p['path'] not in old]+[consumer]
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'contract.json';p.write_text(json.dumps(c),encoding='utf-8')
            target=m.strict_json(c['target']['path'])
            obj=m.prepare_diagnostic_representation(pin(p),target_path=c['target']['path'],target=target,part='chest')
            self.assertFalse(obj.array('serializedGlbF32','positions').flags.writeable)
            obj.geometry_proof(c['final']['geometry'],c['final']['candidate'],'chest','working')

if __name__=='__main__':unittest.main()
