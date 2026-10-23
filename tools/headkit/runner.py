"""Immutable, input-hashed stage receipts for the reusable CPU processing chain."""
from pathlib import Path
import sys
import time
import traceback
import uuid
import numpy as np
from PIL import Image
from .common import read,write,require,pin,verify,asset,manifest,bindings,source_version,digest,code_pins,python_package_pins

# Every stage produces evidence that needs an explicit operator decision before consumption.
STAGES=('prepare','precluster','repair','unwrap','bake','ownership','tone','palette','export','native','render')


class Runner:
    def __init__(self, manifest_path, bindings_path, run, *, runtime=None):
        self.manifest_path=Path(manifest_path).resolve();self.bindings_path=Path(bindings_path).resolve()
        self.data=manifest(self.manifest_path);self.bindings=bindings(self.bindings_path);self.runtime=runtime
        self.run=Path(run).resolve();self.run.mkdir(parents=True,exist_ok=True)
        self.state_path=self.run/'state.json'
        self.state=read(self.state_path) if self.state_path.exists() else {'schemaVersion':1,'id':self.data['id'],'stages':{}}
        require(self.state['id']==self.data['id'],'Run belongs to a different head')

    def input(self,name):
        require(name in self.data['inputs'],'Missing manifest input: '+name)
        if name in ('ownership1k','ownership4k'):
            config=self.data.get('ownership',{})
            require(config.get('reviewed') is True,'Imported ownership needs reviewed UV-mesh binding')
            source=self.source('uvMesh','unwrap','mesh')
            require(config.get('sourceSha256')==pin(source)['sha256'],
                    'Imported ownership review must bind the exact UV mesh')
        if name=='field':
            review=self.data.get('approval',{}).get('appearanceField',{})
            geometry_role=next((role for role in ('uvMesh','repairedMesh','comfyExport')
                                if role in self.data['inputs']),None)
            require(geometry_role is not None,'Generated field needs an active geometry input')
            geometry=asset(self.manifest_path,self.data['inputs'][geometry_role])
            field=self.data['inputs'][name]
            require(review.get('decision')=='approved' and isinstance(review.get('notes'),str)
                    and review['notes'].strip() and review.get('geometryInput')==geometry_role
                    and review.get('geometrySha256')==geometry['sha256']
                    and review.get('fieldSha256')==field['sha256'],
                    'Generated field approval must bind its exact bytes to the active geometry input: '+geometry_role)
        atlas_roles={'basecolor4k','runtimeColor','runtimeShades'}|set(self.data.get('render',{}).get('mapInputs',{}).values())
        if name in atlas_roles:
            review=self.data.get('approval',{}).get('textureMaps',{}).get(name,{})
            require(review.get('decision')=='approved' and bool(review.get('notes','').strip()),
                    'Imported texture needs explicit UV-mesh review: '+name)
            source=self.source('uvMesh','unwrap','mesh')
            require(review.get('sourceSha256')==pin(source)['sha256']
                    and review.get('textureSha256')==self.data['inputs'][name]['sha256'],
                    'Imported texture review must bind the exact UV mesh and texture: '+name)
        return asset(self.manifest_path,self.data['inputs'][name])['path']

    def result(self,stage,*,require_review=True,_checked=None):
        if _checked is None:_checked={'results':{},'codeVersion':source_version()}
        if stage in _checked['results']:return _checked['results'][stage]
        row=self.state['stages'].get(stage);require(row is not None,'Stage not completed: '+stage)
        receipt=read(row['path']);verify([row]);verify(receipt['outputs']);verify(receipt['inputs'])
        require(receipt['codeVersion']==_checked['codeVersion'] and receipt['manifestHash']==digest(self.data)
                and receipt['bindingsHash']==digest(self.bindings),'Stale stage; rerun with current input snapshot: '+stage)
        require(receipt['state']=='complete','Failed stage: '+stage)
        if self.runtime is not None:require(receipt.get('runtimeIdentity')==self.runtime,'Stage runtime differs from active launcher')
        for dependency,expected in receipt.get('dependencies',{}).items():
            require(self.state['stages'].get(dependency)==expected,'Changed dependency; rerun stage: '+stage)
            self.result(dependency,_checked=_checked)
        if require_review:
            review_pin=self.state.get('reviews',{}).get(stage)
            require(review_pin is not None,'Visual review pending: '+stage)
            verify([review_pin]);review=read(review_pin['path'])
            require(review.get('stageReceipt')==row,'Stale visual review: '+stage)
            require(review.get('decision')=='approved','Visual review rejected: '+stage)
            _checked['results'][stage]=receipt['result']
        return receipt['result']

    def source(self,provided,stage,key):
        # Importing a reviewed artifact is explicit: it does not pretend its prior stages ran here.
        if provided in self.data['inputs']:return self.input(provided)
        row=self.result(stage)[key];verify([row]);return row['path']

    def execute(self,stage):
        require(stage in STAGES,'Unknown CPU stage')
        # Package bytecode and installed modules must remain inside the frozen inventory.
        sys.dont_write_bytecode=True
        package_inputs=python_package_pins(self.bindings,require_imports=self.runtime is not None)
        if stage in self.state['stages']:
            try:return {'reused':True,'result':self.result(stage,require_review=False)}
            except (ValueError,OSError):pass
        parent=self.run/stage;parent.mkdir(exist_ok=True)
        old=list(parent.glob('attempt-*/receipt.json'))
        failures=[read(p) for p in old if read(p).get('manifestHash')==digest(self.data)
                  and read(p).get('codeVersion')==source_version() and read(p).get('state')=='failed']
        require(len(failures)<2,'Two stage failures retained; fix the manifest or request a bounded exception before more trials')
        inputs=[pin(self.manifest_path),pin(self.bindings_path)]+package_inputs+code_pins()
        inputs += [asset(self.manifest_path,p) for p in self.data['inputs'].values()]
        for row in self.bindings.get('libraries',{}).values():inputs.extend(row['files'])
        for name in ('python','blender','client','embree'):
            if name in self.bindings:inputs.append(self.bindings[name])
        for name in ('toolchain','migrationReceipt'):
            if name in self.bindings:inputs.append(pin(self.bindings[name]))
        dependencies={'prepare':[], 'precluster':[], 'repair':[],
            'unwrap':[] if 'repairedMesh' in self.data['inputs'] else ['repair'],
            'bake':[] if 'uvMesh' in self.data['inputs'] else ['unwrap'],
            'ownership':[] if 'uvMesh' in self.data['inputs'] else ['unwrap'],
            'tone':[] if 'basecolor4k' in self.data['inputs'] else ['bake'],
            'palette':[] if 'runtimeColor' in self.data['inputs'] else ['tone'],
            'export':([] if 'uvMesh' in self.data['inputs'] else ['unwrap'])+([] if 'runtimeShades' in self.data['inputs'] else ['palette']),
            'native':['export'], 'render':[] if 'uvMesh' in self.data['inputs'] else ['unwrap']}
        if stage=='tone' and not any(role in self.data['inputs'] for role in ('ownership1k','ownership4k')):
            dependencies[stage].append('ownership')
        if stage=='palette' and 'ownership1k' not in self.data['inputs']:dependencies[stage].append('ownership')
        imported_atlases={'tone':('basecolor4k','ownership4k','ownership1k'),'palette':('runtimeColor','ownership1k'),
                          'export':('runtimeShades','ownership1k')}.get(stage,())
        if any(role in self.data['inputs'] for role in imported_atlases) and 'uvMesh' not in self.data['inputs'] and 'unwrap' not in dependencies[stage]:
            dependencies[stage].append('unwrap')
        dependency_pins={}
        for dependency in dependencies[stage]:
            self.result(dependency);row=self.state['stages'][dependency]
            dependency_pins[dependency]=row
            previous=read(row['path']);inputs.append(row);inputs.extend(previous['outputs'])
            inputs.append(self.state['reviews'][dependency])
        folder=parent/f'attempt-{len(list(parent.glob("attempt-*")))+1:02d}';folder.mkdir()
        begun=time.monotonic();receipt={'stage':stage,'manifestHash':digest(self.data),'bindingsHash':digest(self.bindings),
            'codeVersion':source_version(),'inputs':inputs,'state':'running','outputs':[], 'dependencies':dependency_pins,'runtimeIdentity':self.runtime}
        write(folder/'intent.json',receipt,fresh=True)
        try:
            result=self._execute(stage,folder);digest(result)
            python_package_pins(self.bindings,require_imports=self.runtime is not None)
            verify(inputs)
            receipt.update(state='complete',result=result,outputs=[pin(p) for p in sorted(folder.rglob('*')) if p.is_file() and p.name not in ('intent.json','receipt.json')])
        except Exception as exc:
            receipt.update(state='failed',error=str(exc),traceback=traceback.format_exc(),
                outputs=[pin(p) for p in sorted(folder.rglob('*')) if p.is_file() and p.name not in ('intent.json','receipt.json')])
            raise
        finally:
            receipt['elapsedSeconds']=time.monotonic()-begun;write(folder/'receipt.json',receipt,fresh=True)
            self.state['stages'][stage]=pin(folder/'receipt.json');write(self.state_path,self.state)
        return {'reused':False,'result':result}

    def _execute(self,stage,folder):
        m=self.data;b=self.bindings
        if stage=='prepare':
            from .images import prepare,prepare_multiview
            require(m.get('approval',{}).get('referenceDesignReviewed') is True,'Review design and feature inventory before preparation')
            require(m.get('features') and all(row.get('placementReviewed') is True for row in m['features']),
                    'Explicitly review hair routing and all horn/tusk/cyberware counts and placement')
            if m.get('profile','pixal-single-v1')=='pixal-single-v1':
                return prepare(self.input('clay'),self.input('detail'),m['alignment'],folder/'images')
            pairs={view:(self.input(view+'Clay'),self.input(view+'Detail')) for view in ('front','left','back','right')}
            return prepare_multiview(pairs,m['alignment'],folder/'images')
        if stage=='precluster':
            from .mesh import precluster
            return precluster(self.input('raw'),folder/'oriented.glb',b)
        if stage=='repair':
            from .mesh import repair
            return repair(self.input('comfyExport'),folder/'final.glb',b,m['mesh'],read(self.input('shellInspection')))
        if stage=='unwrap':
            from .gltf import mesh,write_mesh
            from .uv import unwrap,raster_audit,audit_imported_uvs
            source=self.source('repairedMesh','repair','source')
            value=mesh(source);original=value['positions'][value['faces']].copy();normals=value['normals']
            subtexel=m['mesh'].get('maximumSubtexelFraction',.005)
            if m['mesh'].get('reuseReviewedUvs',False):
                result=audit_imported_uvs(value,subtexel,m['mesh'].get('uv',{}))
            else:
                value,result=unwrap(value,b,dict(m.get('mesh',{}).get('uv',{}),maximumSubtexelFraction=subtexel))
                audit,_=raster_audit(value['uv'],4096);require(not audit['overlapFaces'] and not audit['degenerateUvFaces'] and not audit['unmappedUvFaces'],'4K UV audit failed')
                result['source4kAudit']=audit
            require(np.array_equal(original,value['positions'][value['faces']]),'UV processing changed ordered triangle corners')
            path=folder/'uv.glb';write_mesh(path,value['positions'],value['faces'],value['uv'],normals)
            result['mesh']=pin(path);return result
        if stage=='bake':
            from .textures import bake
            source=self.source('uvMesh','unwrap','mesh')
            return bake(source,self.input('field'),folder/'maps',allow_decoder_overshoot=m['mesh'].get('allowDecoderOvershoot',False),
                        max_subtexel_fraction=m['mesh'].get('maximumSubtexelFraction',.005))
        if stage=='ownership':
            from .palette import project_ownership
            source=self.source('uvMesh','unwrap','mesh');config=m['ownership']
            require(config.get('sourceSha256')==pin(source)['sha256'] and config.get('reviewed') is True,
                    'Ownership review must bind the exact UV mesh')
            if config['mode']=='atlas':
                image=Image.open(self.input('ownership4k'));require(image.mode=='L' and image.size==(4096,4096),'4K discrete ownership atlas required')
            else:
                require(config['mode']=='project','Unsupported ownership mode')
                views=[dict(row,mask=self.input(row['maskInput'])) for row in config['views']]
                project_ownership(source,views,b['embree'],folder/'projected.png')
                image=Image.open(folder/'projected.png').resize((4096,4096),Image.Resampling.NEAREST)
            require(np.max(np.asarray(image))<=9,'Unknown ownership must be resolved before proceeding')
            image.save(folder/'ownership-4096.png');image.resize((1024,1024),Image.Resampling.NEAREST).save(folder/'ownership-1024.png')
            return {'fourk':pin(folder/'ownership-4096.png'),'onek':pin(folder/'ownership-1024.png'),'channelIdsNeverBlended':True,'visualReviewRequired':True}
        if stage=='tone':
            from .textures import tone_match
            color=self.source('basecolor4k','bake','unused') if 'basecolor4k' in m['inputs'] else self.result('bake')['maps']['basecolor-4096.png']['path']
            if 'ownership4k' in m['inputs']:
                ownership=self.input('ownership4k');ownership_source=ownership;ownership_role='ownership4k';upsampling=None
            elif 'ownership1k' in m['inputs']:
                ownership_source=self.input('ownership1k');ownership_role='ownership1k';upsampling='nearest'
                with Image.open(ownership_source) as mask:
                    require(mask.mode=='L' and mask.size==(1024,1024),
                            'Imported ownership1k must be an actual 1024x1024 eight-bit L image')
                    labels=np.asarray(mask)
                    require(np.max(labels)<=9,'Unknown ownership must be resolved before tone matching')
                    ownership=folder/'ownership-4096-nearest.png'
                    mask.resize((4096,4096),Image.Resampling.NEAREST).save(ownership)
            else:
                ownership=self.result('ownership')['fourk']['path'];ownership_source=ownership
                ownership_role='ownership';upsampling=None
            for path in (color,ownership):
                with Image.open(path) as image:
                    require(image.size==(4096,4096),'Tone inputs must be actual 4096x4096 images')
                    if path==ownership:
                        require(image.mode=='L','Tone ownership must be an eight-bit L image')
                        require(np.max(np.asarray(image))<=9,'Unknown ownership must be resolved before tone matching')
            output=folder/'tone-4096.png';result=tone_match(color,ownership,self.input('detail' if m.get('profile','pixal-single-v1')=='pixal-single-v1' else 'frontDetail'),m['tone'],output)
            result.update(ownershipInputRole=ownership_role,ownershipSource=pin(ownership_source),
                          ownershipForTone=pin(ownership),ownershipUpsampling=upsampling)
            image=Image.open(output)
            require(image.size==(4096,4096),'Tone output must be actual 4096x4096 before deriving review maps')
            result['maps']={}
            for size in (2048,1024):
                path=folder/f'tone-{size}.png';image.resize((size,size),Image.Resampling.BOX).save(path);result['maps'][str(size)]=pin(path)
            return result
        if stage=='palette':
            from .palette import quantize
            color=self.input('runtimeColor') if 'runtimeColor' in m['inputs'] else self.result('tone')['maps']['1024']['path']
            palettes={layer:self.input(name) for layer,name in m['palette']['inputs'].items()}
            return quantize(color,self.input('ownership1k') if 'ownership1k' in m['inputs'] else self.result('ownership')['onek']['path'],palettes,m['palette']['rows'],folder/'palette',shade_offsets=m['palette'].get('shadeOffsets'))
        if stage=='export':
            from .native import prepare
            source=self.source('uvMesh','unwrap','mesh')
            shades=self.input('runtimeShades') if 'runtimeShades' in m['inputs'] else self.result('palette')['shades']['path']
            layers=self.input('ownership1k') if 'runtimeShades' in m['inputs'] else self.result('palette')['ownership']['path']
            require(m['fit'].get('model') is not None,'Choose a reserved model slot before native export')
            geometry_audit=None
            if 'uvMesh' in m['inputs'] or 'repairedMesh' in m['inputs']:
                from .mesh import audit
                audit_result=audit(source)
                audit_path=folder/'imported-mesh-audit.json'
                write(audit_path,audit_result,fresh=True)
                require(audit_result.get('passed') is True,
                        'Imported mesh failed topology/collision audit; retain the failed audit evidence')
                geometry_audit=pin(audit_path)
            uv_audit=None
            if 'uvMesh' in m['inputs']:
                from .gltf import mesh
                from .uv import audit_imported_uvs
                uv_result=audit_imported_uvs(mesh(source),m.get('mesh',{}).get('maximumSubtexelFraction',.005),m.get('mesh',{}).get('uv',{}))
                uv_path=folder/'imported-uv-audit.json';write(uv_path,uv_result,fresh=True)
                uv_audit=pin(uv_path)
            result=prepare(source,shades,layers,m['fit'],m['fit']['model'],folder/'converted')
            if uv_audit is not None:result['uvAudit']=uv_audit
            if geometry_audit is not None:result['geometryAudit']=geometry_audit
            return result
        if stage=='native':
            from .native import compile_and_package
            previous=self.result('export');return compile_and_package(Path(previous['ascii']['path']).parents[1],b['client'],folder/'native')
        if stage=='render':
            import subprocess,sys
            from .common import ROOT
            from .review_images import resolutions,atlas_sets,sheets,render_plan,validate_frames
            begun=time.monotonic()
            source=self.source('uvMesh','unwrap','mesh');cfg=dict(m['render'])
            if 'cameras' not in cfg:
                from .cameras import review_cameras
                from .gltf import mesh
                cfg['cameras']=review_cameras(mesh(source)['positions'],cfg['frontAngleDegrees'])
            cfg.update(mesh=source,output=str(folder/'renders'),maps={name:self.input(role) for name,role in cfg['mapInputs'].items()})
            render_plan(cfg)
            texture_sets,atlases=atlas_sets(cfg,folder/'renders',resolutions(cfg))
            cfg.update(textureSets={str(size):maps for size,maps in texture_sets.items()},atlases=atlases)
            cfg['inputs']=[pin(source),*[pin(p) for p in cfg['maps'].values()],*[row['image'] for row in atlases],*code_pins()]
            write(folder/'render-config.json',cfg,fresh=True)
            write(folder/'render-inputs.json',cfg['inputs']+[pin(folder/'render-config.json')],fresh=True)
            command=[sys.executable,str(ROOT/'tools/phenotypes/launch_shared_tool.py'),'--toolchain',b['toolchain'],
                '--migration-receipt',b['migrationReceipt'],'--tool','blender','--output',str(folder/'blender-launch')]
            command+=['--input-manifest',str(folder/'render-inputs.json')]
            command+=['--','--python',str(Path(__file__).parent/'blender_render.py'),'--','--config',str(folder/'render-config.json')]
            execution=subprocess.run(command,capture_output=True,text=True,timeout=1800,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            (folder/'blender.log').write_text(execution.stdout+'\n'+execution.stderr);require(execution.returncode==0,'CPU render failed; inspect log')
            result=read(folder/'renders'/'renders.json');validate_frames(cfg,result['views'])
            result.update(sheets(result['views'],folder/'renders',result['triangles']),elapsedWithEvidenceSeconds=time.monotonic()-begun)
            write(folder/'renders'/'renders.json',result);return result
        raise ValueError('Stage not implemented')

    def review(self,stage,decision,notes):
        require(decision in ('approved','rejected') and notes.strip(),'Explicit visual decision and notes required')
        self.result(stage,require_review=False);target=self.run/'reviews'/f'{stage}-{uuid.uuid4().hex}.json'
        result={'stageReceipt':self.state['stages'][stage],'decision':decision,'notes':notes,'productionAccepted':False}
        write(target,result,fresh=True);review_pin=pin(target)
        self.state.setdefault('reviews',{})[stage]=review_pin;write(self.state_path,self.state)
        return review_pin

    def status(self):
        result={}
        for stage in STAGES:
            if stage not in self.state['stages']:result[stage]='not-run';continue
            try:
                self.result(stage,require_review=False)
                review_pin=self.state.get('reviews',{}).get(stage)
                if review_pin:
                    verify([review_pin]);review=read(review_pin['path'])
                    require(review.get('stageReceipt')==self.state['stages'][stage],'Stale visual review: '+stage)
                    decision=review['decision']
                else:decision='pending'
                result[stage]={'state':'complete','review':decision}
            except (ValueError,OSError) as exc:result[stage]={'staleOrFailed':str(exc)}
        return {'id':self.data['id'],'stages':result,'next':'Explicitly choose the next stage; no GPU job is started by status/resume'}
