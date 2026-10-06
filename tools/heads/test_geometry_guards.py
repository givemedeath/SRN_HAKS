"""Corrupt native trees, altered retexture geometry and neck trim boundaries."""
from pathlib import Path
import struct
import tempfile
import unittest
import numpy as np
from correct_neck_rim import cap_neck, clip, write_glb
from head_export import triangles
from native_reader import decode
from verify_retexture import verify
from verify_texture_transfer import verify as verify_atlas
from audit_neck_revision import audit as audit_revision
from head_workflow import pin,write_fresh


def native_fixture():
    root,child,children=128,256,240
    faces=child+0x264; raw_offset=faces+32; raw_size=144
    data=bytearray(12+raw_offset+raw_size)
    struct.pack_into('<III',data,0,0,raw_offset,raw_size)
    for offset,name,flag in ((root,b'pmh0_head082',1),(child,b'pmh0_head082p0',33)):
        data[12+offset+32:12+offset+32+len(name)]=name
        struct.pack_into('<I',data,12+offset+0x6c,flag)
    struct.pack_into('<III',data,12+root+0x48,children,1,1)
    struct.pack_into('<I',data,12+children,child)
    struct.pack_into('<III',data,12+child+0x78,faces,1,1)
    struct.pack_into('<HH',data,12+child+0x230,3,1)
    values=[np.array([[0,0,0],[1,0,0],[0,1,0]]),np.array([[0,0],[1,0],[0,1]]),
            np.tile([0,0,1],(3,1)),np.tile([1,0,0],(3,1)),np.ones((3,1))]
    cursor=0
    for field,value in zip((0x22c,0x234,0x244,0x258,0x260),values):
        struct.pack_into('<I',data,12+child+field,cursor)
        block=value.astype('<f4').tobytes(); data[12+raw_offset+cursor:12+raw_offset+cursor+len(block)]=block; cursor+=len(block)
    struct.pack_into('<HHH',data,12+faces+26,0,1,2)
    return data,root,child,children


