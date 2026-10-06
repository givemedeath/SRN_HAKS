from pathlib import Path
import json
import struct
import tempfile
import unittest
from catalog import discover,table
from gff import encode


class GalleryTests(unittest.TestCase):
    def test_native_pack_audit_rejects_stale_and_duplicate_payloads(self):
        import hashlib
        from build_gallery import verify_pack
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'sample.hak';header=bytearray(160);header[:8]=b'HAK V1.0'
            struct.pack_into('<I',header,16,1);struct.pack_into('<II',header,24,160,184)
            key=struct.pack('<16sIHH',b'custom',0,2002,0)
            path.write_bytes(header+key+struct.pack('<II',192,4)+b'data')
            row={'name':'custom.mdl','sha256':hashlib.sha256(b'data').hexdigest()}
            self.assertTrue(verify_pack(path,[row])['payloadVerified'])
            with self.assertRaisesRegex(ValueError,'differs'):verify_pack(path,[{**row,'sha256':'0'*64}])
            struct.pack_into('<I',header,16,2);struct.pack_into('<II',header,24,160,208)
            path.write_bytes(header+key+key+struct.pack('<II',224,4)*2+b'data')
            with self.assertRaisesRegex(ValueError,'Duplicate'):verify_pack(path,[row])
    def test_unregistered_models_get_test_appearances_and_every_tile_gets_a_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);pack=root/'pack';pack.mkdir();tables=root/'srn_2da';tables.mkdir()
            (root/'hakbuilder.json').write_text(json.dumps({'HakList':[{'Name':'srn_placeable','Path':'pack'}]}))
            (pack/'new.mdl').write_bytes(b'model')
            (pack/'sample.set').write_text('[GENERAL]\nName=Sample\n'+''.join(f'[TILE{i}]\nModel=tile{i}\n' for i in range(130)))
            for filename in ('placeables.2da','genericdoors.2da'):(tables/filename).write_text('2DA V2.0\n\nLabel ModelName\n4 stock stock\n')
            for filename in ('ambientmusic.2da','ambientsound.2da'):(tables/filename).write_text('2DA V2.0\n\nResource\n')
            (tables/'skyboxes.2da').write_text('2DA V2.0\n\nLABEL DAY\n')
            result=discover(root,{'prestaged':[],'additions':[]})
            entry=result['entries']['placeables'][0]
            self.assertEqual(entry['appearance'],5);self.assertTrue(entry['testOnlyAppearance'])
            pages=result['entries']['tilesets'];self.assertEqual(len(pages),3)
            self.assertEqual([tile for page in pages for tile in page['tiles']],list(range(130)))
            self.assertEqual(pages[1]['id'],'tilesets:sample:page2')
            self.assertEqual((tables/'placeables.2da').read_text(),'2DA V2.0\n\nLabel ModelName\n4 stock stock\n')
            (tables/'genericdoors.2da').write_text('2DA V2.0\n\nLabel ModelName\n900 custom new\n')
            doors=discover(root,{'prestaged':[],'additions':[]})['entries']['doors']
            self.assertEqual(doors[0]['appearance'],0);self.assertEqual(doors[0]['productionAppearance'],900)
    def test_refresh_tracks_models_blueprints_and_removed_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);pack=root/'pack';pack.mkdir();tables=root/'srn_2da';tables.mkdir()
            (root/'hakbuilder.json').write_text(json.dumps({'HakList':[{'Name':'pack','Path':'pack'}]}))
            (pack/'custom.mdl').write_bytes(b'model');(pack/'new.uti').write_bytes(b'blueprint')
            (tables/'placeables.2da').write_text('2DA V2.0\n\nLabel ModelName\n5 "Custom chair" CUSTOM\n6 stock stock\n7 alias CUSTOM\n')
            (tables/'genericdoors.2da').write_text('2DA V2.0\n\nLabel ModelName\n')
            for filename in ('ambientmusic.2da','ambientsound.2da'):(tables/filename).write_text('2DA V2.0\n\nResource\n')
            (tables/'skyboxes.2da').write_text('2DA V2.0\n\nLABEL DAY\n')
            c={'prestaged':['placeables:custom'],'additions':[]};first=discover(root,c)
            self.assertEqual(first['counts']['placeables'],1);self.assertEqual(first['counts']['items'],1)
            self.assertEqual(first['entries']['placeables'][0]['appearance'],5)
            (pack/'custom.mdl').unlink()
            with self.assertRaisesRegex(ValueError,'Unknown prestaged'):discover(root,c)
            second=discover(root,{'prestaged':[],'additions':[]});self.assertEqual(second['counts']['placeables'],0)
            self.assertEqual(second['resourceCount'],1)

    def test_table_defaults_quotes_and_invalid_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'table.2da';p.write_text('2DA V2.0\n\nDEFAULT: ****\nLabel Model\n12 "with spaces" model\n')
            self.assertEqual(table(p)[0],{'row':12,'Label':'with spaces','Model':'model'})
            p.write_text('2DA V2.0\n\nLabel Model\n12 missing\n')
            with self.assertRaisesRegex(ValueError,'Malformed'):table(p)
            p.write_bytes('2DA V2.0\n\nLabel Model\n12 "Café" model\n'.encode('cp1252'))
            self.assertEqual(table(p)[0]['Label'],'Café')

    def test_gff_nested_indices_localized_text_and_signed_values(self):
        doc={'__data_type':'IFO ','__struct_id':-1,'Name':{'type':'cexolocstring','value':{'0':'Gallery'}},
             'Count':{'type':'int','value':-5},'Rows':{'type':'list','value':[{'__struct_id':6,'Area_Name':{'type':'resref','value':'start'}}]}}
        blob=encode(doc);self.assertEqual(blob[:8],b'IFO V3.2')
        accented=encode({'__data_type':'UTD ','Name':{'type':'cexolocstring','value':{'0':'Café'}}})
        self.assertIn(b'Caf\xe9',accented);self.assertNotIn(b'Caf\xc3\xa9',accented)
        offsets=struct.unpack_from('<12I',blob,8);self.assertEqual(offsets[1],2)
        root_id,index,count=struct.unpack_from('<III',blob,offsets[0]);self.assertEqual((root_id,count),(0xffffffff,3))
        ids=struct.unpack_from('<3I',blob,offsets[8]+index)
        kinds=[struct.unpack_from('<III',blob,offsets[2]+12*i)[0] for i in ids]
        self.assertEqual(kinds,[12,5,15]);self.assertIn(b'Gallery',blob);self.assertIn(b'start',blob)
        with self.assertRaisesRegex(ValueError,'label'):encode({'__data_type':'IFO ','too_long_field_label':{'type':'int','value':0}})


if __name__=='__main__':unittest.main()
