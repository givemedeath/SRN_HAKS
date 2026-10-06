"""Exercise non-Human attachment and animation selection without installed tools."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from head_workflow import pin, read, write_fresh
from prepare_assembly import prepare


class DerivedAssemblyTests(unittest.TestCase):
    def test_troll_contract_drives_neck_rig_and_motion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); stock=root/'ascii';stock.mkdir()
            rig=stock/'pmg0.mdl';rig.write_text('Troll rig')
            neck=stock/'pmg0_neck001.mdl';neck.write_text('Troll neck')
            animation=stock/'a_ba.mdl'
            clips=('pause1','tlknorm','walk','run','castout','1hslashr','getlow','kneel','deadfnt')
            animation.write_text(''.join(f'newanim {clip} pmg0\nlength 1\ndoneanim {clip} pmg0\n' for clip in clips))
            body=root/'pmg0_chest001.mdl';body.write_bytes(b'protected Troll body')
            manifest=root/'body.json';write_fresh(manifest,{'resources':[{'path':body.name,'sha256':pin(body)['sha256']}]})
            source=root/'source.glb';source.write_bytes(b'head')
            palettes=[]
            for name in ('skin','hair'):
                file=root/name;file.write_bytes(name.encode());palettes.append(pin(file))
            frames={name:np.eye(4) for name in ('head_g','neck_g','torso_g')}
            target={'schemaVersion':1,'kind':'srn-head-target','race':'troll','sex':'male','prefix':'pmg0',
                    'phenotype':0,'approved':True,'bodyRevision':pin(manifest)['sha256'],'bodyManifest':pin(manifest),
                    'bodyResourceRoot':str(root),'rig':pin(rig),'neckGeometry':pin(neck),'palettes':palettes,
                    'animations':[pin(animation)],'headBindMatrix':frames['head_g'].tolist(),
                    'cranialEnvelope':[[-1,-1,-1],[1,1,1]],'landmarkTolerance':.035,'runtimeScale':10/7}
            target_path=root/'target.json';write_fresh(target_path,target)
            fit=root/'fit.json';write_fresh(fit,{'source':pin(source),'target':pin(target_path),'localMatrix':np.eye(4).tolist()})
            positions=np.array([[[0,0,0],[1,0,0],[0,1,0]]],float)
            normals=np.tile([0.,0,1],(1,3,1));uv=np.zeros((1,3,2))
            native={'name':'chest','position':positions[0],'normal':normals[0],'uv':uv[0],'faces':np.array([[0,1,2]])}
            with patch('prepare_assembly.world_frames',return_value=frames), patch('prepare_assembly.nodes',return_value={}), \
                 patch('prepare_assembly.decode',return_value=[native]), \
                 patch('prepare_assembly.mesh_corners',return_value=[{'position':positions,'normal':normals,'uv':uv}]), \
                 patch('prepare_assembly.triangles',return_value=(positions,normals,uv)), \
                 patch('prepare_assembly.pose',side_effect=lambda directory,prefix,clip,t,stock:(frames,{'time':t,'length':.5})) as sample:
                prepare(manifest,root,root,[fit],root/'review',target_path)
            result=read(root/'review/assembly.json')
            self.assertEqual(result['runtimeScale'],10/7)
            self.assertEqual(result['neckGeometry'],pin(neck))
            self.assertEqual(result['rig'],pin(rig))
            self.assertEqual(len(result['samples']),82)
            self.assertTrue(all(call.args[1]=='pmg0' for call in sample.call_args_list))
            self.assertEqual(max(call.args[3] for call in sample.call_args_list),.5)
            self.assertEqual(len(sample.call_args_list),90)
            self.assertFalse(result['productionAccepted'])


if __name__=='__main__':unittest.main()