class GeometryGuards(unittest.TestCase):
    def test_atlas_transfer_retains_selected_geometry_and_rejects_uv_drift(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);source=root/'source.glb';returned=root/'returned.glb'
            p=np.array([[[0,0,0],[1,0,0],[0,1,1]],[[0,1,1],[1,0,0],[1,1,0]]],float)
            normal=np.tile([0,0,1],(2,3,1));uv=np.array([[[0,0],[1,0],[0,1]],[[0,1],[1,0],[1,1]]],float)
            write_glb(source,p,normal,uv);original=source.read_bytes()
            write_glb(returned,p*2+[3,4,5],np.tile([0,1,0],(2,3,1)),uv)
            verify_atlas(source,returned,root/'transfer.json')
            self.assertEqual(source.read_bytes(),original)
            shifted=uv.copy();shifted[0,0,0]=.01;write_glb(returned,p*2+[3,4,5],normal,shifted)
            with self.assertRaisesRegex(ValueError,'UVs'):verify_atlas(source,returned,root/'bad.json')

    def test_closed_neck_cap_has_opposite_winding_and_no_boundary(self):
        corners=np.array([[-1,-1,0],[1,-1,0],[1,1,0],[-1,1,0],
                          [-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]],float)
        faces=np.array([[0,1,5],[0,5,4],[1,2,6],[1,6,5],[2,3,7],[2,7,6],
                        [3,0,4],[3,4,7],[4,5,6],[4,6,7]])
        p=corners[faces]; n=np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0]);n/=np.linalg.norm(n,axis=1)[:,None]
        normal=np.repeat(n[:,None,:],3,axis=1); uv=np.tile([[.3,.3],[.6,.3],[.4,.6]],(len(p),1,1))
        closed,nn,uu,record=cap_neck(p,normal,uv,0)
        self.assertEqual(record['capLoops'],1);self.assertEqual(record['capTriangles'],2)
        np.testing.assert_array_equal(closed[:len(p)],p)
        np.testing.assert_array_equal(uu[:len(p)],uv)
        self.assertTrue(np.all(np.cross(closed[-2:,1]-closed[-2:,0],closed[-2:,2]-closed[-2:,0])[:,2]<0))
        vertices,ids=np.unique(closed.reshape(-1,3),axis=0,return_inverse=True);edges={}
        for row in ids.reshape(-1,3):
            for a,b in zip(row,np.roll(row,-1)):edges.setdefault(tuple(sorted((a,b))),[]).append((a,b))
        self.assertTrue(all(len(rows)==2 and rows[0]==rows[1][::-1] for rows in edges.values()))

    def test_actual_native_tree_bounds_and_unsupported_nodes(self):
        data,root,child,children=native_fixture()
        result=decode(data,'pmh0_head082')
        self.assertEqual(result[0]['name'],'pmh0_head082p0')
        np.testing.assert_equal(result[0]['faces'],[[0,1,2]])
        for operation in ('cycle','outside','skin','index'):
            bad=bytearray(data)
            if operation=='cycle': struct.pack_into('<I',bad,12+children,root)
            elif operation=='outside': struct.pack_into('<I',bad,12+root+0x48,len(bad))
            elif operation=='skin': struct.pack_into('<I',bad,12+child+0x6c,97)
            else: struct.pack_into('<H',bad,12+child+0x264+26,3)
            with self.subTest(operation=operation),self.assertRaises(ValueError): decode(bad,'pmh0_head082')
        with self.assertRaises(ValueError): decode(data[:-1],'pmh0_head082')
        with self.assertRaises(ValueError): decode(data,'pmh0_head083')

    def test_taper_preserves_upper_surface_and_closes_inward_lower_ring(self):
        corners=np.array([[-.04,-.04,0],[.04,-.04,0],[.04,.04,0],[-.04,.04,0],
                          [-.04,-.04,.1],[.04,-.04,.1],[.04,.04,.1],[-.04,.04,.1]])
        faces=np.array([[0,1,5],[0,5,4],[1,2,6],[1,6,5],[2,3,7],[2,7,6],
                        [3,0,4],[3,4,7],[4,5,6],[4,6,7]])
        p=corners[faces];normal=np.tile([0,0,1],(len(p),3,1));uv=np.tile([[.3,.3],[.6,.3],[.4,.6]],(len(p),1,1))
        result,n,u,c=cap_neck(p,normal,uv,0,.035,.5,[0,0])
        np.testing.assert_array_equal(result[:len(p)],p)
        np.testing.assert_array_equal(n[:len(p)],normal);np.testing.assert_array_equal(u[:len(p)],uv)
        cap=result[c['capFaceIds']]
        np.testing.assert_allclose(cap[:,:,2],-.035)
        self.assertAlmostEqual(abs(cap[:,:,:2]).max(),.02)
        _,ids=np.unique(result.reshape(-1,3),axis=0,return_inverse=True);edges={}
        for row in ids.reshape(-1,3):
            for a,b in zip(row,np.roll(row,-1)):edges.setdefault(tuple(sorted((a,b))),[]).append((a,b))
        self.assertTrue(all(len(rows)==2 and rows[0]==rows[1][::-1] for rows in edges.values()))
        for depth,inset,center in [(.07,.5,[0,0]),(.035,1,[0,0]),(.035,.5,None)]:
            with self.assertRaises(ValueError):cap_neck(p,normal,uv,0,depth,inset,center)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name,depth,inset in [('old',0,1),('new',.035,.5)]:
                pp,nn,uu,record=cap_neck(p,normal,uv,0,depth,inset,[0,0])
                source=root/(name+'.glb');write_glb(source,pp,nn,uu)
                write_fresh(root/(name+'-fit.json'),{'source':pin(source),'localMatrix':np.eye(4).tolist()})
                write_fresh(root/(name+'-correction.json'),{**record,'output':pin(source)})
            audit_revision(root/'old-fit.json',root/'old-correction.json',root/'new-fit.json',root/'new-correction.json',root/'audit.json')
            uu[0,0,0]+=.01;write_glb(root/'new.glb',pp,nn,uu)
            (root/'new-fit.json').unlink();(root/'new-correction.json').unlink()
            write_fresh(root/'new-fit.json',{'source':pin(root/'new.glb'),'localMatrix':np.eye(4).tolist()})
            write_fresh(root/'new-correction.json',{**record,'output':pin(root/'new.glb')})
            with self.assertRaisesRegex(ValueError,'P/N/UV'):
                audit_revision(root/'old-fit.json',root/'old-correction.json',root/'new-fit.json',root/'new-correction.json',root/'bad.json')

    def test_trim_interpolates_uvs_without_moving_retained_corners(self):
        p=np.array([[[-1,0,-1],[1,0,1],[0,1,1]]],float)
        n=np.tile([0,-1,1],(1,3,1)); n=n/np.linalg.norm(n,axis=2)[:,:,None]
        uv=np.array([[[0,0],[1,0],[.5,1]]],float)
        selected,normal,texture,counts=clip(p,n,uv,0)
        self.assertEqual(len(selected),2); self.assertEqual(counts['splitTriangles'],1)
        self.assertTrue(np.all(selected[:,:,2]>=0))
        self.assertTrue(any(np.array_equal(corner,p[0,1]) for corner in selected.reshape(-1,3)))
        boundary=selected[:,:,2]==0
        np.testing.assert_allclose(np.unique(texture[boundary],axis=0),[[.25,.5],[.5,0]])
        np.testing.assert_array_equal(p[0,0],[-1,0,-1])

    def test_retexture_geometry_and_uv_changes_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name); source=root/'source.glb'; returned=root/'returned.glb'
            p=np.array([[[0,0,0],[1,0,0],[0,1,0]]],float)
            n=np.tile([0,0,1],(1,3,1)); uv=p[:,:,:2].copy()
            write_glb(source,p,n,uv); write_glb(returned,p,n,uv)
            verify(source,returned,root/'same.json')
            for field in ('position','uv','normal'):
                pp,nn,uu=p.copy(),n.copy(),uv.copy()
                if field=='position': pp[0,1,0]+=.01
                elif field=='uv': uu[0,1,0]=.99
                else: nn[:]=[0,1,0]
                write_glb(returned,pp,nn,uu)
                with self.subTest(field=field),self.assertRaises(ValueError): verify(source,returned,root/(field+'.json'))


if __name__=='__main__': unittest.main()
