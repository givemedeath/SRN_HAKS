import struct,tempfile,unittest
from pathlib import Path
import numpy as np
from .phenomorpher_scene_v15a import read_attributes,native_attributes,glb_document,export_glb


def fixture():
    model_size=0x700;raw=bytearray()
    b=bytearray(12+model_size);struct.pack_into('<III',b,0,0,model_size,0)
    b[20:25]=b'test\0';b[12+0x72]=4
    struct.pack_into('<II',b,12+0x48,0xe8,3)
    for off,name,flag in [(0xe8,'test',1),(0x158,'pivot',1),(0x1c8,'mesh',33)]:
        at=12+off;b[at+0x20:at+0x20+len(name)+1]=(name+'\0').encode()
        struct.pack_into('<I',b,at+0x6c,flag)
    struct.pack_into('<III',b,12+0xe8+0x48,0x500,1,1)
    struct.pack_into('<I',b,12+0x500,0x158)
    struct.pack_into('<III',b,12+0x158+0x48,0x504,1,1)
    struct.pack_into('<I',b,12+0x504,0x1c8)
    at=12+0x1c8;struct.pack_into('<III',b,at+0x78,0x520,1,1)
    struct.pack_into('<3H',b,12+0x520+26,0,1,2)
    struct.pack_into('<HH',b,at+0x230,3,1);struct.pack_into('<I',b,at+0xdc,1)
    attrs=[(0x22c,np.array([[0,0,0],[1,0,0],[0,0,1]],'<f4')),(0x234,np.array([[0,0],[1,0],[0,1]],'<f4')),(0x244,np.tile(np.array([0,-1,0],'<f4'),(3,1))),(0x248,np.array([0xffffffff,0x01234567,0x89abcdef],'<u4'))]
    for field,a in attrs:
        struct.pack_into('<I',b,at+field,len(raw));raw.extend(a.tobytes())
    for field in (0x258,0x260):struct.pack_into('<I',b,at+field,0xffffffff)
    struct.pack_into('<I',b,8,len(raw))
    return bytes(b+raw)


class NativeColorTests(unittest.TestCase):
    def test_real_format_nested_tree_retains_opaque_uint32_colors(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'test.mdl';p.write_bytes(fixture())
            skeleton,attrs,_=read_attributes(p)
            self.assertEqual(skeleton['mesh']['parent'],'pivot')
            self.assertEqual(skeleton['pivot']['parent'],'test')
            np.testing.assert_array_equal(attrs['mesh']['color'].reshape(-1),np.array([0xffffffff,0x01234567,0x89abcdef],'<u4'))
            self.assertEqual(attrs['mesh']['color'].dtype,np.dtype('<u4'))
            self.assertNotIn('tangent',attrs['mesh'])

    def test_color_raw_bounds_rejected_not_silently_omitted(self):
        b=bytearray(fixture());struct.pack_into('<I',b,12+0x1c8+0x248,struct.unpack_from('<I',b,8)[0]-4)
        with self.assertRaisesRegex(ValueError,'raw bounds'):native_attributes(bytes(b),'test',{'mesh'})

    def test_glb_and_exact_companion_preserve_packed_color_without_display_rgba(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'test.mdl';p.write_bytes(fixture());_,attrs,_=read_attributes(p);a=attrs['mesh']
            m={**a,'name':'mesh','part':'chest','sourceAttributes':a}
            frames={'torso_g':np.eye(4)};parents={'torso_g':'null'}
            doc,binary=glb_document([m],frames,parents)
            primitive=doc['meshes'][0]['primitives'][0];self.assertNotIn('COLOR_0',primitive['attributes'])
            ix=primitive['attributes']['_NWN_PACKED_COLOR'];acc=doc['accessors'][ix];view=doc['bufferViews'][acc['bufferView']]
            values=np.frombuffer(binary,'<u4',count=3,offset=view['byteOffset'])
            np.testing.assert_array_equal(values,a['color'].reshape(-1))
            result=export_glb([m],frames,parents,Path(tmp)/'scene.glb')
            with np.load(result['sourceAttributeArchive']['path']) as data:np.testing.assert_array_equal(data['mesh0_color'],a['color'])

if __name__=='__main__':unittest.main()
