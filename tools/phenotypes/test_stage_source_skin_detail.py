"""Original-pixel replay, chart, source/mirror and treatment rejection tests."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image

import target_contract as c
import source_skin_detail_contract as detail
import replay_stage_skin_detail as replay
from place_purposebuilt_pelvis import read_glb,raw_corners,write_glb
from mirror_stock_limb_part import detached_affine_bake,reflection_between_frames
from test_human_female_stock_exact import stock_fixture
from test_diagnose_native_cap_normal import fixture


def write(path,value):
    path.write_text(json.dumps(value),encoding='utf-8');return path


def tiny_atlas():
    size=64;y,x=np.indices((size,size));height=np.repeat(np.linspace(-.014,.045,size)[:,None],size,1)
    # Deterministic authored fixture pixels; no renderer or stochastic source.
    original=np.stack([150+((x+3*y)%19),80+((x+2*y)%11),55+((x+y)%7)],axis=2).astype('u1')
    protected=np.zeros((size,size),bool);protected[7:10,8:12]=True
    masks={'coverage':np.ones((size,size),bool),'protected':protected}
    theta=np.where(x<32,0.,.7);shaft=np.stack([.035*np.cos(theta),.035*np.sin(theta),height],axis=2)
    owner=np.where(x<32,0,1).astype('i4');roots=np.array([0,1])
    stats=[np.array(v,float) for v in ([190,80,60],[190,94,74],[183,103,59],[202,110,77])]
    return original,height,masks,shaft,owner,roots,stats


class SourceDetailMathTests(unittest.TestCase):
    def test_charts_use_full_physical_uv_edges_and_no_color_bleed(self):
        p=np.array([[0,0,0],[1,0,0],[0,1,0],[0,0,0],[1,0,0],[1,-1,0]],float)
        uv=np.array([[0,0],[1,0],[0,1],[.2,.2],[.8,.2],[.8,.8]],float);faces=np.array([[0,1,2],[3,4,5]])
        self.assertEqual(len(np.unique(detail.chart_roots(p,uv,faces))),2)
        uv[3:5]=uv[:2];self.assertEqual(len(np.unique(detail.chart_roots(p,uv,faces))),1)
        charts=np.tile([0]*5+[1]*5,(6,1));rgb=np.zeros((6,10,3),dtype='u1');rgb[:,:5]=30;rgb[:,5:]=200
        (a,b),_=detail.chart_blurs([rgb,rgb],charts,np.ones(charts.shape,bool))
        np.testing.assert_allclose(a,rgb,atol=1e-12);np.testing.assert_array_equal(a,b)

    def test_periodic_nearest_matches_exhaustive_metric_and_lowest_id_tie(self):
        st=np.array([-np.pi+.001,-np.pi+.001,0.]);sh=np.array([.030,.030,.030]);ids=np.array([9,3,1])
        qt=np.array([np.pi-.001,0.]);qh=np.array([.030,.030]);selected,error,_=detail.exact_periodic_nearest(st,sh,ids,qt,qh)
        np.testing.assert_array_equal(selected,[3,1])
        source=np.c_[.035*np.cos(st),.035*np.sin(st),sh];query=np.c_[.035*np.cos(qt),.035*np.sin(qt),qh]
        for i,q in enumerate(query):
            distance=((source-q)**2).sum(1);winners=ids[distance==distance.min()]
            self.assertEqual(selected[i],winners.min());self.assertAlmostEqual(error[i],np.sqrt(distance.min()))
        with self.assertRaisesRegex(ValueError,'cohort'):
            detail.exact_periodic_nearest(st,np.array([.023,.030,.030]),ids,qt,qh)
        with self.assertRaises(ValueError):detail.exact_periodic_nearest(np.array([0.]),np.array([.025]),np.array([1]),np.array([1.]),np.array([.039]))

    def test_two_rgb_phases_preserve_protected_source_and_donor_lineage(self):
        original,h,masks,shaft,owner,roots,stats=tiny_atlas();saved=original.copy()
        parent,_=detail.common_tone(original,h,masks,'shinl',*stats)
        rgb,lineage,_,metrics=detail.detail_transfer(original,parent,h,masks,shaft,np.zeros(2),roots,owner,stats[2]/stats[0])
        np.testing.assert_array_equal(original,saved);np.testing.assert_array_equal(rgb[masks['protected']],original[masks['protected']])
        self.assertTrue(np.any(rgb!=parent));self.assertLess(metrics['maximumLookupMetricErrorMeters'],.001)
        ids=lineage['donorSourcePixelId'][lineage['targetMask']]
        self.assertTrue(lineage['donorMask'].ravel()[ids].all())
        np.testing.assert_array_equal(rgb[masks['coverage']&~lineage['targetMask']],parent[masks['coverage']&~lineage['targetMask']])
        goal=lineage['donorHeightGoal'][lineage['targetMask']];self.assertGreaterEqual(goal.min(),.024);self.assertLessEqual(goal.max(),.040)
        uv=lineage['donorOriginalUV'][lineage['targetMask']];np.testing.assert_array_equal(uv,(np.c_[ids%64+.5,ids//64+.5]/64).astype('f4'))
        # A direct byte change can never pass an otherwise identical replay.
        bad=rgb.copy();i=np.flatnonzero(lineage['targetMask'])[0];bad.reshape(-1,3)[i,0]^=1
        with self.assertRaisesRegex(ValueError,'pixels differ'):replay.exact_image(bad,rgb,'rehashedRGB')

    def test_rehashed_donor_chart_support_protected_or_padding_claims_reject(self):
        original,h,masks,shaft,owner,roots,stats=tiny_atlas();parent,_=detail.common_tone(original,h,masks,'shinl',*stats)
        _,lineage,_,_=detail.detail_transfer(original,parent,h,masks,shaft,np.zeros(2),roots,owner,stats[2]/stats[0])
        detail.match_arrays(lineage,lineage)
        for key in ('donorSourcePixelId','sourcePixelChartRoot','weight','protected','paddingSourcePixelId','donorOriginalUV'):
            bad={k:v.copy() for k,v in lineage.items()};flat=bad[key].reshape(-1)
            index=np.flatnonzero(np.isfinite(flat))[0]
            flat[index]=not flat[index] if flat.dtype==bool else flat[index]+1
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'mathematical replay differs'):detail.match_arrays(bad,lineage)
        with self.assertRaisesRegex(ValueError,'inventory'):detail.match_arrays({**lineage,'approval':np.array([True])},lineage)

    def test_original_ao_siblings_use_final_rgb_fractional_luma_once(self):
        rgb=np.tile([183,103,59],(3,3,1)).astype('u1');red=np.full((3,3),57,dtype='u1')
        for ao in (0,.15,.35):
            expected=(np.dot(rgb.astype(float),[.2126,.7152,.0722])*(1-ao*(1-57/255))).astype('u1')
            np.testing.assert_array_equal(detail.intensity(rgb,red,ao),expected)
        # Pre-truncated/pre-AO intensity is not a legal color parent.
        with self.assertRaisesRegex(ValueError,'byteRGB'):detail.intensity(detail.intensity(rgb,red,.15),red,.35)
        for value in (True,.2,-.1):
            with self.assertRaises(ValueError):detail.intensity(rgb,red,value)
        np.testing.assert_array_equal(detail.intensity(rgb,red,0),(rgb.astype(float)@detail.LUMA).astype('u1'))

    def test_exact_controls_reject_generic_png_strength_and_foreign_modes(self):
        valid={'mode':detail.MODE,'receipt':{'path':'r','sha256':'a'*64},'sourceManifest':{'path':'m','sha256':'b'*64}}
        detail.controls(valid)
        for change in ({'png':'arbitrary.png'},{'strength':.65},{'accepted':True},{'mode':'c1'},{'mode':'original-source-uv-detail-v2'}):
            with self.assertRaises(ValueError):detail.controls({**valid,**change})
        for bad in ({'receipt':{}},{'sourceManifest':{'path':'m','sha256':'A'*64}}):
            with self.assertRaises(ValueError):detail.controls({**valid,**bad})


class SourceDetailBindingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.tp,self.target=stock_fixture(self.root)
        doc,binary=fixture();self.source=self.root/'shin.glb';write_glb(self.source,doc,binary)
        extra={};p,n,uv,_=raw_corners(doc,binary,extra=extra);t=np.concatenate(extra['TANGENT']['rows']);nu=uv.copy();nu[:,:,1]=1-nu[:,:,1]
        archive=self.root/'corners.npz';np.savez_compressed(archive,positions=p,normals=n,uvGltf=uv,uvNative=nu,tangents=t)
        self.rec={'schemaVersion':2,'kind':'target-part-geometry',**c.binding(self.tp,self.target,'working'),
                  'part':'shinl','joint':c.PART_JOINTS['shinl'],'model':c.model(self.target,'shinl'),'operation':'measured-angular-profile-ankle-taper',
                  'candidate':str(self.source),'candidateSha256':c.sha(self.source),'statureApplications':0,
                  'attachmentWorld':c.frame(self.target,c.PART_JOINTS['shinl'],'working').tolist(),
                  'nativeCornerArchive':replay.file_row(archive),'frozenInputs':{str(self.source):c.sha(self.source)}}
        self.rp=write(self.root/'geometry.json',self.rec);self.appearance={'leftGeometry':{'shinl':replay.file_row(self.rp)}}
        hashes={key:hashlib.sha256(np.asarray(value,dtype='f4').tobytes()).hexdigest() for key,value in
                [('positionsFloat32',p),('normalsFloat32',n),('uvFloat32',uv),('tangentsFloat32',t)]}
        self.entry={'part':'shinl','materialDonorPart':'shinl','workingGeometryReceipt':replay.file_row(self.rp),
                    'workingCandidate':replay.file_row(self.source),'nativeCornerArchive':replay.file_row(archive),
                    'originalFitReceipt':{},'originalUntreatedCandidate':{},'originalMaps':{},'originalUvLocationAtlas':{},
                    'originalToCurrentCornerOrder':[0,1,2],'materialRoles':{'0':'skin'},'exactSourceAttributeSha256':hashes,
                    'derivedColorField':'color','derivedAO0IntensityField':'intensityAO0'}

    def tearDown(self):self.tmp.cleanup()

    def invoke(self):return replay.validate_geometry(self.entry,'shinl',self.appearance,self.tp,self.target,replay.Inputs())

    def rebound_receipt(self):
        write(self.rp,self.rec);self.entry['workingGeometryReceipt']=replay.file_row(self.rp);self.appearance['leftGeometry']['shinl']=replay.file_row(self.rp)

    def test_literal_source_archive_pnut_and_rig_binding(self):
        row=self.invoke();self.assertEqual(row['source'],self.source)
        self.assertEqual(row['receipt']['attachmentWorld'],self.rec['attachmentWorld'])
        self.entry['exactSourceAttributeSha256']['normalsFloat32']='0'*64
        with self.assertRaisesRegex(ValueError,'attribute differs'):self.invoke()

    def test_foreign_stale_part_frame_and_chained_stage_sources_reject(self):
        for key,value in [('part','footl'),('targetId','foreign'),('kind','target-part-stage'),('statureApplications',1)]:
            original=deepcopy(self.rec);self.rec[key]=value;self.rebound_receipt()
            with self.subTest(key=key),self.assertRaises(ValueError):self.invoke()
            self.rec=original;self.rebound_receipt()
        self.rec['attachmentWorld'][0][3]+=.01;self.rebound_receipt()
        with self.assertRaisesRegex(ValueError,'attachment'):self.invoke()
        self.rec['attachmentWorld'][0][3]-=.01;self.rebound_receipt();self.source.write_bytes(self.source.read_bytes()+b' ')
        with self.assertRaises(ValueError):self.invoke()

    def test_actual_installed_opposite_frame_mirror_and_rejection(self):
        left=self.invoke();matrix,plane=reflection_between_frames(c.frame(self.target,c.PART_JOINTS['shinl'],'working'),
                    c.frame(self.target,c.PART_JOINTS['shinr'],'working'),[0,0,0],[1,0,0])
        doc,binary,_,_=detached_affine_bake(left['document'],left['binary'],matrix,True);right_source=self.root/'right.glb';write_glb(right_source,doc,binary)
        cfg={'schemaVersion':2,'operation':'mirror','part':'shinr','sourcePart':'shinl','coordinateSpace':'working',
             'source':str(self.source),'sourceSha256':c.sha(self.source),'sourceReceipt':str(self.rp),'sourceReceiptSha256':c.sha(self.rp),
             'targetContract':str(self.tp),'targetContractSha256':c.sha(self.tp),'planeOriginWorld':[0,0,0],'planeNormalWorld':[1,0,0]}
        cp=write(self.root/'mirror.json',cfg);rec={'operation':'mirror','sourcePart':'shinl','part':'shinr','source':str(self.source),
             'sourceSha256':c.sha(self.source),'sourceReceipt':str(self.rp),'sourceReceiptSha256':c.sha(self.rp),
             'sourceToAttachmentLocal':matrix.tolist(),'reflectionWorld':plane.tolist(),'frozenInputs':{str(cp):c.sha(cp)}}
        right={'receipt':rec,'receiptPath':write(self.root/'mirror-geometry.json',rec),'document':doc,'binary':binary};proof=replay.mirror_binding('shinr',left,right,self.tp,self.target,replay.Inputs())
        self.assertTrue(proof['literalEncodedPNUTIndicesWAndMapsReplayed']);self.assertFalse(proof['textureUOrNormalMapChannelFlipped'])
        rec['sourceToAttachmentLocal'][0][3]+=.001
        with self.assertRaisesRegex(ValueError,'reflection differs'):replay.mirror_binding('shinr',left,right,self.tp,self.target,replay.Inputs())
        rec['sourceToAttachmentLocal']=matrix.tolist();right['binary']=binary[:-1]+bytes([binary[-1]^1])
        with self.assertRaisesRegex(ValueError,'PNUT/winding/maps'):replay.mirror_binding('shinr',left,right,self.tp,self.target,replay.Inputs())

    def test_supplied_target_rebind_and_rehashed_corner_archive_reject(self):
        controls={'mode':detail.MODE,'receipt':{'path':'r','sha256':'a'*64},'sourceManifest':{'path':'m','sha256':'b'*64}}
        forged=deepcopy(self.target);forged['rig']['frames']['working'][c.PART_JOINTS['shinl']][0][3]+=.01
        with self.assertRaisesRegex(ValueError,'pinned live contract'):
            replay.staging_inputs(controls,self.tp,forged,'shinl','working',self.source,self.rp,{0:'skin'},0)
        archive=Path(self.entry['nativeCornerArchive']['path'])
        with np.load(archive,allow_pickle=False) as saved:rows={k:saved[k] for k in saved.files}
        rows['uvGltf'][0,0,0]+=.1;np.savez_compressed(archive,**rows)
        self.rec['nativeCornerArchive']=replay.file_row(archive);self.entry['nativeCornerArchive']=replay.file_row(archive);self.rebound_receipt()
        with self.assertRaisesRegex(ValueError,'corner archive differs'):self.invoke()

    def test_stage_entry_rejects_runtime_garment_role_and_foreign_part_before_recipe(self):
        controls={'mode':detail.MODE,'receipt':{'path':'r','sha256':'a'*64},'sourceManifest':{'path':'m','sha256':'b'*64}}
        for part,space,roles in [('shinl','runtime',{0:'skin'}),('chest','working',{0:'skin'}),('shinl','working',{0:'garment'}),('shinl','working',{0:'skin',1:'skin'})]:
            with self.assertRaisesRegex(ValueError,'ownership'):
                replay.staging_inputs(controls,self.tp,self.target,part,space,self.source,self.rp,roles,0)


if __name__=='__main__':unittest.main()