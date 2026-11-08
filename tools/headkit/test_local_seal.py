import json,tempfile,unittest
from pathlib import Path
import numpy as np
from PIL import Image
from headkit.gltf import mesh,write_mesh
from headkit.local_seal import bundle,read_bundle,geometry_fingerprint,genus,allocate_uv
from headkit.stock_encoding import preserve

class LocalRepairContract(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
  self.source=self.root/'source.glb'
  p=np.array([[0,0,0],[1,0,0],[0,1,0],[0,0,1]],np.float32);f=np.array([[0,2,1],[0,1,3],[1,2,3],[2,0,3]])
  uv=np.tile(np.array([[.1,.1],[.2,.1],[.1,.2]]),(4,1,1));write_mesh(self.source,p,f,uv);self.value=mesh(self.source)
 def test_genus_requires_one_closed_shell(self):
  p=self.value['positions'];f=self.value['faces'];self.assertEqual(genus(p,f),0)
  with self.assertRaises(ValueError):genus(p,f[:-1])
  with self.assertRaises(ValueError):genus(np.r_[p,p+5],np.r_[f,f+len(p)])
 def test_fingerprint_includes_uv(self):
  self.assertNotEqual(geometry_fingerprint(self.value),geometry_fingerprint({**self.value,'uv':self.value['uv']+.001}))
 def test_bundle_verifies_embedded_bytes(self):
  paths={}
  for key in ('basecolor4k','shades','layers','decoded','hairPalette'):
   p=self.root/(key+'.png');Image.new('RGB',(2,2)).save(p);paths[key]=p
  output=self.root/'bundle.glb';bundle(self.source,paths,{'1':99},output)
  with self.assertRaisesRegex(ValueError,'dimensions'):read_bundle(output)
  from headkit.gltf import load,encode
  d,b,_=load(output.read_bytes());b=bytearray(b);view=d['bufferViews'][d['extras']['headkitLocalRepair']['maps']['shades']['bufferView']]
  b[view.get('byteOffset',0)]^=1;output.write_bytes(encode(d,bytes(b)))
  with self.assertRaisesRegex(ValueError,'Baseline map changed'):read_bundle(output)
 def test_new_chart_avoids_all_original_charts(self):
  old=np.array([[[.3,.3],[.6,.3],[.3,.6]]]);new,report=allocate_uv(old,3,size=64)
  from headkit.uv import raster_audit
  self.assertFalse(np.any((raster_audit(old,64)[1]>=0)&(raster_audit(new,64)[1]>=0)));self.assertEqual(report['gutterPixels'],5)
 def test_manifest_stock_import_requires_typed_local_route_and_keeps_direct_export_blocked(self):
  from headkit.common import manifest,pin
  data={'schemaVersion':1,'id':'test','inputs':{role:{'path':'source.glb','sha256':pin(self.source)['sha256']}
       for role in ('runtimeColor','ownership1k','uvMesh')},
       'faceMasks':{},'ownership':{'featureChannels':True},'tone':{'faceTreatment':{}},'quality':{},
       'mesh':{'localSeal':{'reviewed':True}},'palette':{'fullShadeRange':True,'preserveStockEncoding':True}}
  path=self.root/'manifest.json';path.write_text(json.dumps(data))
  manifest(path)
  data['inputs']['runtimeShades']=data['inputs']['runtimeColor'];path.write_text(json.dumps(data))
  with self.assertRaisesRegex(ValueError,'runtimeShades'):manifest(path)
  data['inputs'].pop('runtimeShades');data['palette']['preserveStockEncoding']=False;path.write_text(json.dumps(data))
  with self.assertRaisesRegex(ValueError,'do not import'):manifest(path)
 def test_body_calibration_measures_preserved_face_and_actual_body(self):
  from unittest.mock import patch
  from headkit.stock_encoding import body_calibration
  import struct
  body=self.root/'body.plt';body.write_bytes(b'PLT V1  '+bytes(8)+struct.pack('<II',1,1)+bytes([100,0]))
  shades=np.full((1024,1024),101,np.uint8);layers=np.zeros_like(shades)
  owners=np.zeros_like(shades,dtype=int)
  with patch('headkit.uv.face_region',return_value=(np.ones(4,bool),None)),patch('headkit.uv.raster_audit',return_value=({},owners)):
   result=body_calibration(self.source,shades,layers,body)
   self.assertEqual(result['target'],100);self.assertEqual(result['achieved'],101)
   self.assertEqual(result['faceTexels'],1024*1024)
   with self.assertRaisesRegex(ValueError,'Too few'):
    body_calibration(self.source,shades,np.ones_like(layers),body)
 def test_stock_import_records_measured_body_calibration_without_changing_indices(self):
  from unittest.mock import patch
  import struct
  self.prepare_encoding();self.rows={'0':1};self.arrays['rows']=np.array(json.dumps(self.rows))
  self.arrays['layers'][:]=0;self.save();Image.fromarray(self.arrays['layers']).save(self.ownership)
  body=self.root/'body.plt';body.write_bytes(b'PLT V1  '+bytes(8)+struct.pack('<II',1,1)+bytes([99,0]))
  with patch('headkit.uv.face_region',return_value=(np.ones(4,bool),None)),patch('headkit.uv.raster_audit',return_value=({},np.zeros((1024,1024),int))):
   result=preserve(self.package,self.ownership,{'0':self.palette},self.rows,self.source,self.root/'output',body_skin=body)
  calibration=result['layers']['0']['shadeRange']['skinMedian']
  self.assertEqual(calibration['target'],99);self.assertEqual(calibration['achieved'],100)
  self.assertTrue(np.array_equal(np.asarray(Image.open(result['shades']['path'])),self.arrays['shades']))
 def prepare_encoding(self):
  shades=np.full((1024,1024),100,np.uint8);layers=np.ones_like(shades);rgb=np.full((1024,1024,3),100,np.uint8)
  rgba=np.zeros((2,256,4),np.uint8);rgba[:,:,:3]=np.arange(256,dtype=np.uint8)[None,:,None];rgba[:,:,3]=255
  self.palette=self.root/'palette.png';Image.fromarray(rgba).save(self.palette)
  self.ownership=self.root/'ownership.png';Image.fromarray(layers).save(self.ownership)
  self.package=self.root/'runtime.npz';self.rows={'1':1}
  self.arrays=dict(kind=np.array('headkit-stock-runtime-v1'),shades=shades,layers=layers,rgb=rgb,
    rows=np.array(json.dumps(self.rows)),geometryFingerprint=np.array(geometry_fingerprint(self.value)));self.save()
 def save(self):np.savez_compressed(self.package,**self.arrays)
 def run_preserve(self):return preserve(self.package,self.ownership,{'1':self.palette},self.rows,self.source,self.root/'output')
 def test_stock_import_preserves_every_index(self):
  self.prepare_encoding();result=self.run_preserve()
  self.assertTrue(np.array_equal(np.asarray(Image.open(result['shades']['path'])),self.arrays['shades']))
  self.assertEqual(result['preservedStockEncoding']['reprocessedTexels'],0)
 def test_stock_import_rejects_geometry_rows_ownership_and_decode_drift(self):
  for key,changed in [('geometryFingerprint',np.array('bad')),('rows',np.array('{"1":0}')),
       ('rgb',np.zeros((1024,1024,3),np.uint8)),('layers',np.zeros((1024,1024),np.uint8))]:
   with self.subTest(key=key):
    self.prepare_encoding();self.arrays[key]=changed;self.save()
    with self.assertRaises(ValueError):self.run_preserve()
 def test_stock_import_rejects_transparent_next_shade(self):
  self.prepare_encoding();rgba=np.asarray(Image.open(self.palette)).copy();rgba[1,101,3]=0;Image.fromarray(rgba).save(self.palette)
  with self.assertRaisesRegex(ValueError,'transparency'):self.run_preserve()
 def test_bundle_binds_hair_tie_to_exact_approved_palette_maps(self):
  from headkit.common import pin
  from headkit.gltf import load
  paths={}
  for key in ('basecolor4k','shades','layers','decoded','hairPalette'):
   path=self.root/(key+'.png')
   Image.new('L' if key in ('shades','layers') else 'RGB',(2,2),1).save(path);paths[key]=path
  report={'rows':{'1':1},'layers':{'1':{'pixels':4,'shadeRange':{'checked':True,'endTie':.14}}},
          **{role:pin(paths[name]) for role,name in [('shades','shades'),('ownership','layers'),('decoded','decoded')]}}
  report_path=self.root/'palette.json';report_path.write_text(json.dumps(report))
  out=self.root/'with-evidence.glb';bundle(self.source,paths,{'1':1},out,palette_report=report_path)
  doc,_,_=load(out.read_bytes())
  evidence=doc['extras']['headkitLocalRepair']['hairEndTieEvidence']
  self.assertEqual(evidence['report'],pin(report_path));self.assertEqual(evidence['endTie'],.14)
  for role in ('rows','shades','ownership','decoded'):
   changed=json.loads(json.dumps(report))
   if role=='rows':changed[role]={'1':0}
   else:changed[role]['sha256']='0'*64
   report_path.write_text(json.dumps(changed))
   with self.subTest(role=role),self.assertRaisesRegex(ValueError,'Baseline palette'):
    bundle(self.source,paths,{'1':1},self.root/(role+'.glb'),palette_report=report_path)
 def test_hair_tie_is_diluted_by_added_and_changed_hair(self):
  from headkit.local_seal import retained_hair_evidence
  layers=np.ones(100,dtype=np.uint8);shades=np.full(100,100,np.uint8)
  evidence={'report':{'path':'approved.json','sha256':'a'*64},'endTie':.14,'hairTexels':100}
  unchanged=retained_hair_evidence(evidence,shades,layers,shades,layers)
  self.assertAlmostEqual(unchanged['lowerBound'],.1395)
  old_layers=np.r_[layers,np.zeros(100,dtype=np.uint8)]
  old_shades=np.r_[shades,np.zeros(100,dtype=np.uint8)]
  grown=retained_hair_evidence(evidence,old_shades,old_layers,old_shades,np.ones(200,np.uint8))
  self.assertAlmostEqual(grown['lowerBound'],.06975)
  changed=shades.copy();changed[:10]=101
  reduced=retained_hair_evidence(evidence,shades,layers,changed,layers)
  self.assertAlmostEqual(reduced['lowerBound'],.0395)
 def test_preserved_hair_tie_keeps_quality_exemption_without_touching_indices(self):
  from headkit.local_seal import retained_hair_evidence
  from headkit.quality import shade_span_failures
  self.prepare_encoding()
  # A 0.657 span passes the 0.5 numeric floor but needs the approved 0.75 hair exemption.
  self.arrays['shades'][:512]=43;self.arrays['shades'][512:]=210
  self.arrays['rgb']=np.repeat(self.arrays['shades'][...,None],3,axis=2)
  e=retained_hair_evidence({'report':{'path':'approved.json','sha256':'a'*64},'endTie':.14,
       'hairTexels':1024*1024},self.arrays['shades'],self.arrays['layers'],self.arrays['shades'],self.arrays['layers'])
  self.arrays['hairEndTieEvidence']=np.array(json.dumps(e));self.save()
  result=preserve(self.package,self.ownership,{'1':self.palette},self.rows,self.source,self.root/'output',full_range=True)
  span=result['layers']['1']['shadeRange']['spanFraction']
  self.assertAlmostEqual(span,.657)
  self.assertEqual(shade_span_failures({'1':span},result,.75,hair_end_tie=.1),([],['1']))
  self.assertTrue(np.array_equal(np.asarray(Image.open(result['shades']['path'])),self.arrays['shades']))
 def test_preserved_hair_rejects_inflated_tie_metadata(self):
  from headkit.local_seal import retained_hair_evidence
  self.prepare_encoding()
  e=retained_hair_evidence({'report':{'path':'approved.json','sha256':'a'*64},'endTie':.14,
       'hairTexels':1024*1024},self.arrays['shades'],self.arrays['layers'],self.arrays['shades'],self.arrays['layers'])
  e['lowerBound']=.99;self.arrays['hairEndTieEvidence']=np.array(json.dumps(e));self.save()
  with self.assertRaisesRegex(ValueError,'lower bound'):
   self.run_preserve()
 def test_missing_tie_does_not_invent_an_exemption_from_quantized_colours(self):
  from headkit.quality import shade_span_failures
  self.prepare_encoding();self.arrays['shades'][:512]=43;self.arrays['shades'][512:]=210
  self.arrays['rgb']=np.repeat(self.arrays['shades'][...,None],3,axis=2);self.save()
  result=preserve(self.package,self.ownership,{'1':self.palette},self.rows,self.source,self.root/'output',full_range=True)
  self.assertEqual(shade_span_failures({'1':.657},result,.75,hair_end_tie=.1),(['shadeSpan1'],[]))
 def test_stock_import_keeps_full_range_gate(self):
  self.prepare_encoding();self.arrays['shades'][:512]=90;self.arrays['shades'][512:]=110
  self.arrays['rgb']=np.repeat(self.arrays['shades'][...,None],3,axis=2);self.save()
  with self.assertRaisesRegex(ValueError,'range floor'):
   preserve(self.package,self.ownership,{'1':self.palette},self.rows,self.source,self.root/'output',full_range=True)
if __name__=='__main__':unittest.main()
